#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.extraction.writing_phrase import writing_phrase_regex_fallback_payload  # noqa: E402
from src.prompts import PromptExecutionContext, PromptExecutor, PromptMetadata, prompt_registry  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        reports = asyncio.run(_evaluate(args))
    except Exception as exc:
        print(f"Prompt evaluation failed: {exc}", file=sys.stderr)
        return 2

    output: dict[str, Any] | list[dict[str, Any]]
    if args.all:
        output = {
            "status": "failed" if any(report["status"] == "failed" for report in reports) else "passed",
            "reports": reports,
        }
    else:
        output = reports[0]

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            metrics = report["metrics"]
            print(
                f"{report['prompt_id']}@{report['version']}: {report['status']} "
                f"schema_pass_rate={metrics['schema_pass_rate']} "
                f"repair_rate={metrics['repair_rate']} "
                f"fallback_rate={metrics['fallback_rate']} "
                f"accepted_rate={metrics['accepted_rate']}"
            )

    return 1 if any(report["status"] == "failed" for report in reports) else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate registered prompt eval sets.")
    parser.add_argument("--prompt-id", help="Prompt id to evaluate.")
    parser.add_argument("--version", help="Prompt version. Defaults to active version.")
    parser.add_argument("--all", action="store_true", help="Evaluate every prompt with eval_set.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument(
        "--min-schema-pass-rate",
        type=float,
        default=0.6,
        help="Fail if schema_pass_rate is below this threshold.",
    )
    return parser.parse_args(argv)


async def _evaluate(args: argparse.Namespace) -> list[dict[str, Any]]:
    metadata = _selected_metadata(args)
    reports = []
    for item in metadata:
        reports.append(
            await evaluate_prompt_metadata(
                item,
                min_schema_pass_rate=args.min_schema_pass_rate,
            )
        )
    return reports


def _selected_metadata(args: argparse.Namespace) -> list[PromptMetadata]:
    if args.all:
        items = [item for item in prompt_registry.list() if item.eval_set]
    else:
        if not args.prompt_id:
            raise ValueError("Use --prompt-id PROMPT_ID or --all.")
        item = prompt_registry.get(args.prompt_id, args.version)
        items = [item]
    if not items:
        raise ValueError("No prompt eval_set found.")
    missing = [item.id for item in items if not item.eval_set]
    if missing:
        raise ValueError(f"Prompt has no eval_set: {', '.join(missing)}")
    return items


async def evaluate_prompt_metadata(
    metadata: PromptMetadata,
    *,
    min_schema_pass_rate: float,
) -> dict[str, Any]:
    cases = list(_read_eval_set(metadata))
    if not cases:
        raise ValueError(f"Empty eval_set for {metadata.id}@{metadata.version}")

    executor = PromptExecutor()
    results: list[dict[str, Any]] = []
    for case in cases:
        raw_output = case.get("raw_output")
        if not isinstance(raw_output, str):
            raise ValueError(f"{metadata.eval_set} case {case.get('case_id')} missing raw_output")
        variables = case.get("input") if isinstance(case.get("input"), dict) else {}
        result = await executor.execute_with_raw_output(
            prompt_id=metadata.id,
            version=metadata.version,
            variables=variables,
            raw_output=raw_output,
            context=PromptExecutionContext(source_module="prompt_eval"),
            fallback_parser=_fallback_parser(metadata, variables),
        )
        results.append(
            {
                "case_id": case.get("case_id"),
                "schema_validation_status": result.schema_validation_status,
                "repair_used": result.repair_used,
                "fallback_used": result.fallback_used,
                "decision": result.decision,
                "confidence": result.confidence,
                "parse_mode": result.parse_mode,
                "schema_error_summary": result.schema_error_summary,
            }
        )

    metrics = _metrics(results)
    threshold_failures = []
    if metrics["schema_pass_rate"] < min_schema_pass_rate:
        threshold_failures.append(
            {
                "metric": "schema_pass_rate",
                "value": metrics["schema_pass_rate"],
                "rule": "min",
                "expected": min_schema_pass_rate,
            }
        )
    return {
        "prompt_id": metadata.id,
        "version": metadata.version,
        "eval_set": metadata.eval_set,
        "status": "failed" if threshold_failures else "passed",
        "metrics": metrics,
        "threshold_failures": threshold_failures,
        "case_count": len(results),
        "cases": results,
    }


def _read_eval_set(metadata: PromptMetadata) -> list[dict[str, Any]]:
    assert metadata.eval_set is not None
    path = REPO_ROOT / metadata.eval_set
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        cases.append(value)
    return cases


def _fallback_parser(metadata: PromptMetadata, variables: dict[str, Any]):
    if metadata.id != "writing_phrase.import":
        return None

    def parse(raw_output: str) -> dict[str, Any] | None:
        topic = variables.get("topic") if isinstance(variables.get("topic"), str) else None
        return writing_phrase_regex_fallback_payload(raw_output, topic)

    return parse


def _metrics(results: list[dict[str, Any]]) -> dict[str, float | None]:
    total = len(results)
    statuses = [str(item["schema_validation_status"]) for item in results]
    confidences = [
        float(item["confidence"])
        for item in results
        if isinstance(item.get("confidence"), int | float)
    ]
    return {
        "schema_pass_rate": _ratio(
            sum(1 for status in statuses if status in {"passed", "repaired"}),
            total,
        ),
        "repair_rate": _ratio(sum(1 for item in results if item["repair_used"]), total),
        "fallback_rate": _ratio(sum(1 for item in results if item["fallback_used"]), total),
        "accepted_rate": _ratio(sum(1 for item in results if item["decision"] == "accepted"), total),
        "review_required_rate": _ratio(
            sum(1 for item in results if item["decision"] == "review_required"),
            total,
        ),
        "confidence_avg": round(sum(confidences) / len(confidences), 4) if confidences else None,
    }


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
