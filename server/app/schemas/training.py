"""Pydantic models for training management endpoints."""

from pydantic import BaseModel, Field


class TrainingConfig(BaseModel):
    learning_rate: float = 2e-5
    batch_size: int = 8
    num_epochs: int = 3
    output_format: str = "pytorch"
    lora_r: int = Field(default=8, ge=1, le=256)
    lora_alpha: int = Field(default=16, ge=1, le=512)
    lora_dropout: float = Field(default=0.05, ge=0.0, le=0.5)
    max_seq_length: int = Field(default=512, ge=64, le=4096)
    gradient_accumulation_steps: int = Field(default=1, ge=1, le=64)
    # None = no cap (use all samples); only honored by real LoRA path.
    max_steps: int | None = Field(default=None, ge=1, le=100000)
    max_samples: int | None = Field(default=None, ge=1, le=100000)
    # None = follow server default; True forces CPU smoke clamps; False disables.
    cpu_smoke: bool | None = None
    gradient_checkpointing: bool | None = None
    # 4-bit QLoRA. Requires CUDA + bitsandbytes (not in the poetry training extra).
    qlora: bool = False


class CreateTrainingTaskRequest(BaseModel):
    name: str
    dataset_id: str
    training_type: str = "sft"
    base_model: str = "Qwen/Qwen2.5-0.5B"
    config: TrainingConfig = TrainingConfig()
    experiment_id: str | None = None


class ExportModelRequest(BaseModel):
    ollama_tag: str | None = None
    merge: bool = True
    try_create: bool = False


class PushOllamaRequest(BaseModel):
    ollama_tag: str | None = None
    force_convert: bool = False


class VerifyModelRequest(BaseModel):
    ollama_tag: str | None = None
    run_game: bool = False
    player_ids: list[str] | None = None
