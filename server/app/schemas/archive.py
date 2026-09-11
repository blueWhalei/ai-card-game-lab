"""Data archiving and cleanup schemas."""

from pydantic import BaseModel, Field


class ArchiveRequest(BaseModel):
    days_old: int = Field(default=30, ge=1, le=36500)
    game_type: str | None = None
    dry_run: bool = True


class CleanupRequest(BaseModel):
    days_old: int = Field(default=90, ge=1, le=36500)
    game_type: str | None = None
    dry_run: bool = True


class ArchiveResult(BaseModel):
    archived_games: int
    archived_rounds: int
    archived_traces: int
    archived_decisions: int
    archive_file: str | None
    freed_bytes: int


class CleanupResult(BaseModel):
    deleted_games: int
    deleted_rounds: int
    deleted_traces: int
    deleted_decisions: int
    deleted_jsonl_files: int
    freed_bytes: int
