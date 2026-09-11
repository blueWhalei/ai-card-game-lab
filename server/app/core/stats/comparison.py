"""Deterministic paired cohorts and frozen-protocol review (no I/O)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def seed_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    return None


def paired_cohort(
    rows: list[dict[str, Any]], games: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, Any], dict[str, dict[int, dict[str, Any]]]]:
    plans: list[set[int]] = []
    indexes: dict[str, dict[int, dict[str, Any]]] = {}
    coverage: list[dict[str, Any]] = []
    for row in rows:
        protocol = row.get("protocol") or {}
        dataset = protocol.get("dataset") or {}
        plan = [s for raw in dataset.get("deal_seeds", []) if (s := seed_value(raw)) is not None]
        plans.append(set(plan))
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        missing_seed = 0
        for game in games.get(str(row["id"]), []):
            seed = seed_value((game.get("metadata") or {}).get("deal_seed"))
            if seed is None:
                missing_seed += 1
            else:
                grouped[seed].append(game)
        valid: dict[int, dict[str, Any]] = {}
        reasons: Counter[str] = Counter()
        conflicts = []
        duplicate_plan = {s for s, n in Counter(plan).items() if n > 1}
        for seed in sorted(set(plan)):
            candidates = grouped.get(seed, [])
            if len(candidates) > 1 or seed in duplicate_plan:
                reasons["duplicate"] += 1
                conflicts.append(
                    {"seed": seed, "game_ids": sorted(str(g["id"]) for g in candidates)}
                )
            elif not candidates:
                reasons["missing"] += 1
            else:
                game = candidates[0]
                if game.get("status") != "finished":
                    reasons["unfinished"] += 1
                elif not game.get("winner_id") or game.get("winner_role") not in (
                    "landlord",
                    "peasant",
                ):
                    reasons["invalid_outcome"] += 1
                elif row.get("player_ids") and (
                    game.get("player_ids") != row["player_ids"]
                    or game.get("winner_id") not in row["player_ids"]
                ):
                    reasons["seat_mismatch"] += 1
                else:
                    valid[seed] = game
        indexes[str(row["id"])] = valid
        coverage.append(
            {
                "experiment_id": row["id"],
                "planned": len(set(plan)),
                "valid": len(valid),
                "excluded": dict(reasons),
                "conflicts": conflicts,
                "missing_seed_games": missing_seed,
                "unplanned_games": sum(len(v) for k, v in grouped.items() if k not in set(plan)),
            }
        )
    common_plan = set.intersection(*plans) if plans else set()
    effective = common_plan.intersection(*(set(i) for i in indexes.values()))
    for item in coverage:
        item["not_shared"] = item["valid"] - len(effective)
    return {
        "unit": "deal_seed_fixed_seats",
        "planned_shared": len(common_plan),
        "effective_n": len(effective),
        "effective_seeds": sorted(effective),
        "members": [
            {"seed": seed, "game_ids": {eid: index[seed]["id"] for eid, index in indexes.items()}}
            for seed in sorted(effective)
        ],
        "experiments": coverage,
    }, indexes


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict) and value:
        return {
            path: leaf
            for key in sorted(value)
            for path, leaf in _flatten(value[key], f"{prefix}.{key}" if prefix else key).items()
        }
    if isinstance(value, list) and value and prefix == "solver.players":
        return {
            path: leaf
            for i, player in enumerate(value)
            for path, leaf in _flatten(player, f"{prefix}.{i}").items()
        }
    return {prefix: value}


def change_allowed(path: str) -> bool:
    parts = path.split(".")
    return path.startswith(("solver.prompts.", "solver.thinking_budget.")) or (
        len(parts) >= 4
        and parts[:2] == ["solver", "players"]
        and parts[2].isdigit()
        and (
            (parts[3] == "policy_kind" and len(parts) == 4)
            or (parts[3] == "model_config" and len(parts) > 4)
        )
    )


def protocol_review(rows: list[dict[str, Any]], allowed: list[str]) -> dict[str, Any]:
    normalized = []
    unknown = []
    for row in rows:
        p = row.get("protocol") or {}
        missing = []
        if p.get("schema_version") != 2:
            missing.append("schema_version")
        for section, keys in {
            "engine": [
                "game_type",
                "engine_version",
                "decision_schema_version",
                "rules_ref",
                "roles",
                "prompt_keys",
                "supports_deal_seed",
            ],
            "solver": ["players", "prompts", "thinking_budget", "memory"],
            "scorer": ["evaluator", "eval_metric_ids"],
            "dataset": ["deal_seeds"],
        }.items():
            obj = p.get(section) or {}
            for key in keys:
                if (
                    key not in obj
                    or obj[key] is None
                    or (key in ("players", "prompts", "evaluator") and not obj[key])
                ):
                    missing.append(f"{section}.{key}")
        players = (p.get("solver") or {}).get("players") or []
        if len(players) != len(row.get("player_ids") or []):
            missing.append("solver.players.seat_count")
        if [player.get("id") for player in players] != (row.get("player_ids") or []):
            missing.append("solver.players.seat_identity")
        for i, player in enumerate(players):
            if "policy_kind" not in player or "model_config" not in player:
                missing.append(f"solver.players.{i}")
        solver = {k: v for k, v in (p.get("solver") or {}).items() if k != "prompt_version"}
        solver["players"] = [
            {k: v for k, v in player.items() if k not in ("id", "name", "notes")}
            for player in players
        ]
        normalized.append(
            _flatten(
                {
                    "engine": p.get("engine"),
                    "solver": solver,
                    "scorer": p.get("scorer"),
                    "dataset": {"deal_seeds": (p.get("dataset") or {}).get("deal_seeds")},
                }
            )
        )
        if missing:
            unknown.append({"experiment_id": row["id"], "fields": missing})
    differences = []
    baseline = normalized[0] if normalized else {}
    for row, current in zip(rows[1:], normalized[1:], strict=True):
        for path in sorted(baseline.keys() | current.keys()):
            if path not in baseline or path not in current or baseline[path] != current[path]:
                differences.append(
                    {
                        "experiment_id": row["id"],
                        "path": path,
                        "baseline": baseline.get(path),
                        "variant": current.get(path),
                        "baseline_missing": path not in baseline,
                        "variant_missing": path not in current,
                        "allowable": change_allowed(path) and path in baseline and path in current,
                        "declared": path in allowed
                        and change_allowed(path)
                        and path in baseline
                        and path in current,
                    }
                )
    reasons = []
    if len(rows) != 2:
        reasons.append("exploratory")
    target_seats = {
        d["path"].split(".")[2]
        for d in differences
        if d["path"].startswith("solver.players.")
        and not d["baseline_missing"]
        and not d["variant_missing"]
    }
    if len(target_seats) > 1:
        reasons.append("multiple_target_seats")
    if any(
        (r.get("protocol") or {}).get("engine", {}).get("supports_deal_seed") is False for r in rows
    ):
        reasons.append("unsupported_seeds")
    if unknown:
        reasons.append("unknown_protocol")
    if any(not d["declared"] for d in differences):
        reasons.append("undeclared_changes")
    if any(
        (r.get("protocol") or {}).get("solver", {}).get("memory") == "per_experiment" for r in rows
    ):
        reasons.append("dependent_memory")
    if any(
        (r.get("protocol") or {}).get("engine", {}).get("game_type", r.get("game_type", "doudizhu"))
        != "doudizhu"
        for r in rows
    ):
        reasons.append("unsupported_metric")
    return {
        "baseline_id": rows[0]["id"] if rows else None,
        "allowed_changes": sorted(set(allowed)),
        "differences": differences,
        "unknown": unknown,
        "reasons": reasons,
        "controlled": not reasons,
    }
