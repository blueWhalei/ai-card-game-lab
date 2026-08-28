"""Tests for deploy bundle helpers (no torch required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.training.deploy import (
    export_deploy_bundle,
    is_lora_adapter,
    write_gguf_scripts,
    write_modelfile,
)
from app.core.training.verify import _extract_action_json


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


def test_export_bundle_rejects_mock_placeholder(tmp_path: Path) -> None:
    mock = tmp_path / "task1" / "model.bin"
    mock.parent.mkdir(parents=True)
    mock.write_text("mock", encoding="utf-8")
    with pytest.raises(ValueError, match="not a LoRA adapter"):
        export_deploy_bundle(
            task_id="task1",
            model_path=str(mock),
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
