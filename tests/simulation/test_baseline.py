from pathlib import Path

from src.simulation.baseline import (
    compare_report_to_baseline,
    detect_regressions,
    evaluate_thresholds,
    flatten_metric_groups,
    load_baseline,
    write_baseline,
)
from src.simulation.scenario import SimulationReport


def _report() -> SimulationReport:
    return SimulationReport(
        persona="p",
        scenario="episode_runtime_knowledge_practice",
        status="passed",
        steps=[],
        metrics={"api_success_rate": 1.0, "assertion_pass_rate": 1.0},
        metric_groups={
            "runtime": {
                "verification_pass_rate": 1.0,
                "avg_tool_latency_ms": 25,
            }
        },
        failures=[],
    )


def test_flatten_metric_groups_includes_top_level_and_grouped_metrics() -> None:
    flattened = flatten_metric_groups(_report())

    assert flattened["api_success_rate"] == 1.0
    assert flattened["runtime.verification_pass_rate"] == 1.0


def test_load_baseline_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_baseline("missing", tmp_path) is None
    comparison = compare_report_to_baseline(_report(), None)
    assert comparison["baseline_found"] is False


def test_compare_report_to_baseline_outputs_diffs_and_regressions() -> None:
    report = _report()
    report.metric_groups["runtime"]["verification_pass_rate"] = 0.0
    baseline = {
        "scenario_id": "episode_runtime_knowledge_practice",
        "version": 1,
        "metrics": {"api_success_rate": 1.0},
        "metric_groups": {"runtime": {"verification_pass_rate": 1.0}},
    }

    comparison = compare_report_to_baseline(report, baseline)
    regressions = detect_regressions(comparison)

    assert comparison["baseline_found"] is True
    assert comparison["metric_diffs"][1]["metric"] == "runtime.verification_pass_rate"
    assert regressions[0]["metric"] == "runtime.verification_pass_rate"
    assert regressions[0]["severity"] == "critical"


def test_thresholds_support_min_max_and_equals() -> None:
    report = _report()
    failures = evaluate_thresholds(
        report,
        {
            "api_success_rate": {"min": 1.0},
            "runtime.avg_tool_latency_ms": {"max": 10},
            "runtime.verification_pass_rate": {"equals": 0.5},
        },
    )

    assert [failure["metric"] for failure in failures] == [
        "runtime.avg_tool_latency_ms",
        "runtime.verification_pass_rate",
    ]
    assert failures[0]["expected"] == "<= 10"
    assert failures[1]["expected"] == "== 0.5"


def test_write_baseline_preserves_existing_thresholds(tmp_path: Path) -> None:
    existing = {"version": 3, "thresholds": {"api_success_rate": {"min": 1.0}}}

    path = write_baseline(_report(), tmp_path, existing_baseline=existing)
    loaded = load_baseline("episode_runtime_knowledge_practice", tmp_path)

    assert path.exists()
    assert loaded["version"] == 3
    assert loaded["thresholds"] == existing["thresholds"]
