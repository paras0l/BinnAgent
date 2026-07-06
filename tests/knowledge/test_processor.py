import uuid

from src.knowledge.processor import (
    ParsedUnit,
    ParsedVocabularyEntry,
    _merge_manifest_units,
    _node_for_candidate,
    _parse_unit_vocabulary,
    _vocabulary_entry_requires_review,
)
from src.knowledge.parser_profiles import find_book_manifest, profile_for_source
from src.knowledge.parser_report import build_parser_report
from src.models.knowledge import CurriculumNode


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


def test_profile_for_source_recovers_pep_grade7_profiles_for_real_upload_names() -> None:
    manifest, profile = profile_for_source("义务教育教科书·英语七年级下册.pdf")

    assert manifest is not None
    assert manifest.id == "pep-grade7-lower-2024"
    assert manifest.units[0].subtitle == "Can you play the guitar?"
    assert profile is not None
    assert profile.id == "pep_grade7_lower_v1"
    assert profile.expected_unit_count == 12
    assert profile.min_vocabulary_count == 220


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
    assert manifest.units[0].subtitle == ""
    assert resolved_manifest == manifest
    assert profile is None
    assert find_book_manifest("missing.pdf", manifest_path=manifest_path) is None


def test_manifest_units_override_noisy_extracted_subtitles() -> None:
    manifest, _profile = profile_for_source("义务教育教科书·英语七年级上册.pdf")
    assert manifest is not None

    parsed = (
        ParsedUnit("Starter Unit 1", "2a Listen and repeat. 听录音并跟读。", 12),
        ParsedUnit("Starter Unit 2", "2a Listen and repeat. 听录音并跟读。", 16),
    )

    merged = _merge_manifest_units(parsed, manifest)

    assert [(item.title, item.subtitle) for item in merged[:3]] == [
        ("Starter Unit 1", "Good morning!"),
        ("Starter Unit 2", "What's this in English?"),
        ("Starter Unit 3", "What color is it?"),
    ]
    assert merged[0].page_number == 12


def test_multiword_vocabulary_without_phonetic_can_be_published() -> None:
    phrase = ParsedVocabularyEntry(
        unit_title="Unit 1",
        expression="speak English",
        canonical_expression="speak english",
        unit_order=8,
        raw_line="speak English 说英语",
        confidence=0.76,
        warnings=("missing_phonetic",),
    )
    word = ParsedVocabularyEntry(
        unit_title="Unit 1",
        expression="hello",
        canonical_expression="hello",
        unit_order=1,
        raw_line="hello 你好",
        confidence=0.76,
        warnings=("missing_phonetic",),
    )

    assert _vocabulary_entry_requires_review(phrase) is False
    assert _vocabulary_entry_requires_review(word) is True


def test_node_for_candidate_matches_unit_mentions_inside_title() -> None:
    source_id = uuid.uuid4()
    unit_6 = CurriculumNode(
        source_id=source_id,
        node_type="unit",
        title="Unit 6",
        ordinal=6,
        start_page="32",
        end_page="32",
        learning_objectives=[],
    )
    unit_9 = CurriculumNode(
        source_id=source_id,
        node_type="unit",
        title="Unit 9",
        ordinal=9,
        start_page="50",
        end_page="50",
        learning_objectives=[],
    )
    unit_6.id = uuid.uuid4()
    unit_9.id = uuid.uuid4()
    nodes = [unit_6, unit_9]

    node = _node_for_candidate(
        "Unit 6 pronunciation",
        85,
        nodes,
        {item.title: item for item in nodes},
    )

    assert node == unit_6


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
