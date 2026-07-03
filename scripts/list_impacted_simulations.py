#!/usr/bin/env python3
import argparse
import fnmatch
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.simulation.fixtures import BUILTIN_SCENARIOS
from src.simulation.scenario import SimulationScenario


def impacted_simulations(changed_files: list[str]) -> list[SimulationScenario]:
    normalized = [_normalize_path(path) for path in changed_files if path.strip()]
    impacted: list[SimulationScenario] = []
    for scenario in BUILTIN_SCENARIOS.values():
        if any(_matches_any_trigger(path, scenario.change_triggers) for path in normalized):
            impacted.append(scenario)
    return sorted(impacted, key=lambda item: item.id)


def impacted_payload(changed_files: list[str]) -> dict[str, Any]:
    scenarios = impacted_simulations(changed_files)
    module_tags = sorted({tag for scenario in scenarios for tag in scenario.module_tags})
    return {
        "changed_files": [_normalize_path(path) for path in changed_files if path.strip()],
        "module_tags": module_tags,
        "scenario_count": len(scenarios),
        "scenarios": [
            {
                "id": scenario.id,
                "name": scenario.name,
                "module_tags": scenario.module_tags,
                "entrypoints": scenario.entrypoints,
                "required_metrics": scenario.required_metrics,
                "expected_events": scenario.expected_events,
                "expected_tool_calls": scenario.expected_tool_calls,
                "change_triggers": scenario.change_triggers,
            }
            for scenario in scenarios
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="List simulation scenarios impacted by changed files.")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Changed file paths.")
    parser.add_argument(
        "--changed-files-file",
        help="Text file containing one changed file path per line.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    changed_files = list(args.changed_files)
    if args.changed_files_file:
        changed_files.extend(_read_changed_files(Path(args.changed_files_file)))
    if not changed_files:
        parser.error("Provide --changed-files or --changed-files-file")

    payload = impacted_payload(changed_files)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("Changed files:")
    for path in payload["changed_files"]:
        print(f"  - {path}")
    print()
    print(f"Impacted scenarios: {payload['scenario_count']}")
    if not payload["scenarios"]:
        print("  none")
        return 0
    for scenario in payload["scenarios"]:
        print(f"  - {scenario['id']} ({', '.join(scenario['module_tags'])})")
        if scenario["required_metrics"]:
            print(f"    required_metrics: {', '.join(scenario['required_metrics'])}")
    print()
    print(f"Module tags: {', '.join(payload['module_tags'])}")
    return 0


def _read_changed_files(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _matches_any_trigger(path: str, triggers: list[str]) -> bool:
    return any(_matches_trigger(path, trigger) for trigger in triggers)


def _matches_trigger(path: str, trigger: str) -> bool:
    normalized_trigger = _normalize_path(trigger)
    if not normalized_trigger:
        return False
    if normalized_trigger.endswith("/**"):
        prefix = normalized_trigger[:-3].rstrip("/")
        return path == prefix or path.startswith(f"{prefix}/")
    if any(char in normalized_trigger for char in "*?[]"):
        return fnmatch.fnmatch(path, normalized_trigger)
    if path == normalized_trigger:
        return True
    if normalized_trigger.endswith("/"):
        return path.startswith(normalized_trigger)
    return path.startswith(f"{normalized_trigger.rstrip('/')}/")


def _normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/").lstrip("./")


if __name__ == "__main__":
    raise SystemExit(main())
