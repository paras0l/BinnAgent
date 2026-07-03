import json
from pathlib import Path
from typing import Any

from src.simulation.scenario import SimulationReport


def load_baseline(scenario_id: str, baseline_dir: str | Path) -> dict[str, Any] | None:
    path = Path(baseline_dir) / f"{scenario_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_metric_groups(report: SimulationReport) -> dict[str, Any]:
    flattened: dict[str, Any] = dict(report.metrics)
    for group, values in report.metric_groups.items():
        for key, value in values.items():
            flattened[f"{group}.{key}"] = value
    return flattened


def compare_report_to_baseline(
    report: SimulationReport,
    baseline: dict[str, Any] | None,
) -> dict[str, Any]:
    if baseline is None:
        return {
            "baseline_found": False,
            "scenario_id": report.scenario,
            "metric_diffs": [],
        }

    current = flatten_metric_groups(report)
    baseline_metrics = _flatten_baseline_metrics(baseline)
    diffs = []
    for metric, baseline_value in sorted(baseline_metrics.items()):
        current_value = current.get(metric)
        delta = _delta(current_value, baseline_value)
        diffs.append(
            {
                "metric": metric,
                "current": current_value,
                "baseline": baseline_value,
                "delta": delta,
                "status": _diff_status(metric, current_value, baseline_value, delta),
            }
        )
    return {
        "baseline_found": True,
        "scenario_id": report.scenario,
        "baseline_version": baseline.get("version"),
        "metric_diffs": diffs,
    }


def detect_regressions(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    regressions: list[dict[str, Any]] = []
    for diff in comparison.get("metric_diffs", []):
        if diff.get("status") != "regressed":
            continue
        metric = diff["metric"]
        current = diff.get("current")
        baseline = diff.get("baseline")
        delta = diff.get("delta")
        regressions.append(
            {
                "metric": metric,
                "current": current,
                "baseline": baseline,
                "delta": delta,
                "severity": _regression_severity(metric, current, baseline),
                "message": f"{metric} regressed from {baseline!r} to {current!r}",
            }
        )
    return regressions


def evaluate_thresholds(
    report: SimulationReport,
    thresholds: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not thresholds:
        return []

    current = flatten_metric_groups(report)
    failures: list[dict[str, Any]] = []
    for metric, rule in sorted(thresholds.items()):
        if not isinstance(rule, dict):
            continue
        value = current.get(metric)
        for operator, expected in rule.items():
            if operator not in {"min", "max", "equals"}:
                continue
            if _threshold_passed(value, operator, expected):
                continue
            failures.append(
                {
                    "metric": metric,
                    "current": value,
                    "expected": _threshold_expected_text(operator, expected),
                    "severity": "warning" if operator == "max" else "critical",
                }
            )
    return failures


def baseline_payload_for_report(
    report: SimulationReport,
    *,
    existing_baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "scenario_id": report.scenario,
        "version": int((existing_baseline or {}).get("version") or 1),
        "metrics": report.metrics,
        "metric_groups": report.metric_groups,
        "thresholds": (existing_baseline or {}).get("thresholds", {}),
    }


def write_baseline(
    report: SimulationReport,
    baseline_dir: str | Path,
    *,
    existing_baseline: dict[str, Any] | None = None,
) -> Path:
    path = Path(baseline_dir) / f"{report.scenario}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = baseline_payload_for_report(report, existing_baseline=existing_baseline)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _flatten_baseline_metrics(baseline: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    metrics = baseline.get("metrics")
    if isinstance(metrics, dict):
        flattened.update(metrics)
    metric_groups = baseline.get("metric_groups")
    if isinstance(metric_groups, dict):
        for group, values in metric_groups.items():
            if not isinstance(values, dict):
                continue
            for key, value in values.items():
                flattened[f"{group}.{key}"] = value
    return flattened


def _delta(current: Any, baseline: Any) -> float | None:
    if isinstance(current, int | float) and isinstance(baseline, int | float):
        return float(current) - float(baseline)
    return None


def _diff_status(metric: str, current: Any, baseline: Any, delta: float | None) -> str:
    if current is None or baseline is None:
        return "missing"
    if delta is None:
        return "same" if current == baseline else "changed"
    if delta == 0:
        return "same"
    if "latency_ms" in metric:
        return "regressed" if delta > 0 else "improved"
    return "regressed" if delta < 0 else "improved"


def _regression_severity(metric: str, current: Any, baseline: Any) -> str:
    if "pass_rate" in metric or "success_rate" in metric:
        return "critical"
    if "latency_ms" in metric and isinstance(current, int | float) and isinstance(baseline, int | float):
        return "critical" if baseline and current > baseline * 2 else "warning"
    return "warning"


def _threshold_passed(value: Any, operator: str, expected: Any) -> bool:
    if value is None:
        return False
    if operator == "equals":
        return value == expected
    if not isinstance(value, int | float) or not isinstance(expected, int | float):
        return False
    if operator == "min":
        return value >= expected
    if operator == "max":
        return value <= expected
    return False


def _threshold_expected_text(operator: str, expected: Any) -> str:
    if operator == "min":
        return f">= {expected}"
    if operator == "max":
        return f"<= {expected}"
    return f"== {expected!r}"
