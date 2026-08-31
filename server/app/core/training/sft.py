"""SFT training entrypoint: PEFT LoRA only.

Install training deps with::

    cd server && poetry install --with training
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Protocol

import structlog

logger = structlog.get_logger()


class ProgressCallback(Protocol):
    """Callback to report training progress."""

    async def __call__(self, progress: float, **kwargs: Any) -> None: ...


def truncate_texts(texts: list[str], max_samples: int | None) -> list[str]:
    """Cap a list of training texts to ``max_samples`` items.

    ``None`` or ``0`` means no cap (preserve all samples). Negative values are
    treated as no cap as well, mirroring ``config.get("max_samples") or len``.
    """
    if max_samples is None:
        return texts
    n = int(max_samples)
    if n <= 0:
        return texts
    return texts[:n]


def should_cancel(cancel_flag: dict[str, bool] | None) -> bool:
    """Pure check used by the cancel TrainerCallback and tests."""
    return bool(cancel_flag is not None and cancel_flag.get("cancel"))


def lower_process_priority() -> Any:
    """Drop process priority so CPU smoke training does not freeze the host.

    Best-effort: any failure is logged and swallowed so training still runs.
    Returns a restore callable that reverts the priority change (also
    best-effort); callers should invoke it in a ``finally`` block. Returns
    ``None`` when no change was applied, in which case there is nothing to
    restore.
    """
    try:
        if sys.platform == "win32":
            import psutil

            proc = psutil.Process()
            prev = proc.nice()
            proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)

            def _restore() -> None:
                try:
                    proc.nice(prev)
                except Exception as exc:  # restore is best-effort
                    logger.warning("restore_process_priority_failed", error=str(exc))

            return _restore
        else:
            prev_nice = os.nice(0)
            os.nice(5)

            def _restore() -> None:
                try:
                    # os.nice takes a delta; push back toward the previous value.
                    os.nice(prev_nice - os.nice(0))
                except Exception as exc:  # restore is best-effort
                    logger.warning("restore_process_priority_failed", error=str(exc))

            return _restore
    except Exception as exc:  # priority is best-effort
        logger.warning("lower_process_priority_failed", error=str(exc))
        return None


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
    cancel_flag: dict[str, bool] | None = None,
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

    if config.get("cpu_smoke"):
        from app.core.training.cpu_smoke import clamp_cpu_smoke_config

        config = clamp_cpu_smoke_config(config, base_model=base_model)

    # Only lower process priority for CPU smoke runs, and restore it after
    # training finishes so the whole uvicorn process is not permanently
    # demoted for other request paths.
    restore_priority: Any = None
    if config.get("cpu_smoke"):
        restore_priority = lower_process_priority()

    logger.info(
        "lora_sft_start",
        task_id=task_id,
        base_model=base_model,
        sft_data_path=sft_data_path,
        output_dir=output_dir,
        cpu_smoke=bool(config.get("cpu_smoke")),
    )

    try:
        tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        texts = _load_chatml_texts(sft_data_path, tokenizer)
        if not texts:
            raise ValueError(f"No usable ChatML samples in {sft_data_path}")
        texts = truncate_texts(texts, config.get("max_samples"))

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

        max_steps = int(config.get("max_steps") or 0)
        ta_kwargs: dict[str, Any] = {
            "output_dir": str(out / "checkpoints"),
            "num_train_epochs": float(config.get("num_epochs", 3)),
            "per_device_train_batch_size": int(config.get("batch_size", 1)),
            "gradient_accumulation_steps": int(config.get("gradient_accumulation_steps", 1)),
            "learning_rate": float(config.get("learning_rate", 2e-5)),
            "logging_steps": 1,
            "save_strategy": "no",
            "report_to": [],
            "remove_unused_columns": False,
            "fp16": torch.cuda.is_available(),
            "gradient_checkpointing": bool(config.get("gradient_checkpointing", False)),
        }
        if max_steps > 0:
            ta_kwargs["max_steps"] = max_steps
        args = TrainingArguments(**ta_kwargs)

        class _ProgressCallback(TrainerCallback):
            def on_log(self, args: Any, state: Any, control: Any, **kwargs: Any) -> None:
                max_steps_cb = max(int(getattr(state, "max_steps", 0) or 0), 1)
                progress_state["p"] = min(1.0, float(state.global_step) / max_steps_cb)

        class _CancelCallback(TrainerCallback):
            def on_step_end(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
                if should_cancel(cancel_flag):
                    control.should_training_stop = True
                return control

        data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
        trainer = Trainer(
            model=model,
            args=args,
            train_dataset=dataset,
            data_collator=data_collator,
            callbacks=[_ProgressCallback(), _CancelCallback()],
        )
        train_result = trainer.train()
        progress_state["p"] = 1.0

        adapter_dir = out / "adapter"
        adapter_dir.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(adapter_dir))
        tokenizer.save_pretrained(str(adapter_dir))

        metrics = getattr(train_result, "metrics", {}) or {}
        result = {
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
    finally:
        if restore_priority is not None:
            restore_priority()


async def run_lora_sft(
    task_id: str,
    sft_data_path: str,
    base_model: str,
    output_dir: str,
    config: dict[str, Any],
    on_progress: ProgressCallback,
    *,
    cancel_flag: dict[str, bool] | None = None,
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
            cancel_flag=cancel_flag,
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
    cancel_flag: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Run PEFT LoRA SFT. Missing training deps raise ``RuntimeError``."""
    return await run_lora_sft(
        task_id=task_id,
        sft_data_path=sft_data_path,
        base_model=base_model,
        output_dir=output_dir,
        config=config,
        on_progress=on_progress,
        cancel_flag=cancel_flag,
    )
