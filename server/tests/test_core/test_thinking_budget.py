"""protocol.solver.thinking_budget accessors."""

from app.core.task_protocol import build_protocol, protocol_thinking_budget


def test_protocol_thinking_budget_round_trip() -> None:
    protocol = build_protocol(
        players=[{"id": "p1"}],
        source_experiment_id=None,
        pair_deals=False,
        deal_seeds=[],
        frozen_at="t",
        prompt_version="v3",
        collect_mode="free",
        protocol_fingerprint={
            "game_type": "doudizhu",
            "engine_version": "1",
            "decision_schema_version": 2,
            "rules_ref": None,
            "phases": [],
            "prompt_keys": [],
            "roles": [],
            "supports_deal_seed": True,
            "benchmark_seed_count": 0,
            "eval_metric_ids": [],
        },
        thinking_budget={"reasoning_effort": "medium", "max_thinking_tokens": 1024},
    )
    assert protocol["solver"]["thinking_budget"]["reasoning_effort"] == "medium"
    budget = protocol_thinking_budget(protocol)
    assert budget == {"reasoning_effort": "medium", "max_thinking_tokens": 1024}


def test_llm_policy_kwargs_include_thinking_budget() -> None:
    from app.core.policy.llm import LLMPolicy
    from tests.test_core.test_policy.test_llm_policy import ScriptedClient

    policy = LLMPolicy(
        ScriptedClient([]),
        model_name="deepseek-r1",
        reasoning_effort="high",
        max_thinking_tokens=2048,
        max_tokens=512,
    )
    kwargs = policy._call_kwargs(["PASS||"])
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["max_tokens"] == 2048
