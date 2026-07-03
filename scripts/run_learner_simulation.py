#!/usr/bin/env python3
import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import app
from src.simulation.baseline import (
    compare_report_to_baseline,
    detect_regressions,
    evaluate_thresholds,
    load_baseline,
    write_baseline,
)
from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.runner import ScenarioRunner
from src.simulation.scenario import SimulationReport


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic BinnAgent learner simulations.")
    parser.add_argument("--persona", choices=sorted(BUILTIN_PERSONAS), default="grade7_low_vocab")
    parser.add_argument("--scenario", choices=sorted(BUILTIN_SCENARIOS), default="smoke_learning_journey")
    parser.add_argument("--baseline-dir", default=str(ROOT / "var" / "simulation" / "baselines"))
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--fail-on-threshold", action="store_true")
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()

    persona = BUILTIN_PERSONAS[args.persona]
    scenario = BUILTIN_SCENARIOS[args.scenario]
    if scenario.persona_id != persona.id:
        scenario = replace(scenario, persona_id=persona.id)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        report = await ScenarioRunner(client).run(scenario=scenario, persona=persona)

    baseline_path = _apply_baseline(
        report,
        baseline_dir=Path(args.baseline_dir),
        update_baseline=args.update_baseline,
    )
    report_data = report.to_dict()
    _write_report(report_data)
    _print_scenario_contract(scenario)
    _print_baseline_summary(report, baseline_path=baseline_path)
    print(json.dumps(report_data, ensure_ascii=False, indent=2))
    return _exit_code(
        report,
        fail_on_threshold=args.fail_on_threshold,
        fail_on_regression=args.fail_on_regression,
    )


def _write_report(report_data: dict) -> None:
    report_root = ROOT / "var" / "simulation"
    reports_dir = report_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report_data, ensure_ascii=False, indent=2)
    (reports_dir / f"{report_data['run_id']}.json").write_text(content, encoding="utf-8")
    (report_root / "latest_report.json").write_text(content, encoding="utf-8")


def _print_scenario_contract(scenario) -> None:
    print(f"scenario: {scenario.id}", file=sys.stderr)
    print(f"module_tags: {', '.join(scenario.module_tags) or '-'}", file=sys.stderr)
    print(f"required_metrics: {', '.join(scenario.required_metrics) or '-'}", file=sys.stderr)
    print(f"expected_events: {', '.join(scenario.expected_events) or '-'}", file=sys.stderr)
    print(f"expected_tool_calls: {', '.join(scenario.expected_tool_calls) or '-'}", file=sys.stderr)


def _apply_baseline(
    report: SimulationReport,
    *,
    baseline_dir: Path,
    update_baseline: bool,
) -> Path | None:
    baseline = load_baseline(report.scenario, baseline_dir)
    report.baseline_comparison = compare_report_to_baseline(report, baseline)
    report.regressions = detect_regressions(report.baseline_comparison)
    thresholds = baseline.get("thresholds") if isinstance(baseline, dict) else {}
    report.threshold_failures = evaluate_thresholds(report, thresholds)
    if update_baseline:
        return write_baseline(report, baseline_dir, existing_baseline=baseline)
    return None


def _exit_code(
    report: SimulationReport,
    *,
    fail_on_threshold: bool,
    fail_on_regression: bool,
) -> int:
    if report.status != "passed":
        return 1
    if fail_on_threshold and report.threshold_failures:
        return 1
    if fail_on_regression and report.regressions:
        return 1
    return 0


def _print_baseline_summary(report: SimulationReport, *, baseline_path: Path | None) -> None:
    comparison = report.baseline_comparison or {}
    print(
        f"baseline_found: {comparison.get('baseline_found', False)}",
        file=sys.stderr,
    )
    print(f"regressions: {len(report.regressions)}", file=sys.stderr)
    print(f"threshold_failures: {len(report.threshold_failures)}", file=sys.stderr)
    if baseline_path is not None:
        print(f"baseline updated: {baseline_path}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
