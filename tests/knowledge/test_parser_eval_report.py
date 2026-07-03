from __future__ import annotations

import json
from datetime import datetime, timezone

from src.knowledge.parser_eval import (
    build_parser_evaluation_report,
    compare_with_baseline,
    evaluate_thresholds,
    load_golden_dataset,
    validate_expected_schema,
    write_baseline,
)


def test_build_parser_evaluation_report_applies_threshold_failures() -> None:
    expected = _expected_payload("hello")
    actual = _actual_payload("hello")

    report = build_parser_evaluation_report(
        profile_id="sample",
        parser_id="parser",
        parser_version="v1",
        expected=expected,
        actual=actual,
        started_at=datetime(2026, 7, 3, tzinfo=timezone.utc),
        baseline={"thresholds": {"duplicate_rate": {"max": 0.0}}},
    )

    assert report["status"] == "passed"
    assert report["metrics"]["vocabulary_recall"] == 1.0
    assert report["threshold_failures"] == []
    assert report["baseline_comparison"]["baseline_found"] is True

    failed = build_parser_evaluation_report(
        profile_id="sample",
        parser_id="parser",
        parser_version="v1",
        expected=expected,
        actual=_actual_payload("wrong"),
        started_at=datetime(2026, 7, 3, tzinfo=timezone.utc),
        baseline={"thresholds": {"vocabulary_recall": {"min": 1.0}}},
    )

    assert failed["status"] == "failed"
    assert failed["threshold_failures"] == [
        {
            "metric": "vocabulary_recall",
            "value": 0.0,
            "rule": "min",
            "expected": 1.0,
        }
    ]
    assert failed["failures"] == ["vocabulary_recall=0.0 violates min 1.0"]


def test_evaluate_thresholds_and_baseline_regression_direction() -> None:
    metrics = {
        "vocabulary_recall": 0.8,
        "dirty_token_rate": 0.2,
        "duplicate_rate": 0.1,
    }

    failures = evaluate_thresholds(
        metrics,
        {
            "vocabulary_recall": {"min": 0.9},
            "dirty_token_rate": {"max": 0.1},
        },
    )

    assert [failure["metric"] for failure in failures] == [
        "vocabulary_recall",
        "dirty_token_rate",
    ]

    comparison = compare_with_baseline(
        metrics,
        {
            "version": 1,
            "metrics": {
                "vocabulary_recall": 0.9,
                "dirty_token_rate": 0.1,
                "duplicate_rate": 0.05,
            },
            "thresholds": {
                "vocabulary_recall": {"min": 0.8},
                "dirty_token_rate": {"max": 0.2},
            },
        },
    )

    assert comparison["baseline_found"] is True
    assert comparison["metric_deltas"] == {
        "vocabulary_recall": -0.1,
        "dirty_token_rate": 0.1,
        "duplicate_rate": 0.05,
    }
    assert [item["metric"] for item in comparison["regressions"]] == [
        "vocabulary_recall",
        "dirty_token_rate",
        "duplicate_rate",
    ]


def test_write_baseline_updates_metrics_and_preserves_thresholds(tmp_path) -> None:
    baseline_dir = tmp_path / "baselines"
    existing = {
        "version": 3,
        "metrics": {"vocabulary_recall": 0.5},
        "thresholds": {"vocabulary_recall": {"min": 0.9}},
    }

    path = write_baseline(
        profile_id="sample",
        report={"metrics": {"vocabulary_recall": 1.0}},
        baseline_dir=baseline_dir,
        existing_baseline=existing,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["profile_id"] == "sample"
    assert payload["version"] == 3
    assert payload["metrics"] == {"vocabulary_recall": 1.0}
    assert payload["thresholds"] == {"vocabulary_recall": {"min": 0.9}}


def test_real_golden_dataset_has_valid_expected_schema() -> None:
    dataset = load_golden_dataset("pep_grade7_upper")

    assert dataset.manifest["parser_profile_id"] == "pep_grade7_upper_v1"
    assert validate_expected_schema(dataset.expected) == []
    assert len(dataset.expected["units"]) == 12
    assert dataset.expected["vocabulary"]


def _expected_payload(word: str) -> dict[str, list[dict[str, object]]]:
    return {
        "units": [],
        "vocabulary": [
            {
                "text": word,
                "normalized_text": word,
                "source_page": "P.1",
                "is_core": True,
            }
        ],
        "grammar": [],
        "phrases": [],
        "exercises": [],
    }


def _actual_payload(word: str) -> dict[str, list[dict[str, object]]]:
    return {
        "units": [],
        "vocabulary": [
            {
                "text": word,
                "normalized_text": word,
                "source_page": "P.1",
            }
        ],
        "grammar": [],
        "phrases": [],
        "exercises": [],
    }
