from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "evaluate_textbook_parser.py"


def test_evaluate_textbook_parser_cli_outputs_json_report(tmp_path) -> None:
    golden_root = _write_golden_profile(tmp_path, actual_word="hello", expected_word="hello")
    report_dir = tmp_path / "reports"
    baseline_dir = tmp_path / "baselines"

    result = _run_cli(
        "--profile",
        "sample_profile",
        "--golden-dir",
        str(golden_root),
        "--baseline-dir",
        str(baseline_dir),
        "--report-dir",
        str(report_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["profile_id"] == "sample_profile"
    assert payload["status"] == "passed"
    assert payload["metrics"]["vocabulary_recall"] == 1.0
    assert payload["baseline_comparison"]["baseline_found"] is False
    assert (report_dir / "latest_report.json").exists()


def test_evaluate_textbook_parser_cli_updates_baseline(tmp_path) -> None:
    golden_root = _write_golden_profile(tmp_path, actual_word="hello", expected_word="hello")
    report_dir = tmp_path / "reports"
    baseline_dir = tmp_path / "baselines"

    result = _run_cli(
        "--profile",
        "sample_profile",
        "--golden-dir",
        str(golden_root),
        "--baseline-dir",
        str(baseline_dir),
        "--report-dir",
        str(report_dir),
        "--update-baseline",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    baseline = json.loads((baseline_dir / "sample_profile.json").read_text(encoding="utf-8"))
    assert baseline["metrics"]["vocabulary_recall"] == 1.0
    assert json.loads(result.stdout)["baseline_updated"].endswith("sample_profile.json")


def test_evaluate_textbook_parser_cli_fails_on_regression(tmp_path) -> None:
    golden_root = _write_golden_profile(tmp_path, actual_word="wrong", expected_word="hello")
    report_dir = tmp_path / "reports"
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir(parents=True)
    (baseline_dir / "sample_profile.json").write_text(
        json.dumps(
            {
                "profile_id": "sample_profile",
                "version": 1,
                "metrics": {"vocabulary_recall": 1.0},
                "thresholds": {},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_cli(
        "--profile",
        "sample_profile",
        "--golden-dir",
        str(golden_root),
        "--baseline-dir",
        str(baseline_dir),
        "--report-dir",
        str(report_dir),
        "--fail-on-regression",
        "--json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["baseline_comparison"]["regressions"] == [
        {
            "metric": "vocabulary_recall",
            "current": 0.0,
            "baseline": 1.0,
            "delta": -1.0,
        }
    ]


def test_evaluate_textbook_parser_cli_respects_separate_gate_flags(tmp_path) -> None:
    golden_root = _write_golden_profile(tmp_path, actual_word="wrong", expected_word="hello")
    report_dir = tmp_path / "reports"
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir(parents=True)
    (baseline_dir / "sample_profile.json").write_text(
        json.dumps(
            {
                "profile_id": "sample_profile",
                "version": 1,
                "metrics": {"vocabulary_recall": 0.0},
                "thresholds": {"vocabulary_recall": {"min": 1.0}},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    regression_only = _run_cli(
        "--profile",
        "sample_profile",
        "--golden-dir",
        str(golden_root),
        "--baseline-dir",
        str(baseline_dir),
        "--report-dir",
        str(report_dir),
        "--fail-on-regression",
        "--json",
    )
    threshold_only = _run_cli(
        "--profile",
        "sample_profile",
        "--golden-dir",
        str(golden_root),
        "--baseline-dir",
        str(baseline_dir),
        "--report-dir",
        str(report_dir),
        "--fail-on-threshold",
        "--json",
    )

    assert regression_only.returncode == 0
    assert json.loads(regression_only.stdout)["threshold_failures"]
    assert json.loads(regression_only.stdout)["baseline_comparison"]["regressions"] == []
    assert threshold_only.returncode == 1


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def _write_golden_profile(
    tmp_path: Path,
    *,
    actual_word: str,
    expected_word: str,
) -> Path:
    profile_root = tmp_path / "golden" / "sample_profile"
    profile_root.mkdir(parents=True)
    (profile_root / "manifest.json").write_text(
        json.dumps(
            {
                "profile_id": "sample_profile",
                "book_title": "Sample",
                "parser_profile_id": "sample_profile_v1",
                "source_fixture": "actual.json",
                "version": 1,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (profile_root / "actual.json").write_text(
        json.dumps(
            {
                "actual": _actual_payload(actual_word),
                "quality_report_summary": {"unit_count": 1},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(profile_root / "units.expected.json", [])
    _write_json(profile_root / "vocabulary.expected.json", [_expected_vocabulary(expected_word)])
    _write_json(profile_root / "grammar.expected.json", [])
    _write_json(profile_root / "phrases.expected.json", [])
    _write_json(profile_root / "exercises.expected.json", [])
    return tmp_path / "golden"


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


def _expected_vocabulary(word: str) -> dict[str, object]:
    return {
        "text": word,
        "normalized_text": word,
        "unit_id": "unit_1",
        "part_of_speech": "n.",
        "chinese_meaning": "测试",
        "source_page": "P.1",
        "is_core": True,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
