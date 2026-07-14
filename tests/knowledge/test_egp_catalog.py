import csv
from pathlib import Path

import pytest

from src.grammar.egp_catalog import load_egp_catalog


FIELDS = [
    "#",
    "SuperCategory",
    "SubCategory",
    "Level",
    "Lexical Range",
    "guideword",
    "Can-do statement",
    "Example",
    "type",
]


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _row(external_id: int, *, example: str) -> dict[str, str]:
    return {
        "#": str(external_id),
        "SuperCategory": "ADJECTIVES",
        "SubCategory": "combining",
        "Level": "A1",
        "Lexical Range": "limited",
        "guideword": "FORM: TEST",
        "Can-do statement": "Can use a test structure.",
        "Example": example,
        "type": "FORM",
    }


def test_catalog_selects_only_examples_with_cefr_learner_metadata(tmp_path: Path):
    path = tmp_path / "egp.csv"
    _write(path, [
        _row(1, example="A valid example. (A1 BREAKTHROUGH; 2007; Polish; Pass)"),
        _row(2, example="Metadata without a CEFR level. (Polish)"),
        _row(3, example=""),
    ])

    catalog = load_egp_catalog(path, expected_count=1)

    assert [entry.external_id for entry in catalog.entries] == [1]
    assert catalog.source_row_count == 3
    assert catalog.rows_with_examples == 2
    assert catalog.exclusion_count == 2


def test_catalog_splits_multiple_examples(tmp_path: Path):
    path = tmp_path / "egp.csv"
    _write(path, [_row(1, example="First. (A1; Pass)\n\nSecond. (A2; Pass)")])

    catalog = load_egp_catalog(path, expected_count=1)

    assert catalog.entries[0].examples == ["First. (A1; Pass)", "Second. (A2; Pass)"]


def test_catalog_rejects_unexpected_snapshot_count(tmp_path: Path):
    path = tmp_path / "egp.csv"
    _write(path, [_row(1, example="A valid example. (A1; Pass)")])

    with pytest.raises(ValueError, match="Expected 1211"):
        load_egp_catalog(path)
