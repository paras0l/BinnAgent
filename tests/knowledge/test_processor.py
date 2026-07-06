from src.knowledge.processor import _parse_unit_vocabulary
from src.knowledge.parser_profiles import find_book_manifest, profile_for_source
from src.knowledge.parser_report import build_parser_report


class _Page:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class _Reader:
    def __init__(self, pages: list[str]) -> None:
        self.pages = [_Page(page) for page in pages]


def test_unit_wordlist_parser_keeps_only_unit_expression_and_order() -> None:
    reader = _Reader(
        [""] * 7
        + [
            """Words and Expressions in Each Unit
Starter Unit 1
morning /ˈmɔːnɪŋ/ n. 早晨 p.S1
Good morning! 早上好！ p.S1
Unit 1
name /neɪm/ n. name p.1
"""
        ]
        + ["Vocabulary Index"]
    )

    entries = _parse_unit_vocabulary(reader)

    assert [(item.unit_title, item.expression) for item in entries] == [
        ("Starter Unit 1", "morning"),
        ("Starter Unit 1", "Good morning!"),
        ("Unit 1", "name"),
    ]
    assert [item.unit_order for item in entries] == [1, 2, 1]
    assert entries[0].raw_line.startswith("morning")
    assert entries[0].confidence >= 0.9
    assert entries[1].raw_line == "Good morning! 早上好！"


def test_vocabulary_expression_normalizes_pdf_text_layer_artifacts() -> None:
    reader = _Reader(
        [""] * 7
        + [
            """Words and Expressions in Each Unit
Unit 1
To m /tɒm/ 汤姆 p.2
Unit 3
Y ou’re welcome. 别客气。 p.14
Unit 9
/T_hursday /θɜːzdeɪ/ n. 星期四 p.52
"""
        ]
        + ["Vocabulary Index"]
    )

    entries = _parse_unit_vocabulary(reader)

    assert [entry.expression for entry in entries] == ["Tom", "You’re welcome.", "Thursday"]


def test_profile_for_source_has_no_grade_specific_fallbacks() -> None:
    assert profile_for_source("legacy-upper.pdf") == (None, None)
    assert profile_for_source("legacy-lower.pdf") == (None, None)


def test_manifest_parser_accepts_custom_manifest_without_builtin_profile(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        """books:
  - id: custom-book
    filename: "custom.pdf"
    parser_profile: "custom_profile"
    expected:
      unit_count: 2
      min_vocabulary_count: 10
    units:
      - title: "Unit A"
      - title: "Unit B"
""",
        encoding="utf-8",
    )

    manifest = find_book_manifest("custom.pdf", manifest_path=manifest_path)
    resolved_manifest, profile = profile_for_source("custom.pdf", manifest_path=manifest_path)

    assert manifest is not None
    assert manifest.id == "custom-book"
    assert manifest.expected_unit_count == 2
    assert manifest.unit_titles == ("Unit A", "Unit B")
    assert resolved_manifest == manifest
    assert profile is None
    assert find_book_manifest("missing.pdf", manifest_path=manifest_path) is None


def test_parser_quality_report_flags_dirty_tokens_and_low_confidence() -> None:
    reader = _Reader(
        [""] * 7
        + [
            """Words and Expressions in Each Unit
Unit 1
telephone number 电话号码 p.5
"""
        ]
        + ["Vocabulary Index Page PB 9594"]
    )
    entries = _parse_unit_vocabulary(reader)

    report = build_parser_report(
        profile=None,
        unit_count=1,
        vocabulary_entries=entries,
        page_texts=[page.extract_text() for page in reader.pages],
    )

    assert entries[0].raw_line == "telephone number 电话号码"
    assert entries[0].confidence < 0.9
    assert report.low_confidence_entries == 0
    assert report.warnings == ["Dirty PDF tokens were detected in extracted text."]
