"""Pydantic models for training management endpoints."""

from pydantic import BaseModel


class TrainingConfig(BaseModel):
    learning_rate: float = 2e-5
    batch_size: int = 8
    num_epochs: int = 3
    output_format: str = "pytorch"


class CreateTrainingTaskRequest(BaseModel):
    name: str
    dataset_id: str
    training_type: str = "sft"
    base_model: str = "Qwen/Qwen2.5-1.5B"
    config: TrainingConfig = TrainingConfig()

