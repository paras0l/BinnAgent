from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from scripts.validate_public_textbook_pack import validate_public_textbook_pack

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = ROOT_DIR / "books" / "public" / "pep_grade7" / "manifest.v2.json"
PUBLIC_TEXTBOOK_NAMESPACE = uuid.UUID("4d56df4b-005c-4f3c-8dc6-7a47b3f7d201")


def stable_seed_uuid(kind: str, stable_key: str) -> uuid.UUID:
    return uuid.uuid5(PUBLIC_TEXTBOOK_NAMESPACE, f"{kind}:{stable_key}")


def load_public_textbook_seed(manifest_path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    pack, warnings = validate_public_textbook_pack(manifest_path)
    if warnings:
        raise ValueError(f"public textbook pack has validation warnings: {warnings}")
    return _build_seed_payload(pack, manifest_path=manifest_path)


def _build_seed_payload(pack: dict[str, Any], *, manifest_path: Path) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for source in pack["sources"]:
        source_stable_id = source["stable_id"]
        source_id = stable_seed_uuid("source", source_stable_id)
        node_id_by_key = {
            node["stable_key"]: stable_seed_uuid("curriculum_node", node["stable_key"])
            for node in source["curriculum_nodes"]
        }
        point_id_by_key = {
            point["stable_key"]: stable_seed_uuid("knowledge_point", point["stable_key"])
            for point in source["knowledge_points"]
        }
        source_seed = dict(source["source_seed"])
        metadata = dict(source_seed.get("metadata") or {})
        metadata.update(
            {
                "source_kind": "public_textbook",
                "source_stable_id": source_stable_id,
                "default_pack_manifest": str(manifest_path.relative_to(ROOT_DIR)),
                "materialized_from": "public_textbook_pack_manifest.v2",
                "public_textbook_seed": True,
                "exercise_question_count": len(source["exercise_questions"]),
                "extraction_gap_count": len(source["extraction_gaps"]),
            }
        )
        sources.append(
            {
                "stable_id": source_stable_id,
                "id": source_id,
                "source_seed": {**source_seed, "metadata": metadata},
                "curriculum_nodes": [
                    _node_payload(node, source_id=source_id, node_id_by_key=node_id_by_key)
                    for node in source["curriculum_nodes"]
                ],
                "knowledge_points": [
                    _point_payload(
                        point,
                        source_id=source_id,
                        node_id_by_key=node_id_by_key,
                        point_id_by_key=point_id_by_key,
                        source_stable_id=source_stable_id,
                    )
                    for point in source["knowledge_points"]
                ],
                "exercise_questions": [
                    _question_payload(
                        question,
                        source_id=source_id,
                        node_id_by_key=node_id_by_key,
                        point_id_by_key=point_id_by_key,
                        source_stable_id=source_stable_id,
                    )
                    for question in source["exercise_questions"]
                ],
            }
        )
    return {"schema_version": pack["schema_version"], "sources": sources}


def _node_payload(
    node: dict[str, Any],
    *,
    source_id: uuid.UUID,
    node_id_by_key: dict[str, uuid.UUID],
) -> dict[str, Any]:
    return {
        "id": node_id_by_key[node["stable_key"]],
        "source_id": source_id,
        "parent_id": node_id_by_key.get(node["parent_key"]) if node.get("parent_key") else None,
        "node_type": node["node_type"],
        "title": node["title"],
        "subtitle": node.get("subtitle"),
        "ordinal": node["ordinal"],
        "start_page": node.get("start_page"),
        "end_page": node.get("end_page"),
        "estimated_minutes": node.get("estimated_minutes"),
        "learning_objectives": node.get("learning_objectives") or [],
    }


def _point_payload(
    point: dict[str, Any],
    *,
    source_id: uuid.UUID,
    node_id_by_key: dict[str, uuid.UUID],
    point_id_by_key: dict[str, uuid.UUID],
    source_stable_id: str,
) -> dict[str, Any]:
    content = dict(point.get("content") or {})
    content.update(
        {
            "origin": content.get("origin") or "curated_public_textbook_seed",
            "source_stable_id": source_stable_id,
            "curriculum_node_key": point["curriculum_node_key"],
            "stable_key": point["stable_key"],
        }
    )
    return {
        "id": point_id_by_key[point["stable_key"]],
        "source_id": source_id,
        "curriculum_node_id": node_id_by_key[point["curriculum_node_key"]],
        "canonical_key": point["stable_key"],
        "type": point["type"],
        "title": point["title"],
        "summary": point["summary"],
        "source_page": point["source_page"],
        "difficulty": point.get("difficulty", 0.2),
        "status": point.get("status", "published"),
        "content": content,
    }


def _question_payload(
    question: dict[str, Any],
    *,
    source_id: uuid.UUID,
    node_id_by_key: dict[str, uuid.UUID],
    point_id_by_key: dict[str, uuid.UUID],
    source_stable_id: str,
) -> dict[str, Any]:
    metadata = dict(question.get("metadata") or {})
    metadata.update(
        {
            "origin": metadata.get("origin") or "curated_public_textbook_seed",
            "source_stable_id": source_stable_id,
            "curriculum_node_key": question["curriculum_node_key"],
            "knowledge_point_key": question.get("knowledge_point_key"),
            "stable_key": question["stable_key"],
        }
    )
    return {
        "id": stable_seed_uuid("exercise_question", question["stable_key"]),
        "source_id": source_id,
        "curriculum_node_id": node_id_by_key[question["curriculum_node_key"]],
        "knowledge_point_id": point_id_by_key.get(question.get("knowledge_point_key")),
        "question_type": question["question_type"],
        "stem": question["stem"],
        "options": question.get("options") or [],
        "answer": question["answer"],
        "explanation": question["explanation"],
        "difficulty": question.get("difficulty", 0.3),
        "status": question.get("status", "published"),
        "metadata": metadata,
    }


def materialize_public_textbook_seed(
    connection: sa.engine.Connection,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, int]:
    seed = load_public_textbook_seed(manifest_path)
    counts = {"sources": 0, "curriculum_nodes": 0, "knowledge_points": 0, "exercise_questions": 0}
    for source in seed["sources"]:
        _upsert_source(connection, source)
        counts["sources"] += 1
        for node in source["curriculum_nodes"]:
            _upsert_curriculum_node(connection, node)
            counts["curriculum_nodes"] += 1
        for point in source["knowledge_points"]:
            _upsert_knowledge_point(connection, point)
            counts["knowledge_points"] += 1
        for question in source["exercise_questions"]:
            _upsert_exercise_question(connection, question)
            counts["exercise_questions"] += 1
    return counts


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _upsert_source(connection: sa.engine.Connection, source: dict[str, Any]) -> None:
    seed = source["source_seed"]
    connection.execute(
        sa.text(
            """
            INSERT INTO knowledge_sources
              (id, owner_learner_id, title, filename, publisher, edition, grade, volume,
               status, visibility, object_key, sha256, file_size, page_count, unit_count,
               knowledge_count, metadata)
            VALUES
              (:id, NULL, :title, :filename, :publisher, :edition, :grade, :volume,
               :status, :visibility, :object_key, :sha256, :file_size, :page_count,
               :unit_count, :knowledge_count, CAST(:metadata AS jsonb))
            ON CONFLICT (id) DO UPDATE SET
              title = EXCLUDED.title,
              filename = EXCLUDED.filename,
              publisher = EXCLUDED.publisher,
              edition = EXCLUDED.edition,
              grade = EXCLUDED.grade,
              volume = EXCLUDED.volume,
              status = EXCLUDED.status,
              visibility = EXCLUDED.visibility,
              object_key = EXCLUDED.object_key,
              sha256 = EXCLUDED.sha256,
              file_size = EXCLUDED.file_size,
              page_count = EXCLUDED.page_count,
              unit_count = EXCLUDED.unit_count,
              knowledge_count = EXCLUDED.knowledge_count,
              metadata = EXCLUDED.metadata,
              updated_at = now()
            """
        ).bindparams(
            id=source["id"],
            title=seed["title"],
            filename=seed["filename"],
            publisher=seed.get("publisher"),
            edition=seed.get("edition"),
            grade=seed["grade"],
            volume=seed.get("volume"),
            status=seed["status"],
            visibility=seed["visibility"],
            object_key=seed.get("object_key"),
            sha256=seed["sha256"],
            file_size=seed["file_size"],
            page_count=seed.get("page_count"),
            unit_count=seed["unit_count"],
            knowledge_count=seed["knowledge_count"],
            metadata=_json(seed["metadata"]),
        )
    )


def _upsert_curriculum_node(connection: sa.engine.Connection, node: dict[str, Any]) -> None:
    connection.execute(
        sa.text(
            """
            INSERT INTO curriculum_nodes
              (id, source_id, parent_id, node_type, title, subtitle, ordinal, start_page,
               end_page, estimated_minutes, learning_objectives)
            VALUES
              (:id, :source_id, :parent_id, :node_type, :title, :subtitle, :ordinal,
               :start_page, :end_page, :estimated_minutes, CAST(:learning_objectives AS jsonb))
            ON CONFLICT (id) DO UPDATE SET
              parent_id = EXCLUDED.parent_id,
              node_type = EXCLUDED.node_type,
              title = EXCLUDED.title,
              subtitle = EXCLUDED.subtitle,
              ordinal = EXCLUDED.ordinal,
              start_page = EXCLUDED.start_page,
              end_page = EXCLUDED.end_page,
              estimated_minutes = EXCLUDED.estimated_minutes,
              learning_objectives = EXCLUDED.learning_objectives,
              updated_at = now()
            """
        ).bindparams(
            **{
                **node,
                "learning_objectives": _json(node["learning_objectives"]),
            }
        )
    )


def _upsert_knowledge_point(connection: sa.engine.Connection, point: dict[str, Any]) -> None:
    connection.execute(
        sa.text(
            """
            INSERT INTO knowledge_points
              (id, source_id, curriculum_node_id, canonical_key, type, title, summary,
               source_page, difficulty, status, content)
            VALUES
              (:id, :source_id, :curriculum_node_id, :canonical_key, :type, :title,
               :summary, :source_page, :difficulty, :status, CAST(:content AS jsonb))
            ON CONFLICT (id) DO UPDATE SET
              curriculum_node_id = EXCLUDED.curriculum_node_id,
              canonical_key = EXCLUDED.canonical_key,
              type = EXCLUDED.type,
              title = EXCLUDED.title,
              summary = EXCLUDED.summary,
              source_page = EXCLUDED.source_page,
              difficulty = EXCLUDED.difficulty,
              status = EXCLUDED.status,
              content = EXCLUDED.content,
              updated_at = now()
            """
        ).bindparams(**{**point, "content": _json(point["content"])})
    )


def _upsert_exercise_question(connection: sa.engine.Connection, question: dict[str, Any]) -> None:
    connection.execute(
        sa.text(
            """
            INSERT INTO exercise_questions
              (id, source_id, curriculum_node_id, knowledge_point_id, question_type, stem,
               options, answer, explanation, difficulty, status, metadata)
            VALUES
              (:id, :source_id, :curriculum_node_id, :knowledge_point_id, :question_type,
               :stem, CAST(:options AS jsonb), :answer, :explanation, :difficulty,
               :status, CAST(:metadata AS jsonb))
            ON CONFLICT (id) DO UPDATE SET
              curriculum_node_id = EXCLUDED.curriculum_node_id,
              knowledge_point_id = EXCLUDED.knowledge_point_id,
              question_type = EXCLUDED.question_type,
              stem = EXCLUDED.stem,
              options = EXCLUDED.options,
              answer = EXCLUDED.answer,
              explanation = EXCLUDED.explanation,
              difficulty = EXCLUDED.difficulty,
              status = EXCLUDED.status,
              metadata = EXCLUDED.metadata,
              updated_at = now()
            """
        ).bindparams(
            **{
                **question,
                "options": _json(question["options"]),
                "metadata": _json(question["metadata"]),
            }
        )
    )
