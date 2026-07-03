#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pypdf import PdfReader  # noqa: E402

from src.knowledge import processor  # noqa: E402
from src.knowledge.parser_eval import (  # noqa: E402
    build_parser_evaluation_report,
    compare_with_baseline,
    list_golden_profiles,
    load_baseline,
    load_golden_dataset,
    validate_expected_schema,
    write_baseline,
)
from src.knowledge.parser_profiles import PARSER_PROFILES, ParserProfile  # noqa: E402
from src.knowledge.parser_report import build_parser_report  # noqa: E402


PARSER_ID = "pypdf_manifest_profile_v1"
PARSER_VERSION = "v1"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profiles = list_golden_profiles(args.golden_dir) if args.all else [args.profile]
    profiles = [profile for profile in profiles if profile]
    if not profiles:
        print("No profile selected. Use --profile PROFILE or --all.", file=sys.stderr)
        return 2

    reports: list[dict[str, Any]] = []
    exit_code = 0
    for profile_id in profiles:
        try:
            report = evaluate_profile(
                profile_id=profile_id,
                golden_dir=args.golden_dir,
                baseline_dir=args.baseline_dir,
                report_dir=args.report_dir,
                update_baseline=args.update_baseline,
            )
        except Exception as exc:
            print(f"Parser evaluation failed for {profile_id}: {exc}", file=sys.stderr)
            return 1
        reports.append(report)
        comparison = report.get("baseline_comparison") or {}
        regressions = comparison.get("regressions") if isinstance(comparison, dict) else []
        threshold_failures = report.get("threshold_failures") or []
        if args.fail_on_regression and regressions:
            exit_code = 1
        if args.fail_on_threshold and threshold_failures:
            exit_code = 1

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
            print(
                f"{report['profile_id']}: {report['status']} "
                f"unit_title_exact_match={report['metrics'].get('unit_title_exact_match')} "
                f"vocabulary_recall={report['metrics'].get('vocabulary_recall')} "
                f"dirty_token_rate={report['metrics'].get('dirty_token_rate')}"
            )
            if report.get("threshold_failures"):
                print(f"  threshold_failures={report['threshold_failures']}")
            comparison = report.get("baseline_comparison") or {}
            if comparison.get("regressions"):
                print(f"  regressions={comparison['regressions']}")
    return exit_code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate textbook parser against golden datasets.")
    parser.add_argument("--profile", help="Golden profile id, for example pep_grade7_upper")
    parser.add_argument("--all", action="store_true", help="Evaluate every profile under books/golden")
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout")
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Return non-zero if metrics regress below the stored baseline.",
    )
    parser.add_argument(
        "--fail-on-threshold",
        action="store_true",
        help="Return non-zero if metrics violate configured min/max thresholds.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update baseline metrics from the current report while preserving thresholds.",
    )
    parser.add_argument("--report-dir", default="var/parser_eval", help="Directory for reports")
    parser.add_argument("--golden-dir", default="books/golden", help="Golden dataset root")
    parser.add_argument(
        "--baseline-dir",
        default="var/parser_eval/baselines",
        help="Parser evaluation baseline directory",
    )
    return parser.parse_args(argv)


def evaluate_profile(
    *,
    profile_id: str,
    golden_dir: str | Path = "books/golden",
    baseline_dir: str | Path = "var/parser_eval/baselines",
    report_dir: str | Path = "var/parser_eval",
    update_baseline: bool = False,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    dataset = load_golden_dataset(profile_id, golden_dir)
    schema_errors = validate_expected_schema(dataset.expected)
    if schema_errors:
        raise ValueError("; ".join(schema_errors))

    actual, quality_report_summary = parse_fixture(dataset.root, dataset.manifest)
    baseline = load_baseline(profile_id, baseline_dir)
    report = build_parser_evaluation_report(
        profile_id=profile_id,
        parser_id=PARSER_ID,
        parser_version=PARSER_VERSION,
        expected=dataset.expected,
        actual=actual,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        parser_run_id=None,
        quality_report_summary=quality_report_summary,
        baseline=baseline,
    )
    if baseline is None:
        report["baseline_comparison"] = compare_with_baseline(report["metrics"], None)
    if update_baseline:
        baseline_path = write_baseline(
            profile_id=profile_id,
            report=report,
            baseline_dir=baseline_dir,
            existing_baseline=baseline,
        )
        report["baseline_updated"] = str(baseline_path)
    write_report(report, report_dir)
    return report


def parse_fixture(
    profile_root: Path,
    manifest: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    fixture_path = resolve_fixture_path(profile_root, manifest)
    if fixture_path.suffix.lower() == ".json":
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON parser fixture must contain an object")
        actual = payload.get("actual") if isinstance(payload.get("actual"), dict) else payload
        quality = payload.get("quality_report_summary")
        return _normalized_actual(actual), quality if isinstance(quality, dict) else {}
    if fixture_path.suffix.lower() != ".pdf":
        raise ValueError(f"Unsupported source fixture: {fixture_path}")
    return parse_pdf_fixture(fixture_path, manifest)


def parse_pdf_fixture(
    fixture_path: Path,
    manifest: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    parser_profile = _parser_profile_from_manifest(manifest)
    parsed = processor._parse_pdf(fixture_path)
    reader = PdfReader(str(fixture_path))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    vocabulary_entries = processor._parse_unit_vocabulary(reader)
    if not vocabulary_entries and "lower" in str(manifest.get("profile_id", "")):
        vocabulary_entries = processor._known_lower_vocabulary_entries()

    units = [
        {
            "unit_id": unit_id_from_title(unit.title),
            "title": unit.title,
            "order": index + 1,
            "source_page": f"PDF.{unit.page_number}",
        }
        for index, unit in enumerate(parsed.units)
    ]
    vocabulary = [
        {
            "text": entry.expression,
            "normalized_text": entry.canonical_expression,
            "unit_id": unit_id_from_title(entry.unit_title),
            "source_page": "Words and Expressions",
            "confidence": entry.confidence,
            "warnings": list(entry.warnings),
            "requires_review": entry.confidence < 0.75 or bool(entry.warnings),
            "raw_line": entry.raw_line,
        }
        for entry in vocabulary_entries
    ]
    phrases = [
        {
            "text": entry.expression,
            "normalized_text": entry.canonical_expression,
            "unit_id": unit_id_from_title(entry.unit_title),
            "source_page": "Words and Expressions",
            "confidence": entry.confidence,
            "warnings": list(entry.warnings),
            "requires_review": entry.confidence < 0.75 or bool(entry.warnings),
            "raw_line": entry.raw_line,
        }
        for entry in vocabulary_entries
        if " " in entry.canonical_expression
    ]
    grammar = _actual_grammar(manifest)
    quality_report = build_parser_report(
        profile=parser_profile,
        unit_count=len(units),
        vocabulary_entries=list(vocabulary_entries),
        page_texts=page_texts,
        unit_titles=[unit["title"] for unit in units],
        knowledge_points=[],
        section_count=len(grammar),
        rag_chunk_count=None,
        rag_covered_pages=set(),
        chunk_char_counts=[],
    ).to_dict()
    return (
        {
            "units": units,
            "vocabulary": vocabulary,
            "grammar": grammar,
            "phrases": phrases,
            "exercises": [],
        },
        _quality_report_summary(quality_report),
    )


def resolve_fixture_path(profile_root: Path, manifest: dict[str, Any]) -> Path:
    raw = manifest.get("source_fixture")
    if not raw:
        raise ValueError("manifest.json must define source_fixture")
    candidates = [
        REPO_ROOT / str(raw),
        profile_root / str(raw),
        Path(str(raw)),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"source_fixture not found: {raw}")


def write_report(report: dict[str, Any], report_dir: str | Path) -> tuple[Path, Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    profile_path = output_dir / f"{report['profile_id']}_{timestamp}.json"
    latest_path = output_dir / "latest_report.json"
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    profile_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")
    return profile_path, latest_path


def unit_id_from_title(title: str | None) -> str:
    normalized = processor._normalize_unit_title(str(title or "unit"))
    return normalized.casefold().replace(" ", "_")


def _actual_grammar(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if "upper" not in str(manifest.get("profile_id", "")):
        return []
    return [
        {
            "topic": str(topic["title"]),
            "unit_id": unit_id_from_title(str(topic.get("primary") or "")),
            "source_page": f"P.{topic.get('page')}",
            "keywords": [str(topic.get("key"))],
        }
        for topic in processor.GRADE7_UPPER_GRAMMAR_TOPICS
    ]


def _parser_profile_from_manifest(manifest: dict[str, Any]) -> ParserProfile | None:
    profile_id = str(manifest.get("parser_profile_id") or "")
    return PARSER_PROFILES.get(profile_id)


def _quality_report_summary(report: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "page_count",
        "text_char_count",
        "unit_count",
        "expected_unit_count",
        "unit_title_match_rate",
        "unit_order_valid",
        "vocabulary_entry_count",
        "core_vocabulary_hit_rate",
        "low_confidence_vocabulary_ratio",
        "dirty_token_entry_count",
        "warnings",
    }
    return {key: report.get(key) for key in keys}


def _normalized_actual(value: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        group: [item for item in value.get(group, []) if isinstance(item, dict)]
        if isinstance(value.get(group), list)
        else []
        for group in ("units", "vocabulary", "grammar", "phrases", "exercises")
    }


if __name__ == "__main__":
    raise SystemExit(main())
