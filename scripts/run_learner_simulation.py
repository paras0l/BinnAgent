#!/usr/bin/env python3
import argparse
import asyncio
import json
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import app
from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.runner import ScenarioRunner


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic BinnAgent learner simulations.")
    parser.add_argument("--persona", choices=sorted(BUILTIN_PERSONAS), default="grade7_low_vocab")
    parser.add_argument("--scenario", choices=sorted(BUILTIN_SCENARIOS), default="smoke_learning_journey")
    args = parser.parse_args()

    persona = BUILTIN_PERSONAS[args.persona]
    scenario = BUILTIN_SCENARIOS[args.scenario]
    if scenario.persona_id != persona.id:
        scenario = type(scenario)(
            id=scenario.id,
            name=scenario.name,
            persona_id=persona.id,
            steps=scenario.steps,
        )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        report = await ScenarioRunner(client).run(scenario=scenario, persona=persona)

    report_data = report.to_dict()
    _write_report(report_data)
    print(json.dumps(report_data, ensure_ascii=False, indent=2))
    return 0 if report.status == "passed" else 1


def _write_report(report_data: dict) -> None:
    report_root = ROOT / "var" / "simulation"
    reports_dir = report_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report_data, ensure_ascii=False, indent=2)
    (reports_dir / f"{report_data['run_id']}.json").write_text(content, encoding="utf-8")
    (report_root / "latest_report.json").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
