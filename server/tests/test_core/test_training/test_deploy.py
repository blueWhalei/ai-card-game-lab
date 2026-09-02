"""Tests for deploy bundle helpers (no torch required)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.training.deploy import (
    _resolve_quantize_bin,
    convert_merged_to_gguf,
    export_deploy_bundle,
    is_lora_adapter,
    push_lora_to_ollama,
    write_gguf_scripts,
    write_modelfile,
)
from app.core.training.verify import _extract_action_json
from app.utils.exceptions import (
    DeployGgufFailedError,
    DeployLlamaCppMissingError,
    DeployNotLoraError,
    DeployOllamaFailedError,
)


def test_is_lora_adapter_detects_config(tmp_path: Path) -> None:
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    assert is_lora_adapter(adapter) is True
    assert is_lora_adapter(tmp_path / "model.bin") is False


def test_write_modelfile_and_scripts(tmp_path: Path) -> None:
    deploy = tmp_path / "deploy"
    mf = write_modelfile(deploy, gguf_name="model.gguf")
    assert mf.is_file()
    text = mf.read_text(encoding="utf-8")
    assert "FROM ./model.gguf" in text
    scripts = write_gguf_scripts(deploy)
    assert Path(scripts["powershell"]).is_file()
    assert Path(scripts["bash"]).is_file()
    assert Path(scripts["readme"]).is_file()


def test_export_bundle_rejects_non_adapter_file(tmp_path: Path) -> None:
    placeholder = tmp_path / "task1" / "model.bin"
    placeholder.parent.mkdir(parents=True)
    placeholder.write_text("not-an-adapter", encoding="utf-8")
    with pytest.raises(ValueError, match="not a LoRA adapter"):
        export_deploy_bundle(
            task_id="task1",
            model_path=str(placeholder),
            base_model="Qwen/Qwen2.5-1.5B",
            models_dir=str(tmp_path),
            merge=False,
        )


def test_export_bundle_without_merge(tmp_path: Path) -> None:
    adapter = tmp_path / "task2" / "adapter"
    adapter.mkdir(parents=True)
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    (adapter / "adapter_model.safetensors").write_bytes(b"x")

    meta = export_deploy_bundle(
        task_id="task2",
        model_path=str(adapter),
        base_model="Qwen/Qwen2.5-1.5B",
        models_dir=str(tmp_path),
        merge=False,
        try_create=False,
    )
    assert Path(meta["deploy_dir"]).is_dir()
    assert Path(meta["modelfile"]).is_file()
    assert meta["merged"] is False
    assert meta["gguf_ready"] is False
    saved = json.loads(
        (Path(meta["deploy_dir"]) / "export_meta.json").read_text(encoding="utf-8")
    )
    assert saved["task_id"] == "task2"


def test_extract_action_json_variants() -> None:
    assert _extract_action_json('{"action_type":"PASS","cards":[]}') == {
        "action_type": "PASS",
        "cards": [],
    }
    nested = _extract_action_json('note {"action":{"type":"SINGLE","cards":["C3"]}}')
    assert nested == {"action_type": "SINGLE", "cards": ["C3"]}
    assert _extract_action_json("no json here") is None


def test_resolve_quantize_bin_windows_release(tmp_path: Path) -> None:
    llama = tmp_path / "llama.cpp"
    release = llama / "build" / "bin" / "Release"
    release.mkdir(parents=True)
    quant = release / "llama-quantize.exe"
    quant.write_text("stub", encoding="utf-8")
    assert _resolve_quantize_bin(llama) == quant


def test_convert_merged_to_gguf_missing_llama_dir(tmp_path: Path) -> None:
    deploy = tmp_path / "deploy"
    merged = deploy / "merged"
    merged.mkdir(parents=True)
    with pytest.raises(DeployLlamaCppMissingError):
        convert_merged_to_gguf(deploy, llama_cpp_dir=tmp_path / "nope")


def test_convert_merged_to_gguf_mocked_success(tmp_path: Path) -> None:
    deploy = tmp_path / "deploy"
    merged = deploy / "merged"
    merged.mkdir(parents=True)
    llama = tmp_path / "llama.cpp"
    llama.mkdir()
    (llama / "convert_hf_to_gguf.py").write_text("# stub", encoding="utf-8")
    (llama / "llama-quantize").write_text("stub", encoding="utf-8")
    (llama / "llama-quantize.exe").write_text("stub", encoding="utf-8")

    def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        # Second call (quantize) should create model.gguf
        if "llama-quantize" in str(cmd[0]) or (
            len(cmd) > 1 and "llama-quantize" in str(cmd[0])
        ):
            out = Path(cmd[2]) if len(cmd) > 2 else deploy / "model.gguf"
            # scripts pass: quantize f16 -> q4
            if len(cmd) >= 3:
                Path(cmd[2]).write_bytes(b"gguf")
            else:
                (deploy / "model.gguf").write_bytes(b"gguf")
        elif "convert_hf_to_gguf" in " ".join(str(c) for c in cmd):
            # outfile is after --outfile
            if "--outfile" in cmd:
                idx = cmd.index("--outfile")
                Path(cmd[idx + 1]).write_bytes(b"f16")
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = "ok"
        proc.stderr = ""
        return proc

    with patch("app.core.training.deploy.subprocess.run", side_effect=_fake_run):
        result = convert_merged_to_gguf(deploy, llama_cpp_dir=llama)

    assert result["ok"] is True
    assert Path(result["path"]).is_file()


def test_push_lora_reuses_gguf_skips_convert(tmp_path: Path) -> None:
    task_id = "task3abcdefgh"
    adapter = tmp_path / task_id / "adapter"
    adapter.mkdir(parents=True)
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    deploy = tmp_path / task_id / "deploy"
    deploy.mkdir(parents=True)
    (deploy / "model.gguf").write_bytes(b"existing")

    with (
        patch("app.core.training.deploy.merge_lora_to_hf", return_value=str(deploy / "merged")),
        patch("app.core.training.deploy.convert_merged_to_gguf") as convert_mock,
        patch(
            "app.core.training.deploy.try_ollama_create",
            return_value={"created": True, "tag": "cardlab-task3abcde", "returncode": 0},
        ),
    ):
        result = push_lora_to_ollama(
            task_id=task_id,
            model_path=str(adapter),
            base_model="Qwen/Qwen2.5-0.5B",
            models_dir=str(tmp_path),
            llama_cpp_dir="",
            force_convert=False,
        )

    convert_mock.assert_not_called()
    assert result["ok"] is True
    assert result["stages"]["gguf"]["skipped"] is True
    assert result["stages"]["ollama_create"]["ok"] is True


def test_push_lora_rejects_non_adapter(tmp_path: Path) -> None:
    blob = tmp_path / "t" / "model.bin"
    blob.parent.mkdir(parents=True)
    blob.write_text("x", encoding="utf-8")
    with pytest.raises(DeployNotLoraError):
        push_lora_to_ollama(
            task_id="t",
            model_path=str(blob),
            base_model="x",
            models_dir=str(tmp_path),
            llama_cpp_dir=str(tmp_path),
        )


def test_push_lora_ollama_failure_raises(tmp_path: Path) -> None:
    task_id = "task4abcdefgh"
    adapter = tmp_path / task_id / "adapter"
    adapter.mkdir(parents=True)
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    deploy = tmp_path / task_id / "deploy"
    deploy.mkdir(parents=True)
    (deploy / "model.gguf").write_bytes(b"g")

    with (
        patch("app.core.training.deploy.merge_lora_to_hf", return_value=str(deploy / "merged")),
        patch(
            "app.core.training.deploy.try_ollama_create",
            return_value={"created": False, "reason": "ollama_cli_not_found"},
        ),
    ):
        with pytest.raises(DeployOllamaFailedError):
            push_lora_to_ollama(
                task_id=task_id,
                model_path=str(adapter),
                base_model="Qwen/Qwen2.5-0.5B",
                models_dir=str(tmp_path),
                llama_cpp_dir="",
                force_convert=False,
            )


def test_convert_subprocess_nonzero_raises(tmp_path: Path) -> None:
    deploy = tmp_path / "deploy"
    (deploy / "merged").mkdir(parents=True)
    llama = tmp_path / "llama.cpp"
    llama.mkdir()
    (llama / "convert_hf_to_gguf.py").write_text("#", encoding="utf-8")
    (llama / "llama-quantize").write_text("#", encoding="utf-8")
    (llama / "llama-quantize.exe").write_text("#", encoding="utf-8")

    bad = MagicMock()
    bad.returncode = 1
    bad.stdout = ""
    bad.stderr = "boom"
    with patch("app.core.training.deploy.subprocess.run", return_value=bad):
        with pytest.raises(DeployGgufFailedError):
            convert_merged_to_gguf(deploy, llama_cpp_dir=llama)
