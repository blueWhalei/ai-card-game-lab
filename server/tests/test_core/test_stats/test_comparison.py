"""Cohort consistency, missing evidence and protocol review regressions."""

from copy import deepcopy

from app.core.stats.comparison import paired_cohort, protocol_review
from app.services.experiment_service import ExperimentService


def row(id: str) -> dict:
    return {
        "id": id,
        "player_ids": ["a", "b", "c"],
        "protocol": {
            "schema_version": 2,
            "dataset": {"deal_seeds": [1, 2, 3]},
            "engine": {
                "game_type": "doudizhu",
                "engine_version": "1",
                "decision_schema_version": 1,
                "rules_ref": "rules",
                "roles": ["landlord", "peasant"],
                "prompt_keys": {"play": "play"},
                "supports_deal_seed": True,
            },
            "solver": {
                "players": [
                    {"id": p, "name": p, "policy_kind": "llm", "model_config": {"temperature": 0.5}}
                    for p in ["a", "b", "c"]
                ],
                "prompts": {"play": {"content": "play"}},
                "thinking_budget": {},
                "memory": "none",
            },
            "scorer": {"evaluator": {"max_steps": 400}, "eval_metric_ids": ["role:landlord"]},
        },
    }


def game(seed: int, role: str = "landlord", **kwargs: object) -> dict:
    return {
        "id": f"g{seed}",
        "metadata": {"deal_seed": seed},
        "status": "finished",
        "player_ids": ["a", "b", "c"],
        "winner_id": "a",
        "winner_role": role,
        **kwargs,
    }


def test_all_paired_outputs_share_the_intersection() -> None:
    rows = [row("base"), row("variant")]
    games = {"base": [game(1), game(2)], "variant": [game(1, "peasant"), game(3)]}
    coverage, _ = paired_cohort(rows, games)
    assert coverage["planned_shared"] == 3
    assert coverage["effective_seeds"] == [1]
    ExperimentService._attach_paired_compare_metrics(rows, games)
    assert [r["paired_n"] for r in rows] == [1, 1]
    assert [r["paired_landlord_win_rate"] for r in rows] == [1, 0]
    summary = ExperimentService._build_paired_summary(rows, games)
    assert summary is not None
    assert summary["landlord_win_rate_diff"] == -1
    assert summary["seed_diffs"] == [-1]
    assert summary["mcnemar_c"] == 1


def test_duplicates_are_excluded_independent_of_order_even_for_failed_retries() -> None:
    rows = [row("a"), row("b")]
    games = {"a": [game(1), game(1, id="retry", status="failed"), game(2)], "b": [game(1), game(2)]}
    first, _ = paired_cohort(rows, games)
    games["a"].reverse()
    second, _ = paired_cohort(rows, games)
    assert first == second
    assert first["effective_seeds"] == [2]
    assert first["experiments"][0]["conflicts"] == [{"seed": 1, "game_ids": ["g1", "retry"]}]


def test_no_common_outcomes_never_counts_planned_seeds_as_observed_pairs() -> None:
    rows = [row("a"), row("b")]
    games = {"a": [game(1), game(2, status="cancelled"), game(3, winner_role=None)], "b": [game(2)]}
    coverage, _ = paired_cohort(rows, games)
    assert coverage["effective_n"] == 0
    assert coverage["experiments"][0]["excluded"] == {"unfinished": 1, "invalid_outcome": 1}
    summary = ExperimentService._build_paired_summary(rows, games)
    assert summary is not None and summary["shared_seeds"] == 0
    assert summary["landlord_win_rate_diff"] is None


def test_seat_mismatch_and_duplicate_plan_are_not_pairs() -> None:
    rows = [row("a"), row("b")]
    rows[0]["protocol"]["dataset"]["deal_seeds"] = [1, 1, 2, 3]
    games = {"a": [game(1), game(2, player_ids=["b", "a", "c"])], "b": [game(1), game(2)]}
    coverage, _ = paired_cohort(rows, games)
    assert coverage["effective_n"] == 0
    assert coverage["experiments"][0]["excluded"] == {
        "duplicate": 1,
        "seat_mismatch": 1,
        "missing": 1,
    }


def test_exact_declaration_cannot_waive_engine_or_evaluator_changes() -> None:
    a, b = row("a"), row("b")
    b["protocol"]["solver"]["players"][0]["model_config"]["temperature"] = 0.9
    path = "solver.players.0.model_config.temperature"
    assert protocol_review([a, b], [])["controlled"] is False
    review = protocol_review([a, b], [path])
    assert review["controlled"] is True
    assert [d["path"] for d in review["differences"]] == [path]
    b["protocol"]["scorer"]["evaluator"]["max_steps"] = 20
    assert protocol_review([a, b], [path, "scorer.evaluator.max_steps"])["controlled"] is False


def test_missing_identical_protocols_do_not_imply_equivalence() -> None:
    a, b = row("a"), row("b")
    del a["protocol"]["solver"]["prompts"]
    del b["protocol"]["solver"]["prompts"]
    review = protocol_review([a, b], [])
    assert review["controlled"] is False
    assert "unknown_protocol" in review["reasons"]
    assert review["differences"] == []


def test_identity_is_not_a_parameter_and_multiple_groups_are_exploratory() -> None:
    a, b = row("a"), row("b")
    b["protocol"]["solver"]["players"][0]["name"] = "renamed"
    assert protocol_review([a, b], [])["controlled"] is True
    c = deepcopy(b)
    c["id"] = "c"
    assert "exploratory" in protocol_review([a, b, c], [])["reasons"]


def test_non_task_protocol_has_no_pairing_or_control_claim() -> None:
    a = {"id": "a", "protocol": {"schema_version": 1, "deal_seeds": [1], "game_type": "doudizhu"}}
    b = {"id": "b", "protocol": {"schema_version": 1, "deal_seeds": [1], "game_type": "doudizhu"}}
    coverage, _ = paired_cohort([a, b], {"a": [game(1)], "b": [game(1)]})
    assert coverage["effective_n"] == 0
    review = protocol_review([a, b], [])
    assert review["reasons"] == ["unknown_protocol"]
