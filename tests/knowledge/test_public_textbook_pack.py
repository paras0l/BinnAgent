from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_public_textbook_pack import (
    ALLOWED_KNOWLEDGE_TYPES,
    FORBIDDEN_FIELD_NAMES,
    _scan_for_forbidden_raw_text,
    _validate_json_schema,
    _validate_pack,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT_DIR / "books" / "public" / "pep_grade7_public_pack.v1.json"


def load_pack() -> dict:
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


def source_by_id(pack: dict, stable_id: str) -> dict:
    return next(source for source in pack["sources"] if source["stable_id"] == stable_id)


def test_public_textbook_pack_passes_validator() -> None:
    pack = load_pack()
    _validate_json_schema(pack)
    _validate_pack(pack)


def test_public_textbook_pack_covers_grade7_upper_and_lower_units() -> None:
    pack = load_pack()
    upper = source_by_id(pack, "pep-grade7-upper-2024")
    lower = source_by_id(pack, "pep-grade7-lower-2024")

    assert len(upper["curriculum_nodes"]) == 12
    assert len(lower["curriculum_nodes"]) == 12
    assert upper["curriculum_nodes"][0]["title"] == "Starter Unit 1"
    assert upper["curriculum_nodes"][-1]["subtitle"] == "My favorite subject is science."
    assert lower["curriculum_nodes"][0]["subtitle"] == "Can you play the guitar?"
    assert lower["curriculum_nodes"][-1]["title"] == "Unit 12"


def test_every_unit_has_text_note_overview_not_custom_type() -> None:
    pack = load_pack()
    for source in pack["sources"]:
        node_keys = {node["stable_key"] for node in source["curriculum_nodes"]}
        overview_node_keys = {
            point["curriculum_node_key"]
            for point in source["knowledge_points"]
            if point["type"] == "text_note"
            and point.get("content", {}).get("role") == "unit_overview"
        }
        point_types = {point["type"] for point in source["knowledge_points"]}

        assert overview_node_keys == node_keys
        assert "unit_overview" not in point_types
        assert point_types <= ALLOWED_KNOWLEDGE_TYPES


def test_public_source_seed_is_ready_for_existing_knowledge_models() -> None:
    pack = load_pack()
    for source in pack["sources"]:
        seed = source["source_seed"]
        assert seed["visibility"] == "public"
        assert seed["owner_learner_id"] is None
        assert seed["status"] == "published"
        assert seed["unit_count"] == len(source["curriculum_nodes"])
        assert seed["knowledge_count"] == len(source["knowledge_points"])
        assert seed["metadata"]["source_kind"] == "public_textbook"
        assert seed["metadata"]["availability_status"] == "available"


def test_references_and_stable_question_interactions_are_complete() -> None:
    pack = load_pack()
    for source in pack["sources"]:
        node_keys = {node["stable_key"] for node in source["curriculum_nodes"]}
        point_keys = {point["stable_key"] for point in source["knowledge_points"]}
        assert source["exercise_questions"]
        for point in source["knowledge_points"]:
            assert point["curriculum_node_key"] in node_keys
            if point["content"].get("requires_review"):
                assert point["status"] == "draft"
        for question in source["exercise_questions"]:
            assert question["curriculum_node_key"] in node_keys
            assert question["knowledge_point_key"] in point_keys
            assert question["answer"] in question["options"]
            assert question["metadata"]["interaction"]["input_mode"] == "choice"
            assert question["metadata"]["generated_from"]["source_stable_id"] == source["stable_id"]


def test_pack_does_not_include_raw_page_text_fields_or_large_text_blobs() -> None:
    pack = load_pack()
    _scan_for_forbidden_raw_text(pack)
    serialized_keys = set()

    def collect_keys(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                serialized_keys.add(key.lower())
                collect_keys(child)
        elif isinstance(value, list):
            for child in value:
                collect_keys(child)

    collect_keys(pack)
    assert serialized_keys.isdisjoint(FORBIDDEN_FIELD_NAMES)


def test_extraction_gaps_record_scanned_lower_pdf_and_non_default_content() -> None:
    pack = load_pack()
    lower = source_by_id(pack, "pep-grade7-lower-2024")
    all_gap_types = {
        gap["gap_type"]
        for source in pack["sources"]
        for gap in source["extraction_gaps"]
    }

    assert lower["source_seed"]["metadata"]["text_layer_status"] == "empty_text_layer_detected"
    assert "low_confidence_layout" in {gap["gap_type"] for gap in lower["extraction_gaps"]}
    assert "audio_required" in all_gap_types
    assert "copyright_sensitive_long_text" in all_gap_types
