"""Assemble a human-confirmable experiment conclusion draft (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Match ExperimentScenarioBars NOTABLE_DIFF.
_SCENARIO_NOTABLE = 0.05
_MAX_BLUNDERS = 3

_SCENARIO_LABELS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "bidding": "叫分",
        "playing": "出牌",
        "endgame": "残局",
        "bomb": "炸弹",
    },
    "en": {
        "bidding": "bidding",
        "playing": "playing",
        "endgame": "endgame",
        "bomb": "bomb",
    },
}

_VERDICT_CLAIM: dict[str, dict[str, str]] = {
    "zh-CN": {
        "stronger": "对照结果：本实验当地主时赢得更多。",
        "weaker": "对照结果：本实验当地主时赢得更少。",
        "even": "对照结果：两次运行的地主胜率没有明显差别。",
        "peer_pending": "对照实验尚未就绪，暂时不能下结论。",
        "no_data": "还没有足够的对局可以比较。",
    },
    "en": {
        "stronger": "Result: this run wins more often as landlord.",
        "weaker": "Result: this run wins less often as landlord.",
        "even": "Result: landlord win rates look even across the two runs.",
        "peer_pending": "The peer run is not ready yet; no conclusion yet.",
        "no_data": "Not enough games to compare.",
    },
}


@dataclass(frozen=True)
class ConclusionDraft:
    """Payload returned to API / UI before the user confirms a write."""

    text: str
    locale: str
    verdict_key: str
    can_conclude: bool
    blunder_ids: list[str]


def normalize_draft_locale(raw: str | None) -> str:
    """Map Accept-Language / query crumbs to ``zh-CN`` or ``en``."""
    if not raw:
        return "zh-CN"
    primary = raw.split(",")[0].strip().lower().replace("_", "-")
    if primary.startswith("en"):
        return "en"
    return "zh-CN"


def pick_notable_scenario(
    scenario_diffs: dict[str, Any] | None,
    *,
    threshold: float = _SCENARIO_NOTABLE,
) -> tuple[str, float] | None:
    """Largest |train_usable_rate_diff| above threshold, if any."""
    if not isinstance(scenario_diffs, dict):
        return None
    best_id: str | None = None
    best_abs = 0.0
    best_val = 0.0
    for sid, bucket in scenario_diffs.items():
        if not isinstance(bucket, dict):
            continue
        raw = bucket.get("train_usable_rate_diff")
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        magnitude = abs(value)
        if magnitude < threshold:
            continue
        if magnitude > best_abs:
            best_abs = magnitude
            best_val = value
            best_id = str(sid)
    if best_id is None:
        return None
    return best_id, best_val


def build_conclusion_draft(
    *,
    experiment: dict[str, Any],
    delta: dict[str, Any] | None,
    blunders: list[dict[str, Any]],
    locale: str = "zh-CN",
) -> ConclusionDraft:
    """Build a plain-text conclusion draft from stored eval signals."""
    loc = normalize_draft_locale(locale)
    claims = _VERDICT_CLAIM[loc]
    scenario_labels = _SCENARIO_LABELS[loc]

    if delta is None:
        verdict_key = "no_data"
        can_conclude = False
        peer_name = ""
        paired_n = 0
        overall_diff: float | None = None
        ci = None
        scenario_diffs: dict[str, Any] | None = None
    else:
        verdict_key = str(delta.get("verdict_key") or "no_data")
        if verdict_key not in claims:
            verdict_key = "no_data"
        can_conclude = bool(delta.get("can_conclude"))
        peer_name = str(delta.get("peer_name") or "")
        paired_n = int(delta.get("paired_n") or 0)
        raw_diff = delta.get("landlord_win_rate_diff")
        overall_diff = float(raw_diff) if raw_diff is not None else None
        ci = delta.get("this_landlord_win_rate_ci")
        scenario_diffs = (
            delta.get("scenario_diffs")
            if isinstance(delta.get("scenario_diffs"), dict)
            else None
        )

    lines: list[str] = []
    if loc == "en":
        lines.append("[Draft · pending confirmation]")
    else:
        lines.append("【草稿 · 待确认】")

    hypothesis = str(experiment.get("hypothesis") or "").strip()
    if hypothesis:
        if loc == "en":
            lines.append(f"Hypothesis: {hypothesis}")
        else:
            lines.append(f"对照假设：{hypothesis}")

    name = str(experiment.get("name") or "").strip()
    if peer_name:
        if loc == "en":
            lines.append(f"Comparing “{name}” vs “{peer_name}”.")
        else:
            lines.append(f"对照：“{name}” vs “{peer_name}”。")

    claim = claims[verdict_key]
    if not can_conclude and verdict_key in {"stronger", "weaker", "even"}:
        if loc == "en":
            lines.append(f"Evidence is still thin; provisional read — {claim}")
        else:
            lines.append(f"证据仍不足，暂见——{claim}")
    else:
        lines.append(claim)

    if overall_diff is not None:
        delta_pp = f"{overall_diff * 100:+.1f} pp"
        if loc == "en":
            num = f"Δ landlord win rate {delta_pp}; paired n = {paired_n}"
        else:
            num = f"地主胜率 Δ {delta_pp}；配对局数 n = {paired_n}"
        if isinstance(ci, (list, tuple)) and len(ci) >= 2:
            lo, hi = float(ci[0]), float(ci[1])
            if loc == "en":
                num += f"; this-run CI [{lo:.1%}, {hi:.1%}]"
            else:
                num += f"；本实验 CI [{lo:.1%}, {hi:.1%}]"
        lines.append(num)

    notable = pick_notable_scenario(scenario_diffs)
    if notable is not None:
        sid, value = notable
        label = scenario_labels.get(sid, sid)
        gap = f"{value * 100:+.1f} pp"
        if loc == "en":
            lines.append(f"Notable scenario gap ({label} train-usable): {gap}.")
        else:
            lines.append(f"场景缺口（{label} 可训练率）：{gap}。")

    top = blunders[:_MAX_BLUNDERS]
    blunder_ids: list[str] = []
    if top:
        if loc == "en":
            lines.append("High EV-loss moves (sample):")
        else:
            lines.append("高 EV loss 着法（抽样）：")
        for item in top:
            did = str(item.get("id") or "")
            if did:
                blunder_ids.append(did)
            game_id = str(item.get("game_id") or "?")
            round_number = item.get("round_number")
            action_id = str(item.get("action_id") or "?")
            loss = item.get("ev_loss")
            loss_s = f"{float(loss):.2f}" if loss is not None else "?"
            lines.append(
                f"- game={game_id} round={round_number} "
                f"action={action_id} ev_loss={loss_s}"
            )

    text = "\n".join(lines).strip() + "\n"
    return ConclusionDraft(
        text=text,
        locale=loc,
        verdict_key=verdict_key,
        can_conclude=can_conclude,
        blunder_ids=blunder_ids,
    )


__all__ = [
    "ConclusionDraft",
    "build_conclusion_draft",
    "normalize_draft_locale",
    "pick_notable_scenario",
]
