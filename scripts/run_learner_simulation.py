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

from src.api import deps
from src.main import app
from src.simulation.baseline import (
    compare_report_to_baseline,
    detect_regressions,
    evaluate_thresholds,
    load_baseline,
    write_baseline,
)
from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.fake_model import DeterministicFakeModelRouter
from src.simulation.mock_transport import build_contract_transport, contract_graph_invoker
from src.simulation.runner import ScenarioRunner
from src.simulation.scenario import SimulationMode, SimulationReport, SimulationScenario


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic BinnAgent learner simulations.")
    parser.add_argument("--persona", choices=sorted(BUILTIN_PERSONAS), default="grade7_low_vocab")
    parser.add_argument("--scenario", choices=sorted(BUILTIN_SCENARIOS), default="smoke_learning_journey")
    parser.add_argument("--mode", choices=["contract", "integration", "e2e"], default="contract")
    parser.add_argument("--all", action="store_true", help="Run all scenarios, optionally filtered by --tag.")
    parser.add_argument("--tag", action="append", default=[], help="Run scenarios with this module tag. Repeatable.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL for --mode e2e.")
    parser.add_argument("--report-dir", default=str(ROOT / "var" / "simulation" / "reports"))
    parser.add_argument("--baseline-dir", default=str(ROOT / "var" / "simulation" / "baselines"))
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--fail-on-threshold", action="store_true")
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()

    persona = BUILTIN_PERSONAS[args.persona]
    scenarios = _select_scenarios(args)
    reports: list[SimulationReport] = []
    baseline_paths: dict[str, Path | None] = {}

    for scenario in scenarios:
        active_scenario = scenario
        if active_scenario.persona_id != persona.id:
            active_scenario = replace(active_scenario, persona_id=persona.id)
        report = await _run_one(
            scenario=active_scenario,
            persona=persona,
            mode=args.mode,
            base_url=args.base_url,
        )
        reports.append(report)
        baseline_paths[report.scenario] = _apply_baseline(
            report,
            baseline_dir=Path(args.baseline_dir),
            update_baseline=args.update_baseline,
        )
        _print_scenario_contract(active_scenario, mode=args.mode)
        _print_baseline_summary(report, baseline_path=baseline_paths[report.scenario])

    output = _write_reports(
        [report.to_dict() for report in reports],
        report_dir=Path(args.report_dir),
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return _combined_exit_code(
        reports,
        fail_on_threshold=args.fail_on_threshold,
        fail_on_regression=args.fail_on_regression,
    )


def _select_scenarios(args: argparse.Namespace) -> list[SimulationScenario]:
    if args.all or args.tag:
        scenarios = list(BUILTIN_SCENARIOS.values())
        tags = set(args.tag or [])
        if tags:
            scenarios = [
                scenario
                for scenario in scenarios
                if tags.intersection(scenario.module_tags)
            ]
        return sorted(scenarios, key=lambda item: item.id)
    return [BUILTIN_SCENARIOS[args.scenario]]


async def _run_one(
    *,
    scenario: SimulationScenario,
    persona,
    mode: SimulationMode,
    base_url: str,
) -> SimulationReport:
    if mode == "contract":
        async with httpx.AsyncClient(
            transport=build_contract_transport(scenario),
            base_url="http://test",
        ) as client:
            return await ScenarioRunner(
                client,
                graph_invoker=contract_graph_invoker,
                mode=mode,
            ).run(scenario=scenario, persona=persona)
    if mode == "integration":
        fake_model = DeterministicFakeModelRouter()
        previous = dict(app.dependency_overrides)
        app.dependency_overrides[deps.get_model_router] = lambda: fake_model
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await ScenarioRunner(client, mode=mode).run(
                    scenario=scenario,
                    persona=persona,
                )
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous)
    async with httpx.AsyncClient(base_url=base_url) as client:
        return await ScenarioRunner(client, mode=mode).run(
            scenario=scenario,
            persona=persona,
        )


def _write_reports(report_data: list[dict], *, report_dir: Path) -> dict:
    report_dir.mkdir(parents=True, exist_ok=True)
    for report in report_data:
        content = json.dumps(report, ensure_ascii=False, indent=2)
        (report_dir / f"{report['run_id']}.json").write_text(content, encoding="utf-8")
    if len(report_data) == 1:
        output = report_data[0]
    else:
        output = {
            "mode": report_data[0]["mode"] if report_data else None,
            "status": "failed" if any(report["status"] == "failed" for report in report_data) else "passed",
            "scenario_count": len(report_data),
            "reports": report_data,
        }
    (report_dir / "latest_report.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


def _print_scenario_contract(scenario, *, mode: str) -> None:
    print(f"mode: {mode}", file=sys.stderr)
    print(f"scenario: {scenario.id}", file=sys.stderr)
    print(f"entrypoints: {', '.join(scenario.entrypoints) or '-'}", file=sys.stderr)
    print(f"module_tags: {', '.join(scenario.module_tags) or '-'}", file=sys.stderr)
    print(f"required_metrics: {', '.join(scenario.required_metrics) or '-'}", file=sys.stderr)
    print(f"expected_events: {', '.join(scenario.expected_events) or '-'}", file=sys.stderr)
    print(f"expected_tool_calls: {', '.join(scenario.expected_tool_calls) or '-'}", file=sys.stderr)
    print(f"change_triggers: {', '.join(scenario.change_triggers) or '-'}", file=sys.stderr)


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


def _combined_exit_code(
    reports: list[SimulationReport],
    *,
    fail_on_threshold: bool,
    fail_on_regression: bool,
) -> int:
    return max(
        (
            _exit_code(
                report,
                fail_on_threshold=fail_on_threshold,
                fail_on_regression=fail_on_regression,
            )
            for report in reports
        ),
        default=0,
    )


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
