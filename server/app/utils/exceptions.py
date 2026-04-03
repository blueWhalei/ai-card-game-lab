"""Unified exception hierarchy for the application."""


class AppError(Exception):
    """Base exception for all application errors.

    Carries a machine-readable code and an HTTP status code so the global
    exception handler can build a consistent JSON error response.
    """

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


# ── Game ──────────────────────────────────────────────


class GameNotFoundError(AppError):
    def __init__(self, game_id: str) -> None:
        super().__init__(
            message=f"Game not found: {game_id}",
            code="GAME_NOT_FOUND",
            status_code=404,
        )


class GameAlreadyStartedError(AppError):
    def __init__(self, game_id: str) -> None:
        super().__init__(
            message=f"Game already started: {game_id}",
            code="GAME_ALREADY_STARTED",
            status_code=409,
        )


class InvalidActionError(AppError):
    def __init__(self, action: str, reason: str) -> None:
        super().__init__(
            message=f"Invalid action '{action}': {reason}",
            code="INVALID_ACTION",
            status_code=422,
        )


class UnsupportedGameTypeError(AppError):
    def __init__(self, game_type: str) -> None:
        super().__init__(
            message=f"Unsupported game type: {game_type}",
            code="UNSUPPORTED_GAME_TYPE",
            status_code=400,
        )


# ── AI ────────────────────────────────────────────────


class AIProviderError(AppError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(
            message=f"AI provider '{provider}' error: {detail}",
            code="AI_PROVIDER_ERROR",
            status_code=502,
        )


class AIRateLimitExceededError(AppError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(
            message=f"AI provider '{provider}' rate limit exceeded: {detail}",
            code="AI_RATE_LIMIT_EXCEEDED",
            status_code=429,
        )


class AITimeoutError(AppError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(
            message=f"AI provider '{provider}' timed out: {detail}",
            code="AI_TIMEOUT",
            status_code=504,
        )


class AIProviderUnavailableError(AppError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(
            message=f"AI provider '{provider}' unavailable: {detail}",
            code="AI_PROVIDER_UNAVAILABLE",
            status_code=503,
        )


class AIParseError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"Failed to parse AI response: {detail}",
            code="AI_PARSE_FAILED",
            status_code=422,
        )


# ── Data ──────────────────────────────────────────────


class DataExportError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"Data export failed: {detail}",
            code="DATA_EXPORT_FAILED",
            status_code=500,
        )


class DatasetNotFoundError(AppError):
    def __init__(self, dataset_id: str) -> None:
        super().__init__(
            message=f"Dataset not found: {dataset_id}",
            code="DATASET_NOT_FOUND",
            status_code=404,
        )


# ── Training ─────────────────────────────────────────


class TrainingTaskNotFoundError(AppError):
    def __init__(self, task_id: str) -> None:
        super().__init__(
            message=f"Training task not found: {task_id}",
            code="TRAINING_TASK_NOT_FOUND",
            status_code=404,
        )
