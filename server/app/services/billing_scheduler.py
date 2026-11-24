"""Local lifecycle worker for opt-in plans; does not run while the service is stopped."""

import asyncio
from datetime import UTC, datetime
from functools import partial
from typing import Any

import structlog

from app.config import Settings
from app.database import connect_sqlite
from app.repositories.billing_schedule_repo import BillingScheduleRepository
from app.services.study_billing_service import StudyBillingService
from app.utils.exceptions import AppError

logger = structlog.get_logger()


class BillingScheduler:
    poll_seconds = 30
    max_jobs = 2

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs: dict[str, asyncio.Task[None]] = {}

    async def tick(self) -> None:
        if not self.settings.billing_scheduler_enabled:
            return
        async with connect_sqlite(self.settings.sqlite_path) as db:
            repo = BillingScheduleRepository(db)
            now = datetime.now(UTC).isoformat()
            await repo.heartbeat(now)
            await db.commit()
            candidates = await repo.due(now)
        for candidate in candidates:
            if len(self.jobs) >= self.max_jobs:
                break
            study_id = candidate["study_id"]
            if study_id in self.jobs:
                continue
            task = asyncio.create_task(self._run_job(candidate))
            self.jobs[study_id] = task
            task.add_done_callback(partial(self._forget, study_id))

    def _forget(self, study_id: str, task: asyncio.Task[None]) -> None:
        self.jobs.pop(study_id, None)

    async def _run_job(self, candidate: dict[str, Any]) -> None:
        try:
            async with connect_sqlite(self.settings.sqlite_path) as db:
                await StudyBillingService().sync(
                    db,
                    candidate["study_id"],
                    candidate["config_revision"],
                    self.settings,
                    schedule_revision=candidate["revision"],
                )
        except AppError as exc:
            logger.info("billing_schedule_attempt_finished", code=exc.code)
        except Exception as exc:
            # No remote bodies, credential values or arbitrary exception messages in logs.
            logger.warning("billing_schedule_worker_error", error_type=type(exc).__name__)

    async def run(self) -> None:
        try:
            while True:
                try:
                    await self.tick()
                except Exception as exc:
                    logger.warning("billing_schedule_poll_error", error_type=type(exc).__name__)
                await asyncio.sleep(self.poll_seconds)
        finally:
            await self.stop()

    async def stop(self) -> None:
        tasks = list(self.jobs.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.jobs.clear()
