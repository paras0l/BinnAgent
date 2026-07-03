from src.simulation.evaluator import SimulationEvaluator
from src.simulation.scenario import SimulationStepResult


def test_evaluator_outputs_metric_groups_with_runtime_learning_memory_and_prompt_metrics() -> None:
    steps = [
        SimulationStepResult(
            name="answer",
            status="passed",
            output={
                "answer": {
                    "grading_result": {"correct": True},
                    "mastery_update": {"mastery_delta": 0.12},
                    "memory_updates": [
                        {"memory_event_id": "mem-1", "evidence_refs": [{"type": "exercise", "id": "q1"}]}
                    ],
                    "next_capability_recommendations": [{"capability_id": "grammar-explain"}],
                }
            },
        ),
        SimulationStepResult(
            name="attempt",
            status="passed",
            output={"attempt": {"attempt_id": "attempt-1"}},
        ),
    ]

    report = SimulationEvaluator().build_report(
        persona_id="p",
        scenario_id="s",
        steps=steps,
        api_calls=2,
        api_successes=2,
        agent_triggers=0,
        memory_writes=1,
        runtime_metrics={
            "episode_count": 1,
            "completed_episode_count": 1,
            "failed_episode_count": 0,
            "verification_pass_count": 1,
            "verification_fail_count": 0,
            "tool_statuses": ["success", "failed", "success"],
            "tool_latencies_ms": [10, 20, 30],
            "event_types": ["exercise_graded", "mastery_updated", "memory_written"],
            "prompt_executions": [
                {
                    "schema_validation_status": "repaired",
                    "repair_used": True,
                    "fallback_used": False,
                    "prompt_hash": "a" * 64,
                    "model_policy_snapshot": {"temperature": 0.1},
                }
            ],
        },
        scenario_contract={"expected_events": ["memory_written"]},
    )

    assert set(report.metric_groups) == {
        "runtime",
        "learning",
        "memory",
        "recommendation",
        "parser_rag",
        "prompt_schema",
    }
    assert report.metric_groups["runtime"]["episode_completion_rate"] == 1.0
    assert report.metric_groups["runtime"]["tool_success_rate"] == 2 / 3
    assert report.metric_groups["runtime"]["p95_tool_latency_ms"] == 30
    assert report.metric_groups["learning"]["exercise_attempt_created_count"] == 1
    assert report.metric_groups["learning"]["mastery_update_count"] == 1
    assert report.metric_groups["memory"]["memory_evidence_ref_coverage"] == 1.0
    assert report.metric_groups["recommendation"]["recommendation_generated_count"] == 1
    assert report.metric_groups["prompt_schema"]["schema_validation_pass_rate"] == 1.0
    assert report.to_dict()["metric_groups"]["runtime"]["avg_tool_latency_ms"] == 20


def test_evaluator_metric_groups_tolerate_missing_data() -> None:
    report = SimulationEvaluator().build_report(
        persona_id="p",
        scenario_id="s",
        steps=[],
        api_calls=0,
        api_successes=0,
        agent_triggers=0,
        memory_writes=0,
        runtime_metrics={},
        scenario_contract={},
    )

    assert report.metric_groups["runtime"]["episode_completion_rate"] is None
    assert report.metric_groups["runtime"]["tool_success_rate"] is None
    assert report.metric_groups["parser_rag"]["parser_quality_score"] is None
    assert report.metric_groups["prompt_schema"]["prompt_execution_count"] == 0
