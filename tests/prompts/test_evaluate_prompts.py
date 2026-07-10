from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "evaluate_prompts.py"


def test_evaluate_prompts_single_prompt_outputs_metrics() -> None:
    result = _run_cli("--prompt-id", "writing_phrase.import", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["prompt_id"] == "writing_phrase.import"
    assert payload["case_count"] == 3
    assert payload["metrics"]["schema_pass_rate"] == 0.6667
    assert payload["metrics"]["repair_rate"] == 0.3333
    assert payload["metrics"]["fallback_rate"] == 0.3333
    assert payload["metrics"]["accepted_rate"] == 0.6667
    assert payload["metrics"]["review_required_rate"] == 0.3333


def test_evaluate_prompts_all_supports_multiple_eval_sets() -> None:
    result = _run_cli("--all", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    prompt_ids = {report["prompt_id"] for report in payload["reports"]}
    assert {
        "dictionary.lookup",
        "essay.scoring",
        "vocabulary.agent.extract",
        "vocabulary.detail_html_extract",
        "vocabulary.local_enrichment",
        "exercise.generate",
        "graph.feedback",
        "writing_phrase.import",
        "grammar.micro_lesson.structured",
        "expression_lab.ui_spec",
    }.issubset(prompt_ids)


def test_expression_lab_eval_exercises_all_prompt_outcome_paths() -> None:
    result = _run_cli("--prompt-id", "expression_lab.ui_spec", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["expectation_failures"] == []
    assert payload["case_count"] == 6
    outcomes = {
        (case["schema_validation_status"], case["decision"])
        for case in payload["cases"]
    }
    assert outcomes == {
        ("passed", "accepted"),
        ("repaired", "accepted"),
        ("fallback", "review_required"),
        ("failed", "rejected"),
    }
    rejected = next(
        case
        for case in payload["cases"]
        if case["case_id"] == "expression_lab_invalid_output_rejected_without_fallback"
    )
    assert rejected["fallback_used"] is False


def test_evaluate_prompts_fails_when_schema_pass_rate_below_threshold() -> None:
    result = _run_cli(
        "--prompt-id",
        "writing_phrase.import",
        "--min-schema-pass-rate",
        "0.9",
        "--json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["threshold_failures"] == [
        {
            "metric": "schema_pass_rate",
            "value": 0.6667,
            "rule": "min",
            "expected": 0.9,
        }
    ]


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
