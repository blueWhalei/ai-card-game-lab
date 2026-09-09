"""Experiment protocol as Task = Dataset × Solver × Scorer (+ engine).

``schema_version`` 2 stores nested sections. Callers read and mutate through the
accessors below — never dig into section keys ad hoc. Collect rejects anything
that is not a complete v2 document (no silent migration from v1).
"""

from __future__ import annotations

import secrets
from typing import Any

PROTOCOL_SCHEMA_VERSION = 2

_ENGINE_KEYS = (
    "game_type",
    "engine_version",
    "decision_schema_version",
    "rules_ref",
    "phases",
    "prompt_keys",
    "roles",
    "supports_deal_seed",
    "benchmark_seed_count",
)


def build_protocol(
    *,
    players: list[dict[str, Any]],
    source_experiment_id: str | None,
    pair_deals: bool,
    deal_seeds: list[int],
    frozen_at: str,
    prompt_version: str,
    collect_mode: str,
    protocol_fingerprint: dict[str, Any],
    evaluator: dict[str, Any] | None = None,
    prompts: dict[str, dict[str, Any]] | None = None,
    thinking_budget: dict[str, Any] | None = None,
    memory: str | None = None,
) -> dict[str, Any]:
    """Assemble the frozen experiment protocol written at create time."""
    engine = {key: protocol_fingerprint[key] for key in _ENGINE_KEYS if key in protocol_fingerprint}
    scorer: dict[str, Any] = {
        "eval_metric_ids": list(protocol_fingerprint.get("eval_metric_ids") or []),
    }
    if evaluator:
        scorer["evaluator"] = dict(evaluator)
    solver: dict[str, Any] = {
        "players": players,
        "prompt_version": prompt_version,
    }
    if prompts:
        solver["prompts"] = prompts
    if thinking_budget:
        solver["thinking_budget"] = dict(thinking_budget)
    scope = (memory or "none").strip() or "none"
    if scope not in ("none", "per_experiment"):
        scope = "none"
    solver["memory"] = scope
    return {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "frozen_at": frozen_at,
        "dataset": {
            "collect_mode": collect_mode,
            "deal_seeds": list(deal_seeds),
            "pair_deals": pair_deals,
            "source_experiment_id": source_experiment_id,
        },
        "solver": solver,
        "scorer": scorer,
        "engine": engine,
    }


def validate_protocol(protocol: Any) -> dict[str, Any]:
    """Return *protocol* if it is a complete v2 Task document.

    Raises ``ValueError`` with a Chinese message suitable for validation errors.
    """
    if not isinstance(protocol, dict):
        raise ValueError("实验协议缺失或格式无效，无法开局。请新建实验。")
    version = protocol.get("schema_version")
    if version != PROTOCOL_SCHEMA_VERSION:
        raise ValueError(
            f"实验协议版本不受支持（schema_version={version!r}，"
            f"需要 {PROTOCOL_SCHEMA_VERSION}）。请新建实验。"
        )
    dataset = protocol.get("dataset")
    solver = protocol.get("solver")
    scorer = protocol.get("scorer")
    engine = protocol.get("engine")
    if not isinstance(dataset, dict):
        raise ValueError("实验协议缺少 dataset 段，无法开局。请新建实验。")
    if not isinstance(solver, dict):
        raise ValueError("实验协议缺少 solver 段，无法开局。请新建实验。")
    if not isinstance(scorer, dict):
        raise ValueError("实验协议缺少 scorer 段，无法开局。请新建实验。")
    if not isinstance(engine, dict):
        raise ValueError("实验协议缺少 engine 段，无法开局。请新建实验。")
    players = solver.get("players")
    if not isinstance(players, list) or not players:
        raise ValueError("实验协议未冻结选手配置，无法开局。请新建实验。")
    return protocol


def protocol_players(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    solver = protocol.get("solver")
    if not isinstance(solver, dict):
        return []
    players = solver.get("players")
    return list(players) if isinstance(players, list) else []


def protocol_prompt_version(protocol: dict[str, Any]) -> str:
    solver = protocol.get("solver")
    if not isinstance(solver, dict):
        return ""
    return str(solver.get("prompt_version") or "")


def protocol_prompts(protocol: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Frozen prompt bodies keyed by template_key (may be empty on older runs)."""
    if not isinstance(protocol, dict):
        return {}
    solver = protocol.get("solver")
    if not isinstance(solver, dict):
        return {}
    raw = solver.get("prompts")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, entry in raw.items():
        if isinstance(entry, dict) and entry.get("content"):
            out[str(key)] = dict(entry)
    return out


def protocol_thinking_budget(protocol: dict[str, Any] | None) -> dict[str, Any]:
    """Frozen reasoning budget from ``solver.thinking_budget`` (may be empty)."""
    if not isinstance(protocol, dict):
        return {}
    solver = protocol.get("solver")
    if not isinstance(solver, dict):
        return {}
    raw = solver.get("thinking_budget")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    effort = raw.get("reasoning_effort")
    if isinstance(effort, str) and effort.strip():
        out["reasoning_effort"] = effort.strip()
    max_tok = raw.get("max_thinking_tokens")
    if max_tok is not None:
        try:
            out["max_thinking_tokens"] = int(max_tok)
        except (TypeError, ValueError):
            pass
    return out


def protocol_memory(protocol: dict[str, Any] | None) -> str:
    """Frozen memory scope: ``none`` or ``per_experiment``."""
    if not isinstance(protocol, dict):
        return "none"
    solver = protocol.get("solver")
    if not isinstance(solver, dict):
        return "none"
    raw = str(solver.get("memory") or "none").strip() or "none"
    if raw not in ("none", "per_experiment"):
        return "none"
    return raw


def prompt_content_hash(content: str) -> str:
    import hashlib

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


def protocol_deal_seeds(protocol: dict[str, Any]) -> list[int]:
    dataset = protocol.get("dataset")
    if not isinstance(dataset, dict):
        return []
    return [int(s) for s in (dataset.get("deal_seeds") or [])]


def set_protocol_deal_seeds(protocol: dict[str, Any], seeds: list[int]) -> None:
    dataset = protocol.setdefault("dataset", {})
    if not isinstance(dataset, dict):
        protocol["dataset"] = {"deal_seeds": list(seeds)}
        return
    dataset["deal_seeds"] = list(seeds)


def protocol_pair_deals(protocol: dict[str, Any]) -> bool:
    dataset = protocol.get("dataset")
    if not isinstance(dataset, dict):
        return False
    return bool(dataset.get("pair_deals"))


def set_protocol_pair_deals(protocol: dict[str, Any], pair_deals: bool) -> None:
    dataset = protocol.setdefault("dataset", {})
    if not isinstance(dataset, dict):
        protocol["dataset"] = {"pair_deals": pair_deals}
        return
    dataset["pair_deals"] = pair_deals


def protocol_collect_mode(protocol: dict[str, Any]) -> str:
    dataset = protocol.get("dataset")
    if not isinstance(dataset, dict):
        return "free"
    return str(dataset.get("collect_mode") or "free")


def protocol_source_experiment_id(protocol: dict[str, Any]) -> str | None:
    dataset = protocol.get("dataset")
    if not isinstance(dataset, dict):
        return None
    raw = dataset.get("source_experiment_id")
    if raw is None or raw == "":
        return None
    return str(raw)


def protocol_eval_metric_ids(protocol: dict[str, Any]) -> list[str]:
    scorer = protocol.get("scorer")
    if not isinstance(scorer, dict):
        return []
    return [str(x) for x in (scorer.get("eval_metric_ids") or [])]


def protocol_evaluator(protocol: dict[str, Any]) -> dict[str, Any] | None:
    """Frozen EV knobs under ``scorer.evaluator``, or ``None`` when absent."""
    scorer = protocol.get("scorer")
    if not isinstance(scorer, dict):
        return None
    raw = scorer.get("evaluator")
    return dict(raw) if isinstance(raw, dict) else None


def protocol_engine(protocol: dict[str, Any]) -> dict[str, Any]:
    engine = protocol.get("engine")
    return dict(engine) if isinstance(engine, dict) else {}


def protocol_game_type(protocol: dict[str, Any]) -> str | None:
    engine = protocol_engine(protocol)
    raw = engine.get("game_type")
    return str(raw) if raw else None


def flatten_protocol_view(protocol: dict[str, Any] | None) -> dict[str, Any] | None:
    """Flat dict for UIs and tests that expect top-level Task fields."""
    if not isinstance(protocol, dict):
        return None
    engine = protocol_engine(protocol)
    return {
        "schema_version": protocol.get("schema_version"),
        "frozen_at": protocol.get("frozen_at"),
        "prompt_version": protocol_prompt_version(protocol),
        "prompt_hashes": {
            key: str(entry.get("content_hash") or "")
            for key, entry in protocol_prompts(protocol).items()
        },
        "players": protocol_players(protocol),
        "source_experiment_id": protocol_source_experiment_id(protocol),
        "pair_deals": protocol_pair_deals(protocol),
        "deal_seeds": protocol_deal_seeds(protocol),
        "collect_mode": protocol_collect_mode(protocol),
        "eval_metric_ids": protocol_eval_metric_ids(protocol),
        "evaluator": protocol_evaluator(protocol),
        **engine,
    }


def clamp_benchmark_collect_count(
    *,
    deal_seeds: list[int],
    start_index: int,
    count: int,
) -> int:
    """Limit a benchmark collect batch to remaining declared seeds.

    Raises ``ValueError`` when no seeds remain (caller maps to validation error).
    """
    remaining_seeds = max(0, len(deal_seeds) - start_index)
    if remaining_seeds == 0:
        raise ValueError("基准测试的固定发牌种子已用完，不能再开新对局")
    return min(count, remaining_seeds)


def pick_collect_seed(
    *,
    index: int,
    deal_seeds: list[int],
    pair_deals: bool,
    collect_mode: str,
) -> tuple[int, bool]:
    """Choose the deal seed for one collect slot.

    Mutates ``deal_seeds`` when free-mode appends a random seed (pair/compare log).
    Returns ``(seed, paired)``.
    """
    if pair_deals and index < len(deal_seeds):
        return deal_seeds[index], True
    if collect_mode == "benchmark" and index < len(deal_seeds):
        return deal_seeds[index], False

    seed = secrets.randbits(31)
    if index < len(deal_seeds):
        deal_seeds[index] = seed
    else:
        deal_seeds.append(seed)
    return seed, False
