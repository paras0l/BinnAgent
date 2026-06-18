import uuid

from src.knowledge.processor import (
    PEP_GRADE7_LOWER_UNITS,
    _known_knowledge,
)


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
