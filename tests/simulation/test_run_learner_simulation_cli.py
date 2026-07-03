from argparse import Namespace

from scripts.run_learner_simulation import _apply_baseline, _exit_code, _select_scenarios
from src.simulation.scenario import SimulationReport


def _report() -> SimulationReport:
    return SimulationReport(
        persona="p",
        scenario="smoke_learning_journey",
        status="passed",
        steps=[],
        metrics={"api_success_rate": 1.0, "assertion_pass_rate": 1.0},
        metric_groups={"runtime": {"avg_tool_latency_ms": 50}},
        failures=[],
    )


def test_apply_baseline_update_writes_current_report_and_preserves_thresholds(tmp_path) -> None:
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir()
    (baseline_dir / "smoke_learning_journey.json").write_text(
        """
{
  "scenario_id": "smoke_learning_journey",
  "version": 1,
  "metrics": {"api_success_rate": 1.0},
  "metric_groups": {},
  "thresholds": {"api_success_rate": {"min": 1.0}}
}
""".strip(),
        encoding="utf-8",
    )
    report = _report()

    path = _apply_baseline(report, baseline_dir=baseline_dir, update_baseline=True)

    assert path == baseline_dir / "smoke_learning_journey.json"
    assert report.baseline_comparison["baseline_found"] is True
    assert '"assertion_pass_rate": 1.0' in path.read_text(encoding="utf-8")
    assert '"thresholds": {' in path.read_text(encoding="utf-8")


def test_exit_code_can_fail_on_threshold_or_regression() -> None:
    report = _report()
    report.threshold_failures = [{"metric": "api_success_rate"}]

    assert _exit_code(report, fail_on_threshold=True, fail_on_regression=False) == 1
    assert _exit_code(report, fail_on_threshold=False, fail_on_regression=False) == 0

    report.threshold_failures = []
    report.regressions = [{"metric": "runtime.verification_pass_rate"}]
    assert _exit_code(report, fail_on_threshold=False, fail_on_regression=True) == 1


def test_select_scenarios_supports_all_and_tag_filters() -> None:
    all_scenarios = _select_scenarios(Namespace(all=True, tag=[], scenario="smoke_learning_journey"))
    prompt_scenarios = _select_scenarios(
        Namespace(all=False, tag=["prompt_schema"], scenario="smoke_learning_journey")
    )

    assert len(all_scenarios) > 1
    assert [scenario.id for scenario in prompt_scenarios] == [
        "llm_json_missing_field_triggers_repair"
    ]
