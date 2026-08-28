"""SFT training entrypoints: PEFT LoRA (real) + mock fallback.

Install real training deps with::

    cd server && poetry install --with training

Then set ``TRAINING_USE_MOCK=false`` (or ``config.use_mock=false``) to run LoRA.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Protocol

import structlog

logger = structlog.get_logger()

MOCK_STEPS = 20
MOCK_STEP_DELAY = 0.05  # keep mock fast for tests / UI demos


class ProgressCallback(Protocol):
    """Callback to report training progress."""

    async def __call__(self, progress: float, **kwargs: Any) -> None: ...


def training_deps_available() -> bool:
    """Return True when torch/transformers/peft/datasets can be imported."""
    try:
        import datasets  # noqa: F401
        import peft  # noqa: F401
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


async def run_mock_training(
    task_id: str,
    sft_data_path: str,
    config: dict[str, Any],
    on_progress: ProgressCallback,
) -> dict[str, Any]:
    """Simulate an SFT training run (CI / no GPU / missing deps)."""
    logger.info("mock_training_start", task_id=task_id, config=config)

    for step in range(1, MOCK_STEPS + 1):
        await asyncio.sleep(MOCK_STEP_DELAY)
        progress = step / MOCK_STEPS
        await on_progress(progress, step=step, total_steps=MOCK_STEPS)
        logger.debug("mock_training_step", task_id=task_id, step=step, progress=progress)

    result = {
        "train_loss": 0.42,
        "eval_loss": 0.51,
        "total_steps": MOCK_STEPS,
        "epochs": config.get("num_epochs", 3),
        "mock": True,
    }
    logger.info("mock_training_done", task_id=task_id, result=result)
    return result


def _load_chatml_texts(sft_data_path: str, tokenizer: Any) -> list[str]:
    """Load ChatML JSONL and render each sample to a single training string."""
    texts: list[str] = []
    path = Path(sft_data_path)
    with path.open("r", encoding="utf-8") as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            messages = record.get("messages")
            if not isinstance(messages, list) or not messages:
                continue
            if hasattr(tokenizer, "apply_chat_template"):
                try:
                    text = tokenizer.apply_chat_template(
                        messages,
                        tokenize=False,
                        add_generation_prompt=False,
                    )
                except Exception:
                    text = _fallback_format_messages(messages)
            else:
                text = _fallback_format_messages(messages)
            if text.strip():
                texts.append(text)
    return texts


def _fallback_format_messages(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for msg in messages:
        role = str(msg.get("role", "user"))
        content = str(msg.get("content", ""))
        parts.append(f"<|{role}|>\n{content}")
    return "\n".join(parts)


def _run_lora_sft_sync(
    *,
    task_id: str,
    sft_data_path: str,
    base_model: str,
    output_dir: str,
    config: dict[str, Any],
    progress_state: dict[str, float],
) -> dict[str, Any]:
    """Blocking PEFT LoRA SFT (intended to run via asyncio.to_thread)."""
    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainerCallback,
        TrainingArguments,
    )

    logger.info(
        "lora_sft_start",
        task_id=task_id,
        base_model=base_model,
        sft_data_path=sft_data_path,
        output_dir=output_dir,
    )

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    texts = _load_chatml_texts(sft_data_path, tokenizer)
    if not texts:
        raise ValueError(f"No usable ChatML samples in {sft_data_path}")

    max_seq_length = int(config.get("max_seq_length", 512))

    def tokenize(batch: dict[str, list[str]]) -> dict[str, Any]:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_seq_length,
            padding=False,
        )

    dataset = Dataset.from_dict({"text": texts}).map(
        tokenize,
        batched=True,
        remove_columns=["text"],
    )

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        trust_remote_code=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    )
    lora = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=int(config.get("lora_r", 8)),
        lora_alpha=int(config.get("lora_alpha", 16)),
        lora_dropout=float(config.get("lora_dropout", 0.05)),
        target_modules=config.get(
            "lora_target_modules",
            ["q_proj", "k_proj", "v_proj", "o_proj"],
        ),
    )
    model = get_peft_model(model, lora)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    args = TrainingArguments(
        output_dir=str(out / "checkpoints"),
        num_train_epochs=float(config.get("num_epochs", 3)),
        per_device_train_batch_size=int(config.get("batch_size", 1)),
        gradient_accumulation_steps=int(config.get("gradient_accumulation_steps", 1)),
        learning_rate=float(config.get("learning_rate", 2e-5)),
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        remove_unused_columns=False,
        fp16=torch.cuda.is_available(),
    )

    class _ProgressCallback(TrainerCallback):
        def on_log(self, args: Any, state: Any, control: Any, **kwargs: Any) -> None:
            max_steps = max(int(getattr(state, "max_steps", 0) or 0), 1)
            progress_state["p"] = min(1.0, float(state.global_step) / max_steps)

    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=dataset,
        data_collator=data_collator,
        callbacks=[_ProgressCallback()],
    )
    train_result = trainer.train()
    progress_state["p"] = 1.0

    adapter_dir = out / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    metrics = getattr(train_result, "metrics", {}) or {}
    result = {
        "mock": False,
        "base_model": base_model,
        "adapter_path": str(adapter_dir),
        "sample_count": len(texts),
        "train_loss": metrics.get("train_loss"),
        "train_runtime": metrics.get("train_runtime"),
        "epochs": config.get("num_epochs", 3),
        "lora_r": config.get("lora_r", 8),
    }
    logger.info("lora_sft_done", task_id=task_id, result=result)
    return result


async def run_lora_sft(
    task_id: str,
    sft_data_path: str,
    base_model: str,
    output_dir: str,
    config: dict[str, Any],
    on_progress: ProgressCallback,
) -> dict[str, Any]:
    """Run PEFT LoRA SFT in a worker thread while reporting progress."""
    if not training_deps_available():
        raise RuntimeError(
            "Training dependencies missing. Install with: "
            "cd server && poetry install --with training"
        )

    progress_state: dict[str, float] = {"p": 0.0}

    train_task = asyncio.create_task(
        asyncio.to_thread(
            _run_lora_sft_sync,
            task_id=task_id,
            sft_data_path=sft_data_path,
            base_model=base_model,
            output_dir=output_dir,
            config=config,
            progress_state=progress_state,
        )
    )

    while not train_task.done():
        await on_progress(progress_state["p"])
        done, _ = await asyncio.wait({train_task}, timeout=1.0)
        if done:
            break

    result = await train_task
    await on_progress(1.0)
    return result


async def run_sft_training(
    task_id: str,
    sft_data_path: str,
    base_model: str,
    output_dir: str,
    config: dict[str, Any],
    on_progress: ProgressCallback,
    *,
    default_use_mock: bool = True,
) -> dict[str, Any]:
    """Dispatch to LoRA or mock based on config and dependency availability.

    ``config.use_mock``:
    - True / False → honor explicitly
    - None / missing → use ``default_use_mock`` (from settings)
    """
    if "use_mock" in config and config["use_mock"] is not None:
        use_mock = bool(config["use_mock"])
    else:
        use_mock = default_use_mock
    if use_mock:
        result = await run_mock_training(task_id, sft_data_path, config, on_progress)
        # Write a placeholder so the pipeline still has an artifact path
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        placeholder = out / "model.bin"
        placeholder.write_text("mock model placeholder", encoding="utf-8")
        result["adapter_path"] = str(placeholder)
        return result

    return await run_lora_sft(
        task_id=task_id,
        sft_data_path=sft_data_path,
        base_model=base_model,
        output_dir=output_dir,
        config=config,
        on_progress=on_progress,
    )
