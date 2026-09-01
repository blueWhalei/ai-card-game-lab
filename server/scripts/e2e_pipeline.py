#!/usr/bin/env python3
"""End-to-end pipeline CLI for AI Card Game Lab (M4).

Orchestrates: health check → collect games → export decisions →
create dataset → start training → print deploy hints.

Requires the backend API to be running (default http://localhost:8000).

Examples::

    poetry run python scripts/e2e_pipeline.py guide
    poetry run python scripts/e2e_pipeline.py check
    poetry run python scripts/e2e_pipeline.py collect --count 1
    poetry run python scripts/e2e_pipeline.py all --count 1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    print("httpx is required. Run: cd server && poetry install", file=sys.stderr)
    sys.exit(2)

DEFAULT_PLAYERS = ["cfg_temp_09", "cfg_temp_06", "cfg_temp_12"]
DEFAULT_BASE = "http://localhost:8000"


def _api(base: str, method: str, path: str, **kwargs: Any) -> Any:
    url = f"{base.rstrip('/')}{path}"
    with httpx.Client(timeout=120.0) as client:
        resp = client.request(method, url, **kwargs)
        resp.raise_for_status()
        if not resp.content:
            return None
        payload = resp.json()
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload


def cmd_guide(_: argparse.Namespace) -> int:
    print(
        """
AI Card Game Lab — 1 小时闭环指南（斗地主）
==========================================

目标：配置 Key → 采一局 → 导出可训数据 → PEFT LoRA → 本地部署验证

[0] 准备
  - 复制 .env.example → .env，填入至少一个 LLM API Key（或配 Ollama）
  - 在前端「实验配置」页创建至少 3 份选手（斗地主需要 3 个槽位）
  - 启动后端：start-backend.bat  或  cd server && poetry run uvicorn ...
  - 启动前端（可选观战）：start-frontend.bat

[1] 健康检查
  poetry run python scripts/e2e_pipeline.py check

[2] 采集（至少 1 局；批量可加 --count）
  poetry run python scripts/e2e_pipeline.py collect --count 1

[3] 导出决策点（默认仅 train_usable，不含思考）
  poetry run python scripts/e2e_pipeline.py export

[4] 创建数据集 + 训练任务（PEFT LoRA / 无 GPU 走 CPU 冒烟）
  poetry run python scripts/e2e_pipeline.py train
  # 先：cd server && poetry install --with training
  # 详见 docs/E2E_PIPELINE.md「CPU Smoke（无 GPU）」；墙钟 ≤5min，不为牌力；勿在 CI 拉 HF 全量 e2e

[5] 部署（真实 LoRA 产物）
  - 前端「模型仓库」→ 导出部署包
  - 设置 LLAMA_CPP_DIR，运行 deploy/convert_gguf.ps1
  - ollama create <tag> -f Modelfile
  - 「验证决策」或「测一局」

一键（检查 + 采集 + 导出 + 真训）：
  poetry run python scripts/e2e_pipeline.py all --count 1

前端：http://localhost:5173
API：  http://localhost:8000/docs
""".strip()
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[2]
    env_file = root / ".env"
    print(f"[check] project root: {root}")
    print(f"[check] .env exists: {env_file.is_file()}")
    if not env_file.is_file():
        print("  → copy .env.example to .env and fill API keys")
    try:
        health = _api(args.base_url, "GET", "/api/v1/system/health")
        print(f"[check] API health: {health}")
    except Exception as exc:
        print(f"[check] API unreachable at {args.base_url}: {exc}", file=sys.stderr)
        print("  → start backend first (start-backend.bat)")
        return 1
    try:
        resolved = _resolve_players(args.base_url, args.players, stage="check")
        if resolved is None:
            return 1
        args.players = resolved
    except Exception as exc:
        print(f"[check] failed to list experiment configs: {exc}", file=sys.stderr)
        return 1
    print("[check] OK")
    return 0


def _resolve_players(
    base_url: str,
    requested: list[str],
    *,
    stage: str,
) -> list[str] | None:
    """Use requested ids if they exist; otherwise first 3 configs. None if < 3."""
    configs = _api(base_url, "GET", "/api/v1/experiment-configs")
    ids = [str(c.get("id")) for c in (configs or []) if c.get("id")]
    print(f"[{stage}] experiment configs: {ids}")
    if all(p in ids for p in requested):
        return requested
    if len(ids) >= 3:
        fallback = ids[:3]
        print(f"  → requested {requested} missing; using {fallback}")
        return fallback
    print(
        "  → need at least 3 experiment configs; create them at /experiment-configs",
        file=sys.stderr,
    )
    return None


def cmd_collect(args: argparse.Namespace) -> int:
    resolved = _resolve_players(args.base_url, args.players, stage="collect")
    if resolved is None:
        return 1
    args.players = resolved
    print(f"[collect] batch create {args.count} doudizhu game(s) ...")
    data = _api(
        args.base_url,
        "POST",
        "/api/v1/games/batch",
        json={
            "game_type": "doudizhu",
            "player_ids": args.players,
            "count": args.count,
        },
    )
    game_ids = list(data.get("game_ids") or [])
    print(f"[collect] started: {game_ids}")
    if args.no_wait:
        return 0
    return _wait_games(args.base_url, game_ids, timeout=args.timeout)


def _wait_games(base: str, game_ids: list[str], timeout: int) -> int:
    terminal = {"completed", "finished", "failed", "cancelled", "error"}
    deadline = time.time() + timeout
    pending = set(game_ids)
    while pending and time.time() < deadline:
        done: list[str] = []
        for gid in list(pending):
            game = _api(base, "GET", f"/api/v1/games/{gid}")
            status = str(game.get("status") or "")
            print(f"  {gid}: {status}")
            if status in terminal:
                done.append(gid)
        for gid in done:
            pending.discard(gid)
        if pending:
            time.sleep(3)
    if pending:
        print(f"[collect] timeout waiting for: {sorted(pending)}", file=sys.stderr)
        return 1
    print("[collect] all games finished")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    print("[export] decision points → ChatML ...")
    data = _api(
        args.base_url,
        "POST",
        "/api/v1/decision-points/export",
        json={
            "train_usable_only": True,
            "include_thinking": False,
        },
    )
    print(f"[export] filepath={data.get('filepath')} count={data.get('count')}")
    if not data.get("count"):
        print("  → no usable decision points; run collect first", file=sys.stderr)
        return 1
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    print("[train] create dataset from doudizhu games ...")
    ds = _api(
        args.base_url,
        "POST",
        "/api/v1/datasets",
        json={
            "name": args.dataset_name,
            "game_type": "doudizhu",
            "filters": {},
        },
    )
    dataset_id = ds.get("id")
    print(f"[train] dataset_id={dataset_id} samples={ds.get('sample_count')}")
    if not dataset_id:
        print("  → dataset create failed", file=sys.stderr)
        return 1
    if int(ds.get("sample_count") or 0) == 0:
        print("  → empty dataset; collect games first", file=sys.stderr)
        return 1

    print("[train] create training task (PEFT LoRA / CPU smoke) ...")
    task = _api(
        args.base_url,
        "POST",
        "/api/v1/training/tasks",
        json={
            "name": args.task_name,
            "dataset_id": dataset_id,
            "base_model": args.base_model,
            "training_type": "sft",
            "config": {
                "learning_rate": 2e-5,
                "batch_size": 1,
                "num_epochs": 1,
                "lora_r": 8,
                "max_steps": 20,
                "output_format": "pytorch",
            },
        },
    )
    task_id = task.get("id")
    print(f"[train] task_id={task_id} status={task.get('status')}")
    if args.no_wait or not task_id:
        return 0
    return _wait_training(args.base_url, str(task_id), timeout=args.timeout)


def _wait_training(base: str, task_id: str, timeout: int) -> int:
    terminal = {"completed", "failed", "cancelled"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = _api(base, "GET", f"/api/v1/training/tasks/{task_id}")
        status = str(task.get("status") or "")
        progress = task.get("progress")
        print(f"  {task_id}: {status} progress={progress}")
        if status in terminal:
            if status != "completed":
                print(f"[train] ended with {status}: {task.get('result')}", file=sys.stderr)
                return 1
            print(f"[train] model_path={task.get('model_path')}")
            return 0
        time.sleep(2)
    print("[train] timeout", file=sys.stderr)
    return 1


def cmd_deploy_hints(args: argparse.Namespace) -> int:
    models = _api(args.base_url, "GET", "/api/v1/models") or []
    print(f"[deploy] completed models: {len(models)}")
    if not models:
        print("  → no models yet; run train first")
        return 0
    latest = models[0]
    mid = latest.get("id")
    print(json.dumps(latest, ensure_ascii=False, indent=2))
    print(
        f"""
Next:
  1. POST /api/v1/models/{mid}/export   or UI「导出部署包」
  2. Set LLAMA_CPP_DIR → run models/{mid}/deploy/convert_gguf.ps1
  3. ollama create acgl-{str(mid)[:12]} -f models/{mid}/deploy/Modelfile
  4. POST /api/v1/models/{mid}/verify   or UI「验证决策」/「测一局」
""".strip()
    )
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    for fn in (cmd_check, cmd_collect, cmd_export, cmd_train, cmd_deploy_hints):
        code = fn(args)
        if code != 0:
            return code
    print("[all] pipeline finished")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AI Card Game Lab E2E pipeline (M4)")
    p.add_argument(
        "command",
        choices=["guide", "check", "collect", "export", "train", "deploy-hints", "all"],
        help="Pipeline stage",
    )
    p.add_argument("--base-url", default=DEFAULT_BASE, help="API base URL")
    p.add_argument(
        "--players",
        default=",".join(DEFAULT_PLAYERS),
        help="Comma-separated three experiment config ids",
    )
    p.add_argument("--count", type=int, default=1, help="Games to collect")
    p.add_argument("--timeout", type=int, default=1800, help="Wait timeout seconds")
    p.add_argument("--no-wait", action="store_true", help="Do not poll for completion")
    p.add_argument("--dataset-name", default=f"e2e-doudizhu-{time.strftime('%Y%m%d_%H%M%S')}")
    p.add_argument("--task-name", default=f"e2e-sft-{time.strftime('%Y%m%d_%H%M%S')}")
    p.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B")
    return p


def _parse_players(raw: str) -> list[str]:
    players = [p.strip() for p in raw.split(",") if p.strip()]
    if len(players) != 3:
        raise SystemExit(f"--players must have exactly 3 ids, got {players!r}")
    return players


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.players = _parse_players(args.players)
    dispatch = {
        "guide": cmd_guide,
        "check": cmd_check,
        "collect": cmd_collect,
        "export": cmd_export,
        "train": cmd_train,
        "deploy-hints": cmd_deploy_hints,
        "all": cmd_all,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
