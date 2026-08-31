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


class InvalidPlayerCountError(AppError):
    """Raised when player_ids length does not match the engine's slot range."""

    def __init__(
        self,
        game_type: str,
        got: int,
        min_players: int,
        max_players: int,
    ) -> None:
        if min_players == max_players:
            message = f"{game_type} 需要恰好 {min_players} 名选手，当前为 {got}"
        else:
            message = (
                f"{game_type} 需要 {min_players}-{max_players} 名选手，当前为 {got}"
            )
        super().__init__(
            message=message,
            code="INVALID_PLAYER_COUNT",
            status_code=400,
        )


class InvalidPlayerIdsError(AppError):
    """Raised when player_ids reference missing experiment configs."""

    def __init__(self, missing_ids: list[str]) -> None:
        ids_str = ", ".join(missing_ids)
        super().__init__(
            message=f"Unknown experiment config id(s) in player_ids: {ids_str}",
            code="INVALID_PLAYER_IDS",
            status_code=400,
        )


class ProviderNotConfiguredError(AppError):
    """Raised when an experiment config uses a provider without credentials."""

    def __init__(self, providers: list[str]) -> None:
        names = ", ".join(sorted(set(providers)))
        super().__init__(
            message=(
                f"LLM provider not configured: {names}. "
                "Set the matching API key in .env, or switch the experiment "
                "config to ollama."
            ),
            code="PROVIDER_NOT_CONFIGURED",
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


class NoExportableDataError(AppError):
    """No rows matched export filters (empty ChatML / dataset)."""

    def __init__(self, detail: str = "No exportable decision points") -> None:
        super().__init__(
            message=detail,
            code="NO_EXPORTABLE_DATA",
            status_code=400,
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


class TrainingGuardError(AppError):
    """Raised when a training task is rejected by an environment guard.

    Covers: missing training deps, insufficient RAM for CPU smoke, etc.
    Maps to HTTP 400 via the global ``AppError`` handler.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(
            message=detail,
            code="TRAINING_GUARD_FAILED",
            status_code=400,
        )


class DeployNotLoraError(AppError):
    def __init__(self, detail: str = "Model path is not a LoRA adapter directory") -> None:
        super().__init__(
            message=f"[lora] {detail}",
            code="DEPLOY_NOT_LORA",
            status_code=400,
        )


class DeployMergeFailedError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"[merge] {detail}",
            code="DEPLOY_MERGE_FAILED",
            status_code=400,
        )


class DeployLlamaCppMissingError(AppError):
    def __init__(self, detail: str | None = None) -> None:
        msg = detail or (
            "LLAMA_CPP_DIR is missing or invalid. "
            "Set it in .env to a llama.cpp checkout with convert_hf_to_gguf.py."
        )
        super().__init__(
            message=f"[gguf] {msg}",
            code="DEPLOY_LLAMA_CPP_MISSING",
            status_code=400,
        )


class DeployGgufFailedError(AppError):
    def __init__(self, detail: str, *, status_code: int = 500) -> None:
        super().__init__(
            message=f"[gguf] {detail}",
            code="DEPLOY_GGUF_FAILED",
            status_code=status_code,
        )


class DeployOllamaFailedError(AppError):
    def __init__(self, detail: str, *, status_code: int = 500) -> None:
        super().__init__(
            message=f"[ollama] {detail}",
            code="DEPLOY_OLLAMA_FAILED",
            status_code=status_code,
        )
