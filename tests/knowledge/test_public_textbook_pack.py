from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from scripts.validate_public_textbook_pack import (
    ALLOWED_KNOWLEDGE_TYPES,
    FORBIDDEN_FIELD_NAMES,
    _scan_for_forbidden_raw_text,
    validate_public_textbook_pack,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
PACK_MANIFEST_PATH = ROOT_DIR / "books" / "public" / "pep_grade7" / "manifest.v2.json"


def load_pack() -> tuple[dict, list[str]]:
    return validate_public_textbook_pack(PACK_MANIFEST_PATH)


def source_by_id(pack: dict, stable_id: str) -> dict:
    return next(source for source in pack["sources"] if source["stable_id"] == stable_id)


def unit_points(source: dict, node_key: str) -> list[dict]:
    return [
        point
        for point in source["knowledge_points"]
        if point["curriculum_node_key"] == node_key
    ]


def test_split_public_textbook_pack_passes_validator_without_density_warnings() -> None:
    pack, warnings = load_pack()

    assert pack["schema_version"] == "public_textbook_pack.v1"
    assert warnings == []


def test_manifest_references_split_source_curriculum_and_unit_files() -> None:
    manifest = json.loads(PACK_MANIFEST_PATH.read_text(encoding="utf-8"))
    base_dir = PACK_MANIFEST_PATH.parent

    assert manifest["schema_version"] == "public_textbook_pack_manifest.v2"
    assert manifest["deprecated_artifacts"] == ["books/public/pep_grade7_public_pack.v1.json"]
    assert (base_dir / manifest["extraction_gaps_path"]).exists()
    for source in manifest["sources"]:
        assert (base_dir / source["source_path"]).exists()
        assert (base_dir / source["curriculum_path"]).exists()
        assert len(source["unit_paths"]) == 12
        assert all((base_dir / path).exists() for path in source["unit_paths"])


def test_public_textbook_pack_covers_grade7_upper_and_lower_units() -> None:
    pack, _ = load_pack()
    upper = source_by_id(pack, "pep-grade7-upper-2024")
    lower = source_by_id(pack, "pep-grade7-lower-2024")

    assert len(upper["curriculum_nodes"]) == 12
    assert len(lower["curriculum_nodes"]) == 12
    assert upper["curriculum_nodes"][0]["title"] == "Starter Unit 1"
    assert upper["curriculum_nodes"][-1]["subtitle"] == "My favorite subject is science."
    assert lower["curriculum_nodes"][0]["subtitle"] == "Can you play the guitar?"
    assert lower["curriculum_nodes"][-1]["title"] == "Unit 12"


def test_every_unit_has_dense_supported_knowledge_types_and_overview() -> None:
    pack, _ = load_pack()
    for source in pack["sources"]:
        for node in source["curriculum_nodes"]:
            points = unit_points(source, node["stable_key"])
            type_counts = Counter(point["type"] for point in points)
            min_points = 8 if node["title"].startswith("Starter") else 12

            assert len(points) >= min_points
            assert type_counts["vocabulary"] >= 5
            assert type_counts["text_note"] >= 1
            assert any(
                point["type"] == "text_note"
                and point.get("content", {}).get("role") == "unit_overview"
                for point in points
            )
            assert set(type_counts) <= ALLOWED_KNOWLEDGE_TYPES
            assert "unit_overview" not in set(type_counts)


def test_public_source_seed_is_ready_for_existing_knowledge_models() -> None:
    pack, _ = load_pack()
    for source in pack["sources"]:
        seed = source["source_seed"]
        assert seed["visibility"] == "public"
        assert seed["owner_learner_id"] is None
        expected_status = "review_required" if source["stable_id"].endswith("lower-2024") else "published"
        assert seed["status"] == expected_status
        assert seed["unit_count"] == len(source["curriculum_nodes"])
        assert seed["knowledge_count"] == len(source["knowledge_points"])
        assert seed["metadata"]["source_kind"] == "public_textbook"
        assert seed["metadata"]["availability_status"] in {"available", "partially_available"}
        assert seed["metadata"]["default_pack_manifest"] == "books/public/pep_grade7/manifest.v2.json"


def test_references_and_stable_question_interactions_are_complete() -> None:
    pack, _ = load_pack()
    for source in pack["sources"]:
        node_keys = {node["stable_key"] for node in source["curriculum_nodes"]}
        point_keys = {point["stable_key"] for point in source["knowledge_points"]}
        assert len(source["exercise_questions"]) >= 36
        for point in source["knowledge_points"]:
            assert point["curriculum_node_key"] in node_keys
            assert "confidence" in point["content"]
            assert "requires_review" in point["content"]
            if point["content"].get("requires_review"):
                assert point["status"] == "draft"
        for question in source["exercise_questions"]:
            assert question["curriculum_node_key"] in node_keys
            assert question["knowledge_point_key"] in point_keys
            assert question["answer"] in question["options"]
            assert question["metadata"]["interaction"]["input_mode"] == "choice"
            assert question["metadata"]["copyright_note"].startswith("Generated checking item")
            assert question["metadata"]["generated_from"]["source_stable_id"] == source["stable_id"]


def test_upper_unit_6_contains_expanded_food_like_and_countability_content() -> None:
    pack, _ = load_pack()
    upper = source_by_id(pack, "pep-grade7-upper-2024")
    points = unit_points(upper, "pep-grade7-upper-2024:unit:09")
    titles = {point["title"] for point in points}
    summaries = " ".join(point["summary"] for point in points)
    exercises = [
        question
        for question in upper["exercise_questions"]
        if question["curriculum_node_key"] == "pep-grade7-upper-2024:unit:09"
    ]

    assert {"banana", "hamburger", "tomato", "milk", "bread", "rice"} <= titles
    assert {"think about", "How about ...?", "Do you like bananas?", "Does she like tomatoes?"} <= titles
    assert "可数名词与不可数名词" in titles
    assert "一般现在时 like/likes" in titles
    assert "like/likes" in summaries
    assert len(exercises) >= 3


def test_pack_does_not_include_raw_page_text_fields_or_large_text_blobs() -> None:
    pack, _ = load_pack()
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
    pack, _ = load_pack()
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
