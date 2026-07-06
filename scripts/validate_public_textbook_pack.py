#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT_DIR / "books" / "public" / "public_textbook_pack.schema.json"
MANIFEST_PATH = ROOT_DIR / "books" / "manifest.yaml"

ALLOWED_KNOWLEDGE_TYPES = {
    "vocabulary",
    "grammar",
    "phrase",
    "sentence_pattern",
    "pronunciation",
    "text_note",
}
EXPECTED_SOURCE_IDS = {"pep-grade7-upper-2024", "pep-grade7-lower-2024"}
FORBIDDEN_FIELD_NAMES = {
    "page_text",
    "raw_page_text",
    "full_text",
    "raw_pdf_text",
    "raw_pages",
    "tapescript",
    "tapescripts",
}
MAX_LONG_TEXT_CHARS = 1200
ORDINARY_UNIT_MIN_POINTS = 12
STARTER_UNIT_MIN_POINTS = 8
UNIT_MIN_VOCABULARY = 5


class PackValidationError(Exception):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a curated public textbook seed pack.")
    parser.add_argument("pack", type=Path, help="Path to v1 pack JSON or v2 split manifest.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        aggregate, warnings = validate_public_textbook_pack(args.pack)
    except PackValidationError as exc:
        print(f"public textbook pack validation failed: {exc}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    source_count = len(aggregate["sources"])
    print(f"public textbook pack validation passed: {args.pack} ({source_count} sources)")
    return 0


def validate_public_textbook_pack(path: Path) -> tuple[dict[str, Any], list[str]]:
    data = _load_json(path)
    _validate_json_schema(data)
    if data.get("schema_version") == "public_textbook_pack_manifest.v2":
        aggregate = _load_split_pack(path, data)
    elif data.get("schema_version") == "public_textbook_pack.v1":
        aggregate = data
    else:
        raise PackValidationError(f"unsupported schema_version: {data.get('schema_version')}")
    warnings: list[str] = []
    _validate_pack(aggregate, warnings=warnings)
    return aggregate, warnings


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise PackValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PackValidationError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PackValidationError(f"JSON root must be an object: {path}")
    return data


def _validate_json_schema(data: dict[str, Any]) -> None:
    try:
        import jsonschema
    except ImportError:
        return
    schema = _load_json(SCHEMA_PATH)
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path)
        suffix = f" at {location}" if location else ""
        raise PackValidationError(f"schema error{suffix}: {exc.message}") from exc


def _load_split_pack(manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    base_dir = manifest_path.resolve().parent
    sources: list[dict[str, Any]] = []
    global_gaps = _load_optional_gaps(base_dir, manifest)
    for source_ref in manifest.get("sources", []):
        source_path = _resolve_manifest_ref(base_dir, source_ref["source_path"])
        curriculum_path = _resolve_manifest_ref(base_dir, source_ref["curriculum_path"])
        source_file = _load_json(source_path)
        curriculum_file = _load_json(curriculum_path)
        _validate_json_schema(source_file)
        _validate_json_schema(curriculum_file)
        if source_file.get("stable_id") != source_ref["stable_id"]:
            raise PackValidationError(f"source id mismatch in {source_path}")
        if curriculum_file.get("source_stable_id") != source_ref["stable_id"]:
            raise PackValidationError(f"curriculum source id mismatch in {curriculum_path}")
        knowledge_points: list[dict[str, Any]] = []
        exercise_questions: list[dict[str, Any]] = []
        extraction_gaps: list[dict[str, Any]] = [
            gap for gap in global_gaps if gap.get("scope") == source_ref["stable_id"]
        ]
        seen_units: set[str] = set()
        for unit_path_text in source_ref.get("unit_paths", []):
            unit_path = _resolve_manifest_ref(base_dir, unit_path_text)
            unit_file = _load_json(unit_path)
            _validate_json_schema(unit_file)
            if unit_file.get("source_stable_id") != source_ref["stable_id"]:
                raise PackValidationError(f"unit source id mismatch in {unit_path}")
            unit_key = unit_file.get("curriculum_node_key")
            if unit_key in seen_units:
                raise PackValidationError(f"duplicate unit file for {unit_key}")
            seen_units.add(unit_key)
            knowledge_points.extend(unit_file.get("knowledge_points", []))
            exercise_questions.extend(unit_file.get("exercise_questions", []))
            extraction_gaps.extend(unit_file.get("extraction_gaps", []))
        sources.append(
            {
                "stable_id": source_ref["stable_id"],
                "source_seed": source_file["source_seed"],
                "curriculum_nodes": curriculum_file["curriculum_nodes"],
                "knowledge_points": knowledge_points,
                "exercise_questions": exercise_questions,
                "extraction_gaps": extraction_gaps,
            }
        )
    return {
        "schema_version": "public_textbook_pack.v1",
        "generated_from": manifest.get("generated_from", {}),
        "sources": sources,
    }


def _resolve_manifest_ref(base_dir: Path, ref: str) -> Path:
    path = (base_dir / ref).resolve()
    try:
        path.relative_to(base_dir)
    except ValueError as exc:
        raise PackValidationError(f"manifest path escapes pack directory: {ref}") from exc
    if not path.exists():
        raise PackValidationError(f"manifest referenced file does not exist: {ref}")
    return path


def _load_optional_gaps(base_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    ref = manifest.get("extraction_gaps_path")
    if not ref:
        return []
    path = _resolve_manifest_ref(base_dir, ref)
    data = _load_json(path)
    _validate_json_schema(data)
    return list(data.get("extraction_gaps", []))


def _validate_pack(data: dict[str, Any], warnings: list[str] | None = None) -> None:
    warnings = warnings if warnings is not None else []
    if data.get("schema_version") != "public_textbook_pack.v1":
        raise PackValidationError("aggregate schema_version must be public_textbook_pack.v1")
    _scan_for_forbidden_raw_text(data)

    sources = data.get("sources")
    if not isinstance(sources, list):
        raise PackValidationError("sources must be a list")
    source_ids = {source.get("stable_id") for source in sources if isinstance(source, dict)}
    missing_sources = EXPECTED_SOURCE_IDS - source_ids
    if missing_sources:
        raise PackValidationError(f"missing expected sources: {sorted(missing_sources)}")

    manifest_units = _manifest_units()
    for source in sources:
        _validate_source(source, manifest_units.get(source["stable_id"], []), warnings)


def _validate_source(
    source: dict[str, Any],
    expected_units: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    stable_id = source["stable_id"]
    seed = source["source_seed"]
    if seed.get("visibility") != "public" or seed.get("owner_learner_id") is not None:
        raise PackValidationError(f"{stable_id}: public source must not have an owner")
    if seed.get("metadata", {}).get("public_textbook_seed") is not True:
        raise PackValidationError(f"{stable_id}: metadata.public_textbook_seed must be true")

    nodes = source["curriculum_nodes"]
    points = source["knowledge_points"]
    questions = source["exercise_questions"]
    gaps = source["extraction_gaps"]

    _assert_unique(stable_id, "curriculum node", [node["stable_key"] for node in nodes])
    _assert_unique(stable_id, "knowledge point", [point["stable_key"] for point in points])
    _assert_unique(stable_id, "exercise question", [item["stable_key"] for item in questions])

    node_by_key = {node["stable_key"]: node for node in nodes}
    point_by_key = {point["stable_key"]: point for point in points}

    if expected_units:
        if len(nodes) != len(expected_units):
            raise PackValidationError(
                f"{stable_id}: expected {len(expected_units)} units, found {len(nodes)}"
            )
        for index, (node, expected) in enumerate(zip(nodes, expected_units, strict=True), start=1):
            if node["ordinal"] != index:
                raise PackValidationError(f"{stable_id}: unit ordinal mismatch at {node['title']}")
            for field in ("title", "subtitle"):
                if node.get(field) != expected.get(field):
                    raise PackValidationError(
                        f"{stable_id}: unit {index} {field} mismatch: {node.get(field)!r}"
                    )
            if node.get("start_page") != f"P.{expected['start_printed_page']}":
                raise PackValidationError(f"{stable_id}: unit {index} start_page mismatch")
            if node.get("end_page") != f"P.{expected['end_printed_page']}":
                raise PackValidationError(f"{stable_id}: unit {index} end_page mismatch")

    overview_units = {
        point["curriculum_node_key"]
        for point in points
        if point["type"] == "text_note" and point.get("content", {}).get("role") == "unit_overview"
    }
    missing_overview = set(node_by_key) - overview_units
    if missing_overview:
        raise PackValidationError(f"{stable_id}: missing unit overview for {sorted(missing_overview)}")

    if seed.get("unit_count") != len(nodes):
        raise PackValidationError(f"{stable_id}: source_seed.unit_count must match curriculum_nodes")
    if seed.get("knowledge_count") != len(points):
        raise PackValidationError(f"{stable_id}: source_seed.knowledge_count must match knowledge_points")

    points_by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in points:
        if point["curriculum_node_key"] not in node_by_key:
            raise PackValidationError(
                f"{stable_id}: knowledge point references missing node {point['curriculum_node_key']}"
            )
        if point["type"] not in ALLOWED_KNOWLEDGE_TYPES:
            raise PackValidationError(f"{stable_id}: unsupported knowledge type {point['type']}")
        content = point.get("content") or {}
        if content.get("requires_review") is True and point["status"] != "draft":
            raise PackValidationError(
                f"{stable_id}: review-required point must be draft: {point['stable_key']}"
            )
        if point["type"] == "text_note" and content.get("role") == "unit_overview":
            if point["type"] != "text_note":
                raise PackValidationError(f"{stable_id}: unit overview must use text_note")
        points_by_unit[point["curriculum_node_key"]].append(point)

    _validate_density(stable_id, nodes, points_by_unit, warnings)

    for question in questions:
        if question["curriculum_node_key"] not in node_by_key:
            raise PackValidationError(
                f"{stable_id}: exercise references missing node {question['curriculum_node_key']}"
            )
        point_key = question.get("knowledge_point_key")
        if point_key is not None and point_key not in point_by_key:
            raise PackValidationError(f"{stable_id}: exercise references missing point {point_key}")
        if question["question_type"] == "multiple_choice" and len(question.get("options", [])) < 2:
            raise PackValidationError(
                f"{stable_id}: multiple_choice must have at least two options: {question['stable_key']}"
            )
        if (
            question["question_type"] == "multiple_choice"
            and question["answer"] not in question.get("options", [])
        ):
            raise PackValidationError(
                f"{stable_id}: multiple_choice answer must be one of the options: {question['stable_key']}"
            )
        interaction = question.get("metadata", {}).get("interaction", {})
        if interaction.get("input_mode") not in {"choice", "text"}:
            raise PackValidationError(
                f"{stable_id}: exercise missing stable interaction metadata: {question['stable_key']}"
            )

    scopes = {gap["scope"] for gap in gaps}
    if stable_id.endswith("lower-2024") and not any(
        gap.get("gap_type") == "low_confidence_layout" for gap in gaps
    ):
        raise PackValidationError(f"{stable_id}: lower scanned PDF must record layout gap")
    invalid_scopes = scopes - set(node_by_key) - {stable_id}
    if invalid_scopes:
        raise PackValidationError(
            f"{stable_id}: extraction gap references unknown scope {sorted(invalid_scopes)}"
        )


def _validate_density(
    stable_id: str,
    nodes: list[dict[str, Any]],
    points_by_unit: dict[str, list[dict[str, Any]]],
    warnings: list[str],
) -> None:
    for node in nodes:
        unit_points = points_by_unit.get(node["stable_key"], [])
        threshold = STARTER_UNIT_MIN_POINTS if node["title"].startswith("Starter") else ORDINARY_UNIT_MIN_POINTS
        if len(unit_points) < threshold:
            warnings.append(
                f"{stable_id}: {node['stable_key']} has {len(unit_points)} knowledge points; expected >= {threshold}"
            )
        vocabulary_count = sum(1 for point in unit_points if point["type"] == "vocabulary")
        if vocabulary_count < UNIT_MIN_VOCABULARY:
            warnings.append(
                f"{stable_id}: {node['stable_key']} has {vocabulary_count} vocabulary points; expected >= {UNIT_MIN_VOCABULARY}"
            )


def _assert_unique(stable_id: str, label: str, values: list[str]) -> None:
    duplicates = [key for key, count in Counter(values).items() if count > 1]
    if duplicates:
        raise PackValidationError(f"{stable_id}: duplicate {label} stable_key values: {duplicates}")


def _scan_for_forbidden_raw_text(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = key.lower()
            if normalized_key in FORBIDDEN_FIELD_NAMES:
                raise PackValidationError(f"forbidden raw text field at {path}.{key}")
            _scan_for_forbidden_raw_text(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_for_forbidden_raw_text(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if len(value) > MAX_LONG_TEXT_CHARS:
            raise PackValidationError(f"long text value at {path} exceeds {MAX_LONG_TEXT_CHARS} chars")
        if _looks_like_page_dump(value):
            raise PackValidationError(f"value at {path} looks like raw page text")


def _looks_like_page_dump(value: str) -> bool:
    if len(value) < 500:
        return False
    unit_hits = len(re.findall(r"\b(?:Unit|Starter Unit|Grammar Focus|Listen and|Role-play)\b", value))
    page_ref_hits = len(re.findall(r"\bp\.(?:S?\d+|\d+)\b", value, flags=re.I))
    return unit_hits >= 4 or page_ref_hits >= 10


def _manifest_units() -> dict[str, list[dict[str, Any]]]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    books: dict[str, list[dict[str, Any]]] = {}
    current_id: str | None = None
    in_units = False
    current_unit: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 2 and line.startswith("- "):
            current_id = None
            in_units = False
            key, value = _split_key_value(line[2:])
            if key == "id":
                current_id = str(value)
                books[current_id] = []
            continue
        if current_id is None:
            continue
        if indent == 4 and line.startswith("id:"):
            _, value = _split_key_value(line)
            current_id = str(value)
            books.setdefault(current_id, [])
            continue
        if indent == 4 and line == "units:":
            in_units = True
            continue
        if indent == 4 and not line.startswith("units:"):
            in_units = False
            continue
        if in_units and indent == 6 and line.startswith("- "):
            current_unit = {}
            books[current_id].append(current_unit)
            key, value = _split_key_value(line[2:])
            current_unit[key] = value
            continue
        if in_units and indent == 8 and current_unit is not None:
            key, value = _split_key_value(line)
            current_unit[key] = value
    return books


def _split_key_value(line: str) -> tuple[str, Any]:
    key, _, raw_value = line.partition(":")
    value = raw_value.strip()
    if value.startswith('"') and value.endswith('"'):
        return key.strip(), value[1:-1]
    if value.isdigit():
        return key.strip(), int(value)
    return key.strip(), value


if __name__ == "__main__":
    raise SystemExit(main())
