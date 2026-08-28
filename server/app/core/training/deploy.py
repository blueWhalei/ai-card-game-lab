"""Model deploy helpers: LoRA merge, Ollama Modelfile, GGUF conversion scripts.

M3 deliverable — produces a deployable bundle under ``models/<task_id>/deploy/``.

Flow:
1. Merge LoRA adapter into base HF weights (requires training extras)
2. Write ``convert_gguf`` scripts for llama.cpp
3. Write Ollama ``Modelfile`` (FROM ./model.gguf)
4. Optionally ``ollama create`` when a GGUF already exists
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

_DEFAULT_SYSTEM = (
    "你是一个 AI 卡牌游戏玩家。根据当前局面选择最佳动作，"
    '按照 JSON 格式输出：{"action": {"type": "...", "cards": [...]}}'
)


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
    tokenizer = AutoTokenizer.from_pretrained(str(adapter), trust_remote_code=True)
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
        f'PARAMETER temperature 0.7\n'
        f'PARAMETER num_predict 512\n'
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
& (Join-Path $env:LLAMA_CPP_DIR "llama-quantize.exe") $GgufF16 $GgufQ4 q4_k_m
Write-Host "GGUF ready: $GgufQ4"
Write-Host "Next: ollama create <tag> -f $(Join-Path $Root 'Modelfile')"
""",
        encoding="utf-8",
    )

    readme = deploy_dir / "README.md"
    readme.write_text(
        """# 模型部署包

## 步骤

1. **合并 LoRA**（若尚无 `merged/`）：由后端导出接口自动完成，或手动 merge。
2. **转 GGUF**：设置 `LLAMA_CPP_DIR` 后运行 `convert_gguf.ps1` / `convert_gguf.sh`。
3. **导入 Ollama**：`ollama create <tag> -f Modelfile`（Modelfile 默认 `FROM ./model.gguf`）。
4. **验证**：在训练页点「验证」，或配置 AI 玩家 `provider: ollama` + `model_name: <tag>` 后开一局。

Mock 训练的 `model.bin` **不能**导出；需要真实 LoRA adapter。
""",
        encoding="utf-8",
    )

    return {
        "bash": str(bash),
        "powershell": str(ps1),
        "readme": str(readme),
    }


def try_ollama_create(
    *,
    deploy_dir: Path,
    tag: str,
    ollama_bin: str = "ollama",
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
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
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
            "Model path is not a LoRA adapter (mock placeholder cannot be exported). "
            "Train with use_mock=false first."
        )

    root = Path(models_dir) / task_id
    deploy_dir = root / "deploy"
    if deploy_dir.exists():
        # Keep prior GGUF if present
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

    tag = ollama_tag or f"acgl-{task_id[:12]}"
    create_result: dict[str, Any] | None = None
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
    logger.info("deploy_bundle_exported", **{k: meta[k] for k in ("task_id", "deploy_dir", "gguf_ready")})
    return meta
