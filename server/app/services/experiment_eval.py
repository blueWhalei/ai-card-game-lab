"""Pure eval helpers for experiment detail (credibility, delta, verdict)."""

from __future__ import annotations

import math
from typing import Any

from app.core.stats.scenarios import scenario_rate_diffs

_CREDIBILITY_MIN_DECISIVE_N = 20
_CREDIBILITY_MAX_CI_WIDTH = 0.3

# Re-exported for paired-summary low_power checks in ExperimentService.
CREDIBILITY_MIN_DECISIVE_N = _CREDIBILITY_MIN_DECISIVE_N


def build_credibility(
    *,
    decisive_n: int,
    win_rate_ci: list[float] | tuple[float, float] | None,
) -> dict[str, Any]:
    """Sample-size/interval-width warning; this does not estimate statistical power."""
    width: float | None = None
    if win_rate_ci is not None and len(win_rate_ci) >= 2:
        width = round(float(win_rate_ci[1]) - float(win_rate_ci[0]), 4)
    low_power = decisive_n < _CREDIBILITY_MIN_DECISIVE_N or (
        width is not None and width > _CREDIBILITY_MAX_CI_WIDTH
    )
    return {
        "decisive_n": decisive_n,
        "win_rate_ci_width": width,
        "low_power": low_power,
    }


def ci_pair(raw: Any) -> list[float] | None:
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return None
    return [round(float(raw[0]), 4), round(float(raw[1]), 4)]


def resolve_delta_peer(
    experiment: dict[str, Any],
    validation: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Pick the experiment to diff against: source (if this is a control) or first control."""
    from app.core.task_protocol import protocol_source_experiment_id

    protocol = experiment.get("protocol") or {}
    source_id = protocol_source_experiment_id(protocol) if isinstance(protocol, dict) else None
    if source_id:
        return str(source_id), "vs_source"
    progress = list(validation.get("control_progress") or [])
    if progress:
        ready = next((item for item in progress if item.get("ready")), None)
        chosen = ready or progress[0]
        return str(chosen["id"]), "vs_control"
    control_ids = list(validation.get("control_experiment_ids") or [])
    if control_ids:
        return str(control_ids[0]), "vs_control"
    return None, None


def verdict_key(
    *,
    overall_diff: float | None,
    inconclusive_reason: str | None,
) -> str:
    """
    Plain-language claim the UI renders as one sentence (`stage.verdict.<key>`).

    Returned here rather than assembled in the frontend so an eval-formula
    change and its wording stay in one place.
    """
    if inconclusive_reason == "no_games":
        return "no_data"
    if inconclusive_reason == "peer_not_ready":
        return "peer_pending"
    if overall_diff is None:
        return "no_data"
    if overall_diff == 0:
        return "even"
    return "stronger" if overall_diff > 0 else "weaker"


def build_experiment_delta(
    *,
    peer_id: str,
    peer_name: str,
    relation: str,
    peer_ready: bool,
    primary_metric: dict[str, Any],
    affected_player_ids: list[str],
    design_hypothesis: str | None,
    this_win_rate: float | None,
    peer_win_rate: float | None,
    this_win_rate_ci: list[float] | None,
    peer_win_rate_ci: list[float] | None,
    this_decisive_n: int,
    peer_decisive_n: int,
    this_low_power: bool,
    peer_low_power: bool,
    paired_n: int,
    win_rate_diff: float | None,
    paired_low_power: bool,
    paired_p: float | None = None,
    paired_ci: list[float] | None = None,
    scenario_diffs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One-screen verdict vs a source or control experiment (this minus peer)."""
    low_power = this_low_power or peer_low_power or paired_low_power
    if this_decisive_n <= 0 or peer_decisive_n <= 0:
        inconclusive_reason: str | None = "no_games"
    elif not peer_ready:
        inconclusive_reason = "peer_not_ready"
    elif low_power:
        inconclusive_reason = "low_power"
    elif (
        paired_n <= 0
        or win_rate_diff is None
        or paired_ci is None
        or len(paired_ci) != 2
        or not all(math.isfinite(v) for v in paired_ci)
        or not -1 <= paired_ci[0] <= paired_ci[1] <= 1
        or paired_p is None
        or not math.isfinite(paired_p)
        or not 0 <= paired_p <= 1
    ):
        inconclusive_reason = "missing_paired_evidence"
    elif not (
        paired_p < 0.05
        and ((paired_ci[0] > 0 and win_rate_diff > 0) or (paired_ci[1] < 0 and win_rate_diff < 0))
    ):
        inconclusive_reason = "uncertain_difference"
    else:
        inconclusive_reason = None

    difference_basis = "paired" if win_rate_diff is not None else None
    if (
        win_rate_diff is None
        and design_hypothesis is None
        and this_win_rate is not None
        and peer_win_rate is not None
    ):
        # Free comparisons can still describe the two full runs without paired evidence.
        win_rate_diff = round(this_win_rate - peer_win_rate, 4)
        difference_basis = "unpaired"

    return {
        "difference_basis": difference_basis,
        "design_hypothesis": design_hypothesis,
        "peer_id": peer_id,
        "peer_name": peer_name,
        "relation": relation,
        "peer_ready": peer_ready,
        "primary_metric": primary_metric,
        "affected_player_ids": affected_player_ids,
        "this_win_rate": this_win_rate,
        "peer_win_rate": peer_win_rate,
        "this_win_rate_ci": this_win_rate_ci,
        "peer_win_rate_ci": peer_win_rate_ci,
        "this_decisive_n": this_decisive_n,
        "peer_decisive_n": peer_decisive_n,
        "paired_n": paired_n,
        "win_rate_diff": win_rate_diff,
        "paired_p": paired_p,
        "paired_ci": paired_ci,
        "low_power": low_power,
        "can_conclude": inconclusive_reason is None and win_rate_diff is not None,
        "inconclusive_reason": inconclusive_reason,
        "verdict_key": verdict_key(
            overall_diff=win_rate_diff,
            inconclusive_reason=inconclusive_reason,
        ),
        "scenario_diffs": scenario_diffs or scenario_rate_diffs(None, None),
    }


def derive_experiment_status(
    *,
    target_games: int,
    total_games: int,
    active_games: int,
    finished_games: int,
) -> str:
    """Derive UI status from game rows (not persisted)."""
    if total_games == 0:
        return "pending_collect"
    if active_games > 0:
        return "collecting"
    if finished_games >= target_games:
        return "ready_review"
    return "ready_more"
