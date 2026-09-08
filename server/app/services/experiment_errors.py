"""Experiment service exceptions (shared, no circular imports)."""

from __future__ import annotations

from app.utils.exceptions import AppError


class ExperimentNotFoundError(AppError):
    def __init__(self, experiment_id: str) -> None:
        super().__init__(
            message=f"Experiment not found: {experiment_id}",
            code="EXPERIMENT_NOT_FOUND",
            status_code=404,
        )


class ExperimentValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            code="EXPERIMENT_VALIDATION_FAILED",
            status_code=400,
        )
