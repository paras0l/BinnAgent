import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.knowledge import KnowledgePoint, KnowledgeSource, ParserReviewItem


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.fixture
def review_api_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _source() -> KnowledgeSource:
    source = KnowledgeSource(
        title="英语 七年级上册",
        filename="七年级上册.pdf",
        grade="grade-7",
        status="review_required",
        visibility="public",
        sha256="7" * 64,
        file_size=100,
        unit_count=12,
        knowledge_count=100,
        metadata_={
            "parser_report": {
                "unit_count": 12,
                "expected_unit_count": 12,
                "unit_title_match_rate": 1.0,
                "unit_order_valid": True,
                "section_coverage_rate": 1.0,
                "core_vocabulary_hit_rate": 1.0,
                "low_confidence_vocabulary_ratio": 0.0,
                "dirty_token_entry_count": 0,
                "source_page_coverage_rate": 1.0,
                "evidence_ref_coverage_rate": 1.0,
                "rag_chunk_count": 20,
                "rag_page_coverage_rate": 1.0,
                "chunk_avg_size": 360,
                "warnings": [],
            }
        },
    )
    source.id = uuid.uuid4()
    source.created_at = datetime.now(timezone.utc)
    return source


def _point(source_id: uuid.UUID) -> KnowledgePoint:
    point = KnowledgePoint(
        source_id=source_id,
        curriculum_node_id=uuid.uuid4(),
        canonical_key="vocabulary.hello",
        type="vocabulary",
        title="hello",
        summary="待校对词条。",
        source_page="Words and Expressions",
        status="draft",
        content={"requires_review": True, "confidence": 0.62},
    )
    point.id = uuid.uuid4()
    return point


def _item(
    source_id: uuid.UUID,
    *,
    target_id: uuid.UUID | None = None,
    severity: str = "warning",
    issue_type: str = "low_confidence",
) -> ParserReviewItem:
    item = ParserReviewItem(
        source_id=source_id,
        parser_run_id=uuid.uuid4(),
        target_type="knowledge_point" if target_id else "source",
        target_id=target_id,
        issue_type=issue_type,
        severity=severity,
        evidence_snapshot={"confidence": 0.62, "raw_line": "hello p.1"},
        suggested_fix={"action": "confirm_or_update"},
        decision="pending",
    )
    item.id = uuid.uuid4()
    item.created_at = datetime.now(timezone.utc)
    return item


@pytest.mark.asyncio
async def test_review_items_api_lists_with_filters_and_summary(client, review_api_session) -> None:
    learner_id = uuid.uuid4()
    source = _source()
    warning_item = _item(source.id, severity="warning")
    blocker_item = _item(
        source.id,
        severity="blocker",
        issue_type="quality_gate_blocker",
    )
    review_api_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _one(source),
            _many([warning_item]),
            _many([warning_item, blocker_item]),
        ]
    )

    response = await client.get(
        f"/api/knowledge/sources/{source.id}/review-items",
        params={
            "learner_id": str(learner_id),
            "severity": "warning",
            "parser_run_id": str(warning_item.parser_run_id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["issue_type"] == "low_confidence"
    assert payload["items"][0]["created_at"] is not None
    assert payload["summary"]["pending_review_count"] == 2
    assert payload["summary"]["pending_blocker_count"] == 1
    assert payload["source"]["pending_blocker_count"] == 1
    assert payload["source_quality_summary"]["pending_blocker_count"] == 1


@pytest.mark.asyncio
async def test_confirm_review_item_updates_decision_and_target(client, review_api_session) -> None:
    learner_id = uuid.uuid4()
    source = _source()
    point = _point(source.id)
    item = _item(source.id, target_id=point.id)
    review_api_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _one(source),
            _one(item),
            _one(point),
            _many([item]),
        ]
    )

    response = await client.post(
        f"/api/knowledge/sources/{source.id}/review-items/{item.id}/confirm",
        params={"learner_id": str(learner_id)},
        json={"review_note": "checked"},
    )

    assert response.status_code == 200
    assert item.decision == "confirmed"
    assert point.content["requires_review"] is False
    assert point.content["review_decision"] == "confirmed"
    assert source.status == "published"
    assert response.json()["source_quality_summary"]["quality_status"] == "published"


@pytest.mark.asyncio
async def test_update_review_item_safely_patches_knowledge_point(client, review_api_session) -> None:
    learner_id = uuid.uuid4()
    source = _source()
    point = _point(source.id)
    item = _item(source.id, target_id=point.id, issue_type="missing_source_page")
    review_api_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _one(source),
            _one(item),
            _one(point),
            _many([item]),
        ]
    )

    response = await client.post(
        f"/api/knowledge/sources/{source.id}/review-items/{item.id}/update",
        params={"learner_id": str(learner_id)},
        json={
            "patch": {
                "id": str(uuid.uuid4()),
                "title": "hello",
                "source_page": "P.95",
                "content": {"confidence": 0.95, "source_page": "P.95"},
            },
            "review_note": "fixed source page",
        },
    )

    assert response.status_code == 200
    assert item.decision == "updated"
    assert point.source_page == "P.95"
    assert point.id != response.json()["item"]["id"]
    assert point.content["confidence"] == 0.95


@pytest.mark.asyncio
async def test_ignore_blocker_requires_explicit_override(client, review_api_session) -> None:
    learner_id = uuid.uuid4()
    source = _source()
    item = _item(
        source.id,
        severity="blocker",
        issue_type="quality_gate_blocker",
    )
    review_api_session.execute = AsyncMock(
        side_effect=[_one(learner_id), _one(source), _one(item)]
    )

    response = await client.post(
        f"/api/knowledge/sources/{source.id}/review-items/{item.id}/ignore",
        params={"learner_id": str(learner_id)},
        json={"review_note": "not enough"},
    )

    assert response.status_code == 409
    assert item.decision == "pending"
