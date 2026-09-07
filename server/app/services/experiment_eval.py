"""Pure eval helpers for experiment detail (credibility, delta, verdict)."""

from __future__ import annotations

from typing import Any

from app.core.stats.scenarios import scenario_rate_diffs

_CREDIBILITY_MIN_DECISIVE_N = 20
_CREDIBILITY_MAX_CI_WIDTH = 0.3

# Re-exported for paired-summary low_power checks in ExperimentService.
CREDIBILITY_MIN_DECISIVE_N = _CREDIBILITY_MIN_DECISIVE_N

"""Below this absolute landlord win-rate gap the two runs are called a tie."""
VERDICT_EVEN_THRESHOLD = 0.02


def build_credibility(
    *,
    decisive_n: int,
    landlord_win_rate_ci: list[float] | tuple[float, float] | None,
) -> dict[str, Any]:
    """Eval-power hint for UI (point estimates alone are easy to over-read)."""
    width: float | None = None
    if landlord_win_rate_ci is not None and len(landlord_win_rate_ci) >= 2:
        width = round(float(landlord_win_rate_ci[1]) - float(landlord_win_rate_ci[0]), 4)
    low_power = decisive_n < _CREDIBILITY_MIN_DECISIVE_N or (
        width is not None and width > _CREDIBILITY_MAX_CI_WIDTH
    )
    return {
        "decisive_n": decisive_n,
        "landlord_ci_width": width,
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
    protocol = experiment.get("protocol") or {}
    source_id = protocol.get("source_experiment_id") if isinstance(protocol, dict) else None
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
    if abs(overall_diff) < VERDICT_EVEN_THRESHOLD:
        return "even"
    return "stronger" if overall_diff > 0 else "weaker"


def build_experiment_delta(
    *,
    peer_id: str,
    peer_name: str,
    relation: str,
    peer_ready: bool,
    this_landlord_win_rate: float,
    peer_landlord_win_rate: float,
    this_landlord_win_rate_ci: list[float] | None,
    peer_landlord_win_rate_ci: list[float] | None,
    this_decisive_n: int,
    peer_decisive_n: int,
    this_low_power: bool,
    peer_low_power: bool,
    paired_n: int,
    paired_landlord_win_rate_diff: float | None,
    paired_low_power: bool,
    scenario_diffs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One-screen verdict vs a source or control experiment (this minus peer)."""
    overall_diff: float | None = None
    if this_decisive_n > 0 and peer_decisive_n > 0:
        overall_diff = round(this_landlord_win_rate - peer_landlord_win_rate, 4)

    low_power = this_low_power or peer_low_power or paired_low_power
    if this_decisive_n <= 0 or peer_decisive_n <= 0:
        inconclusive_reason: str | None = "no_games"
    elif not peer_ready:
        inconclusive_reason = "peer_not_ready"
    elif low_power:
        inconclusive_reason = "low_power"
    else:
        inconclusive_reason = None

    return {
        "peer_id": peer_id,
        "peer_name": peer_name,
        "relation": relation,
        "peer_ready": peer_ready,
        "this_landlord_win_rate": round(this_landlord_win_rate, 4),
        "peer_landlord_win_rate": round(peer_landlord_win_rate, 4),
        "landlord_win_rate_diff": overall_diff,
        "this_landlord_win_rate_ci": this_landlord_win_rate_ci,
        "peer_landlord_win_rate_ci": peer_landlord_win_rate_ci,
        "this_decisive_n": this_decisive_n,
        "peer_decisive_n": peer_decisive_n,
        "paired_n": paired_n,
        "paired_landlord_win_rate_diff": paired_landlord_win_rate_diff,
        "low_power": low_power,
        "can_conclude": inconclusive_reason is None and overall_diff is not None,
        "inconclusive_reason": inconclusive_reason,
        "verdict_key": verdict_key(
            overall_diff=overall_diff,
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
