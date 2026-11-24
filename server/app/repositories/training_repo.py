"""Training task data access layer (SQLite)."""

import json
import math
from typing import Any

import aiosqlite


class TrainingTaskRepository:
    """CRUD operations for the ``training_tasks`` table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a training task and return it as a dict."""
        config_json = json.dumps(data.get("config", {}), ensure_ascii=False)
        await self._db.execute(
            """
            INSERT INTO training_tasks
                (id, name, dataset_id, base_model, training_type,
                 config, status, progress, created_at, experiment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["name"],
                data["dataset_id"],
                data["base_model"],
                data["training_type"],
                config_json,
                data.get("status", "pending"),
                data.get("progress", 0),
                data["created_at"],
                data.get("experiment_id"),
            ),
        )
        await self._db.commit()
        return await self.get_by_id(data["id"])

    async def get_by_id(self, task_id: str) -> dict[str, Any]:
        """Fetch a single task by ID. Raises KeyError if not found."""
        cursor = await self._db.execute("SELECT * FROM training_tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if row is None:
            raise KeyError(f"Training task {task_id} not found")
        return self._normalize(dict(row))

    async def list_all(
        self,
        status: str | None = None,
        experiment_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
        study_id: str | None = None,
        task_id: str | None = None,
        state: str = "all",
    ) -> tuple[list[dict[str, Any]], int]:
        """Return paginated training tasks, newest first."""
        conditions: list[str] = []
        params: list[Any] = []
        if status:
            conditions.append("t.status = ?")
            params.append(status)
        if experiment_id:
            conditions.append("t.experiment_id = ?")
            params.append(experiment_id)
        if study_id is not None:
            conditions.append("sr.study_id = ?")
            params.append(study_id)
        if task_id is not None:
            conditions.append("t.id = ?")
            params.append(task_id)
        if state == "active":
            conditions.append("t.status IN ('pending','exporting','training')")
        elif state == "attention":
            conditions.append(
                "(t.status IS NULL OR t.status NOT IN ('pending','exporting','training','completed','cancelled'))"
            )
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        source = "FROM training_tasks t LEFT JOIN experiments e ON e.id=t.experiment_id LEFT JOIN study_runs sr ON sr.experiment_id=e.id"

        count_cur = await self._db.execute(
            f"SELECT COUNT(*) {source} {where}",
            params,
        )
        count_row = await count_cur.fetchone()
        total = int(count_row[0]) if count_row is not None else 0

        offset = (page - 1) * page_size
        params.extend([page_size, offset])
        cursor = await self._db.execute(
            f"SELECT t.*, sr.study_id, e.name AS run_name {source} {where} ORDER BY t.created_at DESC, t.id DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = await cursor.fetchall()
        return [self._normalize(dict(r)) for r in rows], total

    async def update_status(
        self,
        task_id: str,
        status: str,
        **kwargs: Any,
    ) -> None:
        """Update task status and optional fields (progress, model_path, result, finished_at)."""
        sets = ["status = ?"]
        params: list[Any] = [status]
        for key in ("progress", "model_path", "result", "finished_at"):
            if key in kwargs:
                sets.append(f"{key} = ?")
                val = kwargs[key]
                if key == "result" and isinstance(val, dict):
                    val = json.dumps(val, ensure_ascii=False)
                params.append(val)
        params.append(task_id)
        await self._db.execute(
            f"UPDATE training_tasks SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        await self._db.commit()

    async def delete(self, task_id: str) -> None:
        """Delete a training task by ID."""
        cursor = await self._db.execute("DELETE FROM training_tasks WHERE id = ?", (task_id,))
        await self._db.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Training task {task_id} not found")

    @staticmethod
    def _normalize(row: dict[str, Any]) -> dict[str, Any]:
        """Parse JSON fields."""
        for field in ("config", "result"):
            raw = row.get(field)
            value = raw
            try:
                if isinstance(raw, str):
                    value = json.loads(
                        raw, parse_constant=_reject_constant, parse_float=_finite_float
                    )
                if value is not None and not isinstance(value, dict):
                    raise ValueError("Expected an object")
                row[f"{field}_state"] = "missing" if value is None else "recorded"
            except (ValueError, RecursionError):
                value = None
                row[f"{field}_state"] = "invalid"
            row[field] = value if field == "result" else value or {}
        progress = row.get("progress")
        valid = (
            isinstance(progress, (int, float))
            and not isinstance(progress, bool)
            and math.isfinite(progress)
            and 0 <= progress <= 1
        )
        row["progress_state"] = (
            "missing" if progress is None else "recorded" if valid else "invalid"
        )
        row["progress"] = progress if valid else None
        return row


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number
