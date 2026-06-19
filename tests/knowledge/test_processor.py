import uuid

from src.knowledge.processor import (
    PEP_GRADE7_LOWER_UNITS,
    _known_knowledge,
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
    assert entries[0].lesson_page == "S1"
    assert entries[1].entry_kind == "phrase"
