from pathlib import Path

from src.classroom.catalog import exercise_asset_path, grade7_upper_catalog, unit_catalog


def test_grade7_upper_catalog_covers_every_unit_and_vocabulary_source() -> None:
    catalog = grade7_upper_catalog()

    assert catalog["counts"] == {
        "units": 10,
        "core_vocabulary": 333,
        "primary_review_vocabulary": 349,
        "textbook_tasks": 74,
    }
    starter = unit_catalog(1)
    assert starter is not None
    assert len(starter["vocabulary"]) == 24
    assert len(starter["primary_review_vocabulary"]) == 48
    assert starter["vocabulary"][0]["term"] == "unit"
    assert starter["primary_review_vocabulary"][0]["term"] == "hello"
    assert starter["grammar_lab"]["title"] == "用合适的问候开启并结束对话"
    assert len(starter["grammar_lab"]["checks"]) == 3

    for unit in catalog["units"]:
        assert unit["grammar_lab"]["can_do"]
        assert len(unit["grammar_lab"]["forms"]) >= 3
        assert len(unit["grammar_lab"]["checks"]) == 3


def test_every_textbook_task_crop_is_a_real_webp_asset() -> None:
    catalog = grade7_upper_catalog()

    for unit in catalog["units"]:
        start, end = unit["printed_page_range"]
        assert len(unit["textbook_tasks"]) == end - start + 1
        assert [task["printed_page"] for task in unit["textbook_tasks"]] == list(
            range(start, end + 1)
        )
        for task in unit["textbook_tasks"]:
            path = exercise_asset_path(task["asset"])
            assert isinstance(path, Path)
            assert path.suffix == ".webp"
            assert path.stat().st_size > 20_000
