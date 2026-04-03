"""Training task data access layer (SQLite)."""

import json
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
                 config, status, progress, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        await self._db.commit()
        return await self.get_by_id(data["id"])

    async def get_by_id(self, task_id: str) -> dict[str, Any]:
        """Fetch a single task by ID. Raises KeyError if not found."""
        cursor = await self._db.execute(
            "SELECT * FROM training_tasks WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            raise KeyError(f"Training task {task_id} not found")
        return self._normalize(dict(row))
    async def list_all(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return paginated training tasks, newest first."""
        where = ""
        params: list[Any] = []
        if status:
            where = "WHERE status = ?"
            params.append(status)

        count_cur = await self._db.execute(
            f"SELECT COUNT(*) FROM training_tasks {where}", params,
        )
        total = (await count_cur.fetchone())[0]

        offset = (page - 1) * page_size
        params.extend([page_size, offset])
        cursor = await self._db.execute(
            f"SELECT * FROM training_tasks {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
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
            f"UPDATE training_tasks SET {', '.join(sets)} WHERE id = ?", params,
        )
        await self._db.commit()

    async def delete(self, task_id: str) -> None:
        """Delete a training task by ID."""
        cursor = await self._db.execute(
            "DELETE FROM training_tasks WHERE id = ?", (task_id,)
        )
        await self._db.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Training task {task_id} not found")

    @staticmethod
    def _normalize(row: dict[str, Any]) -> dict[str, Any]:
        """Parse JSON fields."""
        if isinstance(row.get("config"), str):
            try:
                row["config"] = json.loads(row["config"])
            except json.JSONDecodeError:
                row["config"] = {}
        if isinstance(row.get("result"), str):
            try:
                row["result"] = json.loads(row["result"])
            except json.JSONDecodeError:
                pass
        return row
