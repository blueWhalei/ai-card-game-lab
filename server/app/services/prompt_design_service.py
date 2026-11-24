"""Design a single prompt change without re-snapshotting live configuration."""

from __future__ import annotations

import secrets
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from app.core.engine.registry import GameEngineRegistry
from app.core.research.prompt_design import affected_player_ids, baseline_fingerprint
from app.core.stats.comparison import protocol_review
from app.core.task_protocol import prompt_content_hash, validate_runtime_protocol
from app.repositories.comparison_repo import ComparisonRepository
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.prompt_repo import PromptRepository
from app.repositories.research_repo import ResearchRepository
from app.schemas.experiment import CreatePromptVariantRequest
from app.services.experiment_errors import ExperimentNotFoundError, ExperimentValidationError
from app.utils.exceptions import AppError
from app.utils.id_generator import generate_id


async def _source(db: aiosqlite.Connection, experiment_id: str) -> dict[str, Any]:
    try:
        return await ExperimentRepository(db).get_by_id(experiment_id)
    except KeyError as exc:
        raise ExperimentNotFoundError(experiment_id) from exc


def design_issues(source: dict[str, Any], registry: GameEngineRegistry) -> list[str]:
    p = source.get("protocol") or {}
    dataset = p.get("dataset") or {}
    solver = p.get("solver") or {}
    issues = []
    try:
        validate_runtime_protocol(p, registry)
    except ValueError:
        issues.append("runtime_protocol_required")
    if dataset.get("holdout_for"):
        issues.append("holdout_locked")
    if not source.get("study_id"):
        issues.append("study_required")
    if source.get("game_type") != "doudizhu":
        issues.append("doudizhu_required")
    seeds = dataset.get("deal_seeds") or []
    if (
        dataset.get("collect_mode") != "benchmark"
        or not seeds
        or any(type(seed) is not int for seed in seeds)
        or len(set(seeds)) != len(seeds)
        or len(seeds) != source.get("target_games")
    ):
        issues.append("fixed_plan_required")
    review = protocol_review([source, source], [])
    if review["unknown"] or (p.get("engine") or {}).get("supports_deal_seed") is not True:
        issues.append("complete_protocol_required")
    if solver.get("memory") != "none":
        issues.append("independent_games_required")
    if not affected_player_ids(p):
        issues.append("model_player_required")
    prompts = solver.get("prompts") or {}
    keys = set((p.get("engine") or {}).get("prompt_keys", {}).values())
    if not keys or any(
        not isinstance(prompts.get(key), dict)
        or not isinstance(prompts[key].get("content"), str)
        or not isinstance(prompts[key].get("version"), str)
        or not prompts[key]["version"].strip()
        or not prompts[key]["content"].strip()
        or prompts[key].get("content_hash") != prompt_content_hash(prompts[key]["content"])
        for key in keys
    ):
        issues.append("frozen_prompts_required")
    return issues


async def _source_conclusion(
    db: aiosqlite.Connection, source: dict[str, Any], revision_id: str | None
) -> tuple[dict[str, Any] | None, list[str]]:
    if revision_id is None:
        return None, []
    try:
        record = await ResearchRepository(db).get(revision_id)
        comparison = await ComparisonRepository(db).get(record["comparison_id"])
    except KeyError as exc:
        raise AppError("Source conclusion not found", "RESEARCH_NOT_FOUND", 404) from exc
    members = [row for row in comparison["result"]["experiments"] if row["id"] == source["id"]]
    issues = []
    if len(members) != 1:
        issues.append("source_run_not_member")
    elif any(
        source.get(key) != members[0].get(key) for key in ("game_type", "player_ids", "protocol")
    ):
        issues.append("source_conditions_changed")
    return {
        key: record[key]
        for key in (
            "id",
            "comparison_id",
            "revision",
            "created_at",
            "observations",
            "interpretation",
            "limitations",
        )
    }, issues


async def preview_design(
    db: aiosqlite.Connection,
    experiment_id: str,
    registry: GameEngineRegistry,
    source_revision_id: str | None = None,
) -> dict[str, Any]:
    source = await _source(db, experiment_id)
    conclusion, source_issues = await _source_conclusion(db, source, source_revision_id)
    keys = ((source.get("protocol") or {}).get("engine") or {}).get("prompt_keys", {})
    templates = await PromptRepository(db).list_templates(active_only=False)
    return {
        "baseline": source,
        "fingerprint": baseline_fingerprint(source),
        "affected_player_ids": affected_player_ids(source.get("protocol") or {}),
        "issues": design_issues(source, registry) + source_issues,
        "source_conclusion": conclusion,
        "options": [
            {
                "template_key": item.template_key,
                "version": item.version,
                "content": item.content,
                "content_hash": prompt_content_hash(item.content),
            }
            for item in templates
            if item.template_key in keys.values()
        ],
    }


async def create_variant(
    db: aiosqlite.Connection,
    experiment_id: str,
    body: CreatePromptVariantRequest,
    registry: GameEngineRegistry,
) -> str:
    await db.execute("BEGIN IMMEDIATE")
    source = await _source(db, experiment_id)
    if (
        source.get("study_id") != body.study_id
        or baseline_fingerprint(source) != body.baseline_fingerprint
    ):
        raise AppError("Baseline changed; review the design again", "PROMPT_DESIGN_CONFLICT", 409)
    if design_issues(source, registry):
        raise ExperimentValidationError("基线不满足 Prompt A/B 条件，请重新核对设计")
    _, source_issues = await _source_conclusion(db, source, body.source_revision_id)
    if source_issues:
        raise AppError(
            "Source conclusion and baseline conditions do not match",
            "PROMPT_DESIGN_SOURCE_CONFLICT",
            409,
        )
    template = await PromptRepository(db).get_template(body.template_key, body.version)
    if template is None or prompt_content_hash(template.content) != body.content_hash:
        raise AppError("Prompt changed; review the design again", "PROMPT_DESIGN_CONFLICT", 409)
    if not template.content.strip():
        raise ExperimentValidationError("提示词正文不能为空")
    protocol = deepcopy(source["protocol"])
    if body.template_key not in protocol["engine"]["prompt_keys"].values():
        raise ExperimentValidationError("只能替换基线使用的提示词阶段")
    affected = affected_player_ids(protocol)
    metric = body.primary_metric
    if metric.kind == "seat_team_win_rate" and metric.player_id not in affected:
        raise ExperimentValidationError("指定选手必须属于使用该阶段提示词的冻结席位")
    previous = protocol["solver"]["prompts"][body.template_key]
    if previous["content"] == template.content:
        raise ExperimentValidationError("提示词正文未改变，请选择不同内容的版本")
    now = datetime.now(UTC).isoformat()
    protocol["solver"]["prompts"][body.template_key] = {
        "version": template.version,
        "content": template.content,
        "content_hash": body.content_hash,
    }
    protocol["frozen_at"] = now
    protocol["dataset"].update(source_experiment_id=experiment_id, pair_deals=True)
    protocol["design"] = {
        "kind": "prompt_ab",
        "baseline_id": experiment_id,
        "template_key": body.template_key,
        "baseline_hash": previous["content_hash"],
        "variant_hash": body.content_hash,
        "hypothesis": body.hypothesis.strip(),
        "primary_metric": metric.model_dump(),
        "affected_player_ids": affected,
        "created_at": now,
    }
    if body.source_revision_id is not None:
        protocol["design"]["source_revision_id"] = body.source_revision_id
    new_id = generate_id("exp")
    await _insert_frozen_run(
        ExperimentRepository(db),
        source,
        protocol,
        new_id,
        body.name.strip(),
        now,
        body.hypothesis.strip(),
    )
    await db.commit()
    return new_id


async def _insert_frozen_run(
    repo: ExperimentRepository,
    source: dict[str, Any],
    protocol: dict[str, Any],
    experiment_id: str,
    name: str,
    now: str,
    hypothesis: str,
) -> None:
    await repo.create(
        experiment_id=experiment_id,
        study_id=source["study_id"],
        name=name,
        notes="",
        game_type=source["game_type"],
        player_ids=source["player_ids"],
        target_games=source["target_games"],
        created_at=now,
        updated_at=now,
        protocol=protocol,
        hypothesis=hypothesis,
        tags=source.get("tags") or [],
        commit=False,
    )


async def reserve_holdout(
    db: aiosqlite.Connection, variant_id: str, registry: GameEngineRegistry
) -> dict[str, str]:
    """Reserve one fresh plan for both frozen arms. A retry opens the same pair."""
    await db.execute("BEGIN IMMEDIATE")
    repo = ExperimentRepository(db)
    variant = await _source(db, variant_id)
    original = variant.get("protocol") or {}
    design = original.get("design") or {}
    if design.get("kind") != "prompt_ab" or original["dataset"].get("holdout_for"):
        raise ExperimentValidationError("请从调试用牌上的冻结 Prompt A/B 设计创建验证组")
    existing = await repo.holdout_runs(variant_id)
    if existing:
        for row in existing:
            if len(existing) == 2 and any(r["id"] == row["baseline_id"] for r in existing):
                return {"baseline_id": row["baseline_id"], "variant_id": row["id"]}
        raise ExperimentValidationError("独立验证组记录不完整，不能重新抽牌")

    baseline = await _source(db, design["baseline_id"])
    review = protocol_review([baseline, variant], [])
    if (
        design_issues(baseline, registry)
        or design_issues(variant, registry)
        or not review["controlled"]
        or not review.get("design_changes")
        or baseline["study_id"] != variant["study_id"]
        or baseline["player_ids"] != variant["player_ids"]
    ):
        raise ExperimentValidationError("冻结的 A/B 条件不匹配，无法生成独立验证组")

    used = await repo.reserved_deal_seeds()
    seeds: list[int] = []
    while len(seeds) < variant["target_games"]:
        # Separate from public benchmark and 31-bit free draws; exact in JS and SQLite.
        candidate = (1 << 40) | secrets.randbits(40)
        if candidate not in used:
            seeds.append(candidate)
            used.add(candidate)
    now = datetime.now(UTC).isoformat()
    a_id, b_id = generate_id("exp"), generate_id("exp")
    for source, new_id, arm in ((baseline, a_id, "A"), (variant, b_id, "B")):
        protocol = deepcopy(source["protocol"])
        protocol["frozen_at"] = now
        protocol["dataset"].update(
            deal_seeds=seeds,
            holdout_for=variant_id,
            source_experiment_id=a_id if arm == "B" else None,
            pair_deals=arm == "B",
        )
        if arm == "B":
            protocol["design"].update(baseline_id=a_id, created_at=now)
        else:
            protocol.pop("design", None)
        await _insert_frozen_run(
            repo,
            source,
            protocol,
            new_id,
            f"{source['name'][:110]} · {arm}′",
            now,
            design["hypothesis"],
        )
    await db.commit()
    return {"baseline_id": a_id, "variant_id": b_id}
