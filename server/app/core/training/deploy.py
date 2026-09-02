"""Model deploy helpers: LoRA merge, Ollama Modelfile, GGUF conversion.

Produces a deployable bundle under ``models/<task_id>/deploy/``.

Flows:
1. Export bundle — merge (optional) + scripts + Modelfile
2. Push to Ollama — merge → convert/quantize → ``ollama create``
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import structlog

from app.utils.exceptions import (
    DeployGgufFailedError,
    DeployLlamaCppMissingError,
    DeployMergeFailedError,
    DeployNotLoraError,
    DeployOllamaFailedError,
)

logger = structlog.get_logger()

_DEFAULT_SYSTEM = (
    "你是一个 AI 卡牌游戏玩家。根据当前局面选择最佳动作，"
    '按照 JSON 格式输出：{"action": {"type": "...", "cards": [...]}}'
)

GGUF_CONVERT_TIMEOUT_S = 1800
OLLAMA_CREATE_TIMEOUT_S = 600

# Windows defaults to GBK for ``text=True``; llama.cpp / Python child output is UTF-8.
_SUBPROCESS_CAPTURE = {"capture_output": True, "encoding": "utf-8", "errors": "replace"}


def is_lora_adapter(model_path: str | Path) -> bool:
    """Return True if path looks like a PEFT adapter directory."""
    path = Path(model_path)
    if path.is_file():
        return False
    return (path / "adapter_config.json").is_file() or (path / "adapter_model.safetensors").is_file()


def merge_lora_to_hf(
    *,
    base_model: str,
    adapter_path: str | Path,
    output_dir: str | Path,
) -> str:
    """Merge LoRA adapter into base model and save full HF weights.

    Requires ``poetry install --with training``.
    """
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Merging LoRA requires training deps: cd server && poetry install --with training"
        ) from exc

    adapter = Path(adapter_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    logger.info("lora_merge_start", base_model=base_model, adapter=str(adapter), output=str(out))
    # Load vocab from the base model: adapter tokenizer files from training can be
    # incompatible with llama.cpp convert_hf_to_gguf (oversized/corrupt tokenizer.json).
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        trust_remote_code=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    )
    model = PeftModel.from_pretrained(base, str(adapter))
    merged = model.merge_and_unload()
    merged.save_pretrained(str(out))
    tokenizer.save_pretrained(str(out))
    logger.info("lora_merge_done", output=str(out))
    return str(out)


def write_modelfile(
    deploy_dir: Path,
    *,
    gguf_name: str = "model.gguf",
    system_prompt: str = _DEFAULT_SYSTEM,
) -> Path:
    """Write an Ollama Modelfile that loads a local GGUF."""
    deploy_dir.mkdir(parents=True, exist_ok=True)
    path = deploy_dir / "Modelfile"
    content = (
        f"FROM ./{gguf_name}\n"
        f"PARAMETER temperature 0.7\n"
        f"PARAMETER num_predict 512\n"
        f'SYSTEM """{system_prompt}"""\n'
    )
    path.write_text(content, encoding="utf-8")
    return path


def write_gguf_scripts(deploy_dir: Path, *, merged_dirname: str = "merged") -> dict[str, str]:
    """Write bash + PowerShell helpers that call llama.cpp convert/quantize."""
    deploy_dir.mkdir(parents=True, exist_ok=True)

    bash = deploy_dir / "convert_gguf.sh"
    bash.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
# Requires: LLAMA_CPP_DIR pointing at a llama.cpp checkout with convert_hf_to_gguf.py
ROOT="$(cd "$(dirname "$0")" && pwd)"
MERGED="$ROOT/{merged_dirname}"
GGUF_F16="$ROOT/model-f16.gguf"
GGUF_Q4="$ROOT/model.gguf"
: "${{LLAMA_CPP_DIR:?Set LLAMA_CPP_DIR to your llama.cpp directory}}"

python "$LLAMA_CPP_DIR/convert_hf_to_gguf.py" "$MERGED" --outfile "$GGUF_F16"
"$LLAMA_CPP_DIR/llama-quantize" "$GGUF_F16" "$GGUF_Q4" q4_k_m
echo "GGUF ready: $GGUF_Q4"
echo "Next: ollama create <tag> -f $ROOT/Modelfile"
""",
        encoding="utf-8",
    )

    ps1 = deploy_dir / "convert_gguf.ps1"
    ps1.write_text(
        f"""# Requires: $env:LLAMA_CPP_DIR = path to llama.cpp
$ErrorActionPreference = "Stop"
if (-not $env:LLAMA_CPP_DIR) {{ throw "Set LLAMA_CPP_DIR to your llama.cpp directory" }}
$Root = $PSScriptRoot
$Merged = Join-Path $Root "{merged_dirname}"
$GgufF16 = Join-Path $Root "model-f16.gguf"
$GgufQ4 = Join-Path $Root "model.gguf"
python (Join-Path $env:LLAMA_CPP_DIR "convert_hf_to_gguf.py") $Merged --outfile $GgufF16
$Quantize = @(
  (Join-Path $env:LLAMA_CPP_DIR "llama-quantize.exe"),
  (Join-Path $env:LLAMA_CPP_DIR "build\\bin\\Release\\llama-quantize.exe"),
  (Join-Path $env:LLAMA_CPP_DIR "build\\bin\\llama-quantize.exe")
) | Where-Object {{ Test-Path $_ }} | Select-Object -First 1
if (-not $Quantize) {{ throw "llama-quantize not found under LLAMA_CPP_DIR (build llama.cpp first)" }}
& $Quantize $GgufF16 $GgufQ4 q4_k_m
Write-Host "GGUF ready: $GgufQ4"
Write-Host "Next: ollama create <tag> -f $(Join-Path $Root 'Modelfile')"
""",
        encoding="utf-8",
    )

    readme = deploy_dir / "README.md"
    readme.write_text(
        """# 模型部署包

## 步骤

1. **合并 LoRA**（若尚无 `merged/`）：由后端导出接口或「推送到 Ollama」完成。
2. **转 GGUF**：优先用训练台「推送到 Ollama」；或设置 `LLAMA_CPP_DIR` 后运行 `convert_gguf.ps1` / `convert_gguf.sh`。
3. **导入 Ollama**：一键推送会执行 `ollama create`；手动则为 `ollama create <tag> -f Modelfile`。
4. **验证**：在训练页点「验证」，或配置 AI 玩家 `provider: ollama` + `model_name: <tag>` 后开一局。

需要真实 LoRA adapter 目录（`adapter_config.json`）。
""",
        encoding="utf-8",
    )

    return {
        "bash": str(bash),
        "powershell": str(ps1),
        "readme": str(readme),
    }


def _resolve_quantize_bin(llama_cpp: Path) -> Path:
    for candidate in (
        llama_cpp / "llama-quantize.exe",
        llama_cpp / "llama-quantize",
        llama_cpp / "build" / "bin" / "llama-quantize.exe",
        llama_cpp / "build" / "bin" / "llama-quantize",
        llama_cpp / "build" / "bin" / "Release" / "llama-quantize.exe",
        llama_cpp / "build" / "bin" / "Release" / "llama-quantize",
        llama_cpp / "build" / "bin" / "Debug" / "llama-quantize.exe",
        llama_cpp / "build" / "bin" / "Debug" / "llama-quantize",
    ):
        if candidate.is_file():
            return candidate
    raise DeployLlamaCppMissingError(
        f"llama-quantize not found under {llama_cpp}. "
        "Build llama.cpp first (on Windows, check build/bin/Release/)."
    )


def convert_merged_to_gguf(
    deploy_dir: Path,
    *,
    llama_cpp_dir: str | Path,
    merged_dirname: str = "merged",
    quant: str = "q4_k_m",
    timeout_s: int = GGUF_CONVERT_TIMEOUT_S,
) -> dict[str, Any]:
    """Convert ``deploy/merged`` HF weights to quantized ``model.gguf`` via llama.cpp."""
    deploy = Path(deploy_dir)
    llama = Path(llama_cpp_dir) if llama_cpp_dir else Path()
    if not str(llama_cpp_dir).strip() or not llama.is_dir():
        raise DeployLlamaCppMissingError()

    convert_py = llama / "convert_hf_to_gguf.py"
    if not convert_py.is_file():
        raise DeployLlamaCppMissingError(
            f"convert_hf_to_gguf.py not found in {llama}. "
            "Set LLAMA_CPP_DIR to a llama.cpp checkout."
        )

    merged = deploy / merged_dirname
    if not merged.is_dir():
        raise DeployGgufFailedError(
            f"Merged HF directory missing: {merged}. Merge LoRA first.",
            status_code=400,
        )

    quantize_bin = _resolve_quantize_bin(llama)
    gguf_f16 = deploy / "model-f16.gguf"
    gguf_q4 = deploy / "model.gguf"

    try:
        convert_proc = subprocess.run(
            [sys.executable, str(convert_py), str(merged), "--outfile", str(gguf_f16)],
            cwd=str(deploy),
            timeout=timeout_s,
            check=False,
            **_SUBPROCESS_CAPTURE,
        )
    except subprocess.TimeoutExpired as exc:
        raise DeployGgufFailedError(
            f"convert_hf_to_gguf timed out after {timeout_s}s",
            status_code=504,
        ) from exc

    if convert_proc.returncode != 0:
        err = (convert_proc.stderr or convert_proc.stdout or "")[-1500:]
        raise DeployGgufFailedError(f"convert_hf_to_gguf failed: {err}")

    try:
        quant_proc = subprocess.run(
            [str(quantize_bin), str(gguf_f16), str(gguf_q4), quant],
            cwd=str(deploy),
            timeout=timeout_s,
            check=False,
            **_SUBPROCESS_CAPTURE,
        )
    except subprocess.TimeoutExpired as exc:
        raise DeployGgufFailedError(
            f"llama-quantize timed out after {timeout_s}s",
            status_code=504,
        ) from exc

    if quant_proc.returncode != 0:
        err = (quant_proc.stderr or quant_proc.stdout or "")[-1500:]
        raise DeployGgufFailedError(f"llama-quantize failed: {err}")

    if not gguf_q4.is_file():
        raise DeployGgufFailedError("Quantize finished but model.gguf was not created")

    logger.info("gguf_convert_done", path=str(gguf_q4))
    return {
        "ok": True,
        "path": str(gguf_q4),
        "f16_path": str(gguf_f16),
        "quant": quant,
    }


def try_ollama_create(
    *,
    deploy_dir: Path,
    tag: str,
    ollama_bin: str = "ollama",
    timeout_s: int = OLLAMA_CREATE_TIMEOUT_S,
) -> dict[str, Any]:
    """Run ``ollama create`` if ``model.gguf`` exists under deploy_dir."""
    gguf = deploy_dir / "model.gguf"
    modelfile = deploy_dir / "Modelfile"
    if not gguf.is_file():
        return {
            "created": False,
            "reason": "model.gguf_missing",
            "hint": "Run convert_gguf.ps1 / convert_gguf.sh first",
        }
    if not modelfile.is_file():
        write_modelfile(deploy_dir)

    try:
        proc = subprocess.run(
            [ollama_bin, "create", tag, "-f", str(modelfile)],
            cwd=str(deploy_dir),
            timeout=timeout_s,
            check=False,
            **_SUBPROCESS_CAPTURE,
        )
    except FileNotFoundError:
        return {"created": False, "reason": "ollama_cli_not_found"}
    except subprocess.TimeoutExpired:
        return {"created": False, "reason": "ollama_create_timeout"}

    ok = proc.returncode == 0
    return {
        "created": ok,
        "tag": tag,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
        "returncode": proc.returncode,
    }


def _ensure_deploy_dir(root: Path) -> Path:
    deploy_dir = root / "deploy"
    if deploy_dir.exists():
        preserved_gguf = deploy_dir / "model.gguf"
        tmp_gguf: Path | None = None
        if preserved_gguf.is_file():
            tmp_gguf = root / "_model.gguf.bak"
            shutil.copy2(preserved_gguf, tmp_gguf)
        shutil.rmtree(deploy_dir)
        deploy_dir.mkdir(parents=True, exist_ok=True)
        if tmp_gguf and tmp_gguf.is_file():
            shutil.move(str(tmp_gguf), str(deploy_dir / "model.gguf"))
    else:
        deploy_dir.mkdir(parents=True, exist_ok=True)
    return deploy_dir


def push_lora_to_ollama(
    *,
    task_id: str,
    model_path: str,
    base_model: str,
    models_dir: str | Path,
    llama_cpp_dir: str,
    ollama_tag: str | None = None,
    ollama_bin: str = "ollama",
    force_convert: bool = False,
) -> dict[str, Any]:
    """Merge LoRA → GGUF → ollama create. Raises Deploy* errors on failure."""
    if not is_lora_adapter(model_path):
        raise DeployNotLoraError()

    root = Path(models_dir) / task_id
    deploy_dir = _ensure_deploy_dir(root)
    tag = ollama_tag or f"cardlab-{task_id[:12]}"
    stages: dict[str, Any] = {}

    merged_dir = deploy_dir / "merged"
    try:
        merge_lora_to_hf(
            base_model=base_model,
            adapter_path=model_path,
            output_dir=merged_dir,
        )
        stages["merge"] = {"ok": True, "merged_path": str(merged_dir)}
    except RuntimeError as exc:
        raise DeployMergeFailedError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface merge failures clearly
        raise DeployMergeFailedError(str(exc)) from exc

    gguf_path = deploy_dir / "model.gguf"
    if gguf_path.is_file() and not force_convert:
        stages["gguf"] = {"ok": True, "skipped": True, "path": str(gguf_path)}
    else:
        if not str(llama_cpp_dir).strip():
            raise DeployLlamaCppMissingError()
        gguf_result = convert_merged_to_gguf(deploy_dir, llama_cpp_dir=llama_cpp_dir)
        stages["gguf"] = {
            "ok": True,
            "skipped": False,
            "path": gguf_result["path"],
        }

    write_modelfile(deploy_dir)
    write_gguf_scripts(deploy_dir)

    create_result = try_ollama_create(
        deploy_dir=deploy_dir,
        tag=tag,
        ollama_bin=ollama_bin,
    )
    if not create_result.get("created"):
        reason = str(create_result.get("reason") or "unknown")
        hint = str(create_result.get("hint") or create_result.get("stderr") or "")
        status = 504 if "timeout" in reason else 500
        if reason == "ollama_cli_not_found":
            status = 400
            hint = "Install Ollama and ensure `ollama` is on PATH (or set OLLAMA_BIN)."
        raise DeployOllamaFailedError(
            f"ollama create failed ({reason}). {hint}".strip(),
            status_code=status,
        )

    stages["ollama_create"] = {"ok": True, "tag": tag}

    meta: dict[str, Any] = {
        "ok": True,
        "model_id": task_id,
        "task_id": task_id,
        "base_model": base_model,
        "adapter_path": model_path,
        "deploy_dir": str(deploy_dir),
        "ollama_tag": tag,
        "stages": stages,
        "gguf_ready": True,
        "merged": True,
        "merged_path": str(merged_dir),
        "ollama_create": create_result,
    }
    (deploy_dir / "export_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("push_lora_to_ollama_done", task_id=task_id, ollama_tag=tag)
    return meta


def export_deploy_bundle(
    *,
    task_id: str,
    model_path: str,
    base_model: str,
    models_dir: str | Path,
    ollama_tag: str | None = None,
    merge: bool = True,
    try_create: bool = False,
) -> dict[str, Any]:
    """Build deploy bundle for a completed training task.

    Returns paths and status flags. Does not require GGUF to already exist.
    """
    if not is_lora_adapter(model_path):
        raise ValueError(
            "Model path is not a LoRA adapter directory. Train a real LoRA task first."
        )

    root = Path(models_dir) / task_id
    deploy_dir = _ensure_deploy_dir(root)

    merged_dir = deploy_dir / "merged"
    merge_status: dict[str, Any] = {"merged": False}
    if merge:
        try:
            merge_lora_to_hf(
                base_model=base_model,
                adapter_path=model_path,
                output_dir=merged_dir,
            )
            merge_status = {"merged": True, "merged_path": str(merged_dir)}
        except RuntimeError as exc:
            merge_status = {"merged": False, "error": str(exc)}
            logger.warning("lora_merge_skipped", error=str(exc))

    modelfile = write_modelfile(deploy_dir)
    scripts = write_gguf_scripts(deploy_dir)

    meta = {
        "task_id": task_id,
        "base_model": base_model,
        "adapter_path": model_path,
        "deploy_dir": str(deploy_dir),
        "modelfile": str(modelfile),
        **scripts,
        **merge_status,
        "gguf_ready": (deploy_dir / "model.gguf").is_file(),
    }

    tag = ollama_tag or f"cardlab-{task_id[:12]}"
    if try_create:
        create_result = try_ollama_create(deploy_dir=deploy_dir, tag=tag)
        meta["ollama_create"] = create_result
        meta["ollama_tag"] = tag
    else:
        meta["ollama_tag"] = tag
        meta["ollama_create"] = {"created": False, "reason": "skipped"}

    (deploy_dir / "export_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        "deploy_bundle_exported",
        **{k: meta[k] for k in ("task_id", "deploy_dir", "gguf_ready")},
    )
    return meta
