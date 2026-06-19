import uuid

from src.knowledge.processor import (
    GRADE7_UPPER_GRAMMAR_TOPICS,
    PEP_GRADE7_LOWER_UNITS,
    _known_knowledge,
    _parse_notes_on_the_text,
    _parse_pronunciation,
    _parse_unit_vocabulary,
)


class _Page:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class _Reader:
    def __init__(self, pages: list[str]) -> None:
        self.pages = [_Page(page) for page in pages]


def test_grade7_lower_fallback_covers_all_twelve_units_in_order() -> None:
    assert len(PEP_GRADE7_LOWER_UNITS) == 12
    assert PEP_GRADE7_LOWER_UNITS[0].title == "Unit 1"
    assert PEP_GRADE7_LOWER_UNITS[0].subtitle == "Can you play the guitar?"
    assert PEP_GRADE7_LOWER_UNITS[-1].title == "Unit 12"
    assert PEP_GRADE7_LOWER_UNITS[-1].page_number == 67


def test_known_grade7_unit_generates_traceable_draft_knowledge() -> None:
    source_id = uuid.uuid4()
    node_id = uuid.uuid4()

    [point] = _known_knowledge(source_id, node_id, "Unit 6")

    assert point.title == "Present progressive tense (I)"
    assert point.type == "grammar"
    assert point.status == "draft"
    assert point.content["origin"] == "verified_toc_fallback"
    assert point.content["requires_review"] is True


def test_unit_wordlist_parser_keeps_unit_page_and_expression_metadata() -> None:
    reader = _Reader(
        [""] * 7
        + [
            """Words and Expressions in Each Unit
Starter Unit 1
morning /ˈmɔːnɪŋ/ n. 早晨；上午 p.S1
Good morning! 早上好！ p.S1
Unit 1
name /neɪm/ n. 名字；名称 p.1
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
    assert entries[0].phonetic == "/ˈmɔːnɪŋ/"
    assert entries[0].meaning == "早晨；上午"
    assert entries[0].part_of_speech == "n."
    assert entries[0].lesson_page == "S1"
    assert entries[1].entry_kind == "phrase"


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


def test_grade7_upper_appendices_are_grouped_by_unit() -> None:
    pages = [""] * 70 + [
        "Notes on the Text 55 Starter Unit 1 Good morning! 1. greeting note "
        "Unit 1 My name’s Gina. 1. name note",
        "Notes on the Text 56 Unit 1 continued note Unit 2 This is my sister. family note",
        "Tapescripts",
        "Pronunciation 75 phoneme foundations",
        "Pronunciation 79 Starter Unit 1 vowel practice Unit 1 vowel contrast",
        "Grammar 85",
    ]
    reader = _Reader(pages)

    notes = _parse_notes_on_the_text(reader)
    pronunciation = _parse_pronunciation(reader)

    assert [section.unit_title for section in notes] == [
        "Starter Unit 1",
        "Unit 1",
        "Unit 2",
    ]
    assert "continued note" in notes[1].text
    assert pronunciation[0].unit_title is None
    assert pronunciation[0].text == "phoneme foundations"
    assert pronunciation[1].unit_title == "Starter Unit 1"
    assert pronunciation[2].unit_title == "Unit 1"


def test_grade7_upper_grammar_appendix_maps_every_topic_to_units() -> None:
    assert len(GRADE7_UPPER_GRAMMAR_TOPICS) == 16
    assert all(topic["primary"] in topic["related"] for topic in GRADE7_UPPER_GRAMMAR_TOPICS)
    assert {topic["key"] for topic in GRADE7_UPPER_GRAMMAR_TOPICS} >= {
        "noun-plurals",
        "articles",
        "simple-present-be",
        "simple-present-verbs",
        "yes-no-questions",
        "wh-questions",
    }
