"""Assemble a human-confirmable experiment conclusion draft (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MAX_BLUNDERS = 3

_VERDICT_CLAIM: dict[str, dict[str, str]] = {
    "zh-CN": {
        "stronger": "对照结果：本实验的{metric}更高。",
        "weaker": "对照结果：本实验的{metric}更低。",
        "even": "对照结果：两次运行的{metric}点估计相同，不代表等效。",
        "peer_pending": "对照实验尚未就绪，暂时不能下结论。",
        "no_data": "还没有足够的对局可以比较。",
    },
    "en": {
        "stronger": "Result: this run has a higher {metric}.",
        "weaker": "Result: this run has a lower {metric}.",
        "even": "Result: {metric} estimates are equal; this does not establish equivalence.",
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

    if delta is None:
        verdict_key = "no_data"
        can_conclude = False
        peer_name = ""
        paired_n = 0
        overall_diff: float | None = None
        ci = None
    else:
        verdict_key = str(delta.get("verdict_key") or "no_data")
        if verdict_key not in claims:
            verdict_key = "no_data"
        can_conclude = bool(delta.get("can_conclude"))
        peer_name = str(delta.get("peer_name") or "")
        paired_n = int(delta.get("paired_n") or 0)
        raw_diff = delta.get("win_rate_diff")
        overall_diff = float(raw_diff) if raw_diff is not None else None
        ci = delta.get("this_win_rate_ci")

    lines: list[str] = []
    if loc == "en":
        lines.append("[Draft · pending confirmation]")
    else:
        lines.append("【草稿 · 待确认】")

    hypothesis = str(
        (delta or {}).get("design_hypothesis") or experiment.get("hypothesis") or ""
    ).strip()
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

    metric = "table landlord win rate" if loc == "en" else "全桌地主胜率"
    if delta:
        players = ((experiment.get("protocol") or {}).get("solver") or {}).get("players", [])
        names = {p["id"]: f"#{i} {p.get('name') or p['id']}" for i, p in enumerate(players, 1)}
        primary = delta["primary_metric"]
        if primary["kind"] == "seat_team_win_rate":
            pid = primary["player_id"]
            seat = names.get(pid, pid)
            metric = f"team win rate for {seat}" if loc == "en" else f"「{seat}」所在阵营胜率"
        counts = delta["outcome_counts"]
        excluded = delta["paired_excluded_n"]
        purpose = {
            "development": ("调试用牌", "Development deals"),
            "holdout": ("独立验证用牌", "Independent holdout deals"),
            "mixed": ("跨发牌计划的探索性比较", "Exploratory comparison across plans"),
        }[delta["deal_purpose"]][1 if loc == "en" else 0]
        a, b = (peer_name, name) if delta["relation"] == "vs_source" else (name, peer_name)
        if loc == "en":
            lines.append(
                f"{purpose}. Shared plan {paired_n + excluded}, valid pairs {paired_n}, excluded {excluded}."
            )
            lines.append(
                f"A = {a}, B = {b}. Both won {counts['both_won']}, only A won {counts['a_only_won']}, only B won {counts['b_only_won']}, both lost {counts['both_lost']}."
            )
        else:
            lines.append(
                f"{purpose}。共同计划 {paired_n + excluded} 副，配对有效 {paired_n} 副，未纳入 {excluded} 副。"
            )
            lines.append(
                f"A = {a}，B = {b}。均胜 {counts['both_won']}，仅 A 胜 {counts['a_only_won']}，仅 B 胜 {counts['b_only_won']}，均负 {counts['both_lost']}。"
            )
        affected = delta["affected_player_ids"]
        if affected:
            seats = ", ".join(names.get(pid, pid) for pid in affected)
            lines.append(
                f"Seats using the changed prompt: {seats}."
                if loc == "en"
                else f"使用变更提示词的席位：{seats}。"
            )
        if len(affected) > 1 and primary["kind"] == "seat_team_win_rate":
            lines.append(
                "This seat was observed under a shared prompt change."
                if loc == "en"
                else "该席位的结果是在多个席位共同更换提示词的条件下观察到的。"
            )

    claim = claims[verdict_key].format(metric=metric)
    if not can_conclude and verdict_key in {"stronger", "weaker", "even"}:
        if loc == "en":
            lines.append(f"Evidence is still thin; provisional read — {claim}")
        else:
            lines.append(f"证据仍不足，暂见——{claim}")
    else:
        lines.append(claim)

    reason = delta.get("inconclusive_reason") if delta else None
    if reason == "uncertain_difference":
        lines.append(
            "Paired evidence does not support a clear difference; equivalence is not established."
            if loc == "en"
            else "配对证据尚不支持明确差异，也不代表两者等效。"
        )
    elif reason == "incomplete_holdout":
        lines.append(
            "Only part of the holdout plan has valid results."
            if loc == "en"
            else "独立验证计划仅部分发牌有有效结果。"
        )
    elif reason == "missing_paired_evidence":
        lines.append(
            "Complete paired statistics are missing." if loc == "en" else "缺少完整的配对统计证据。"
        )
    elif reason == "protocol_mismatch":
        lines.append(
            "Protocol review did not establish a controlled comparison."
            if loc == "en"
            else "协议审查未确认受控比较条件成立。"
        )
    if delta and delta["deal_purpose"] == "holdout":
        lines.append(
            "The holdout estimate applies to the frozen seats, prompts and evaluator."
            if loc == "en"
            else "验证结果的解释范围限于冻结的席位、提示词和评估条件。"
        )
    else:
        lines.append(
            "Exploratory assessment within these conditions only."
            if loc == "en"
            else "这是本次条件下的探索性判断。"
        )

    if overall_diff is not None:
        delta_pp = f"{overall_diff * 100:+.1f} pp"
        if loc == "en":
            num = f"Δ {metric} {delta_pp}; paired n = {paired_n}"
        else:
            num = f"{metric} Δ {delta_pp}；配对局数 n = {paired_n}"
        if isinstance(ci, (list, tuple)) and len(ci) >= 2:
            lo, hi = float(ci[0]), float(ci[1])
            if loc == "en":
                num += f"; this-run CI [{lo:.1%}, {hi:.1%}]"
            else:
                num += f"；本实验 CI [{lo:.1%}, {hi:.1%}]"
        if delta and delta["difference_basis"] == "unpaired":
            num += " (unpaired full runs)" if loc == "en" else "（两组全量决胜局的未配对描述）"
        lines.append(num)
        paired_ci = delta.get("paired_ci") if delta else None
        if isinstance(paired_ci, (list, tuple)) and len(paired_ci) == 2:
            lo, hi = float(paired_ci[0]) * 100, float(paired_ci[1]) * 100
            label = (
                "Conservative 95% paired difference interval"
                if loc == "en"
                else "配对差值的保守 95% 区间"
            )
            lines.append(f"{label}: [{lo:+.1f}, {hi:+.1f}] pp")

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
                f"- game={game_id} round={round_number} action={action_id} ev_loss={loss_s}"
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
]
