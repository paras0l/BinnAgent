import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.knowledge import KnowledgePoint, KnowledgeSource


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalar(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.fixture
def review_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _healthy_report(pending_count: int) -> dict:
    return {
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
        "requires_review_count": pending_count,
        "rag_chunk_count": 30,
        "rag_page_coverage_rate": 1.0,
        "chunk_avg_size": 420,
        "warnings": [],
    }


def _source(report: dict) -> KnowledgeSource:
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
        metadata_={"parser_report": report},
    )
    source.id = uuid.uuid4()
    return source


def _point(source_id: uuid.UUID) -> KnowledgePoint:
    point = KnowledgePoint(
        source_id=source_id,
        curriculum_node_id=uuid.uuid4(),
        canonical_key="vocabulary.hello",
        type="vocabulary",
        title="hello",
        summary="待校对词条。",
        source_page="P.1",
        status="draft",
        content={"requires_review": True, "confidence": 0.62},
    )
    point.id = uuid.uuid4()
    return point


@pytest.mark.asyncio
async def test_review_recalculates_quality_gate_to_publish(client, review_session) -> None:
    learner_id = uuid.uuid4()
    source = _source(_healthy_report(1))
    point = _point(source.id)
    review_session.execute = AsyncMock(
        side_effect=[_one(learner_id), _one(point), _scalar(0), _one(source), _many([])]
    )

    response = await client.patch(
        f"/api/learners/{learner_id}/knowledge-base/review-items/{point.id}",
        json={"action": "confirm"},
    )

    assert response.status_code == 200
    assert source.status == "completed"
    assert source.metadata_["quality_status"] == "published"
    assert source.metadata_["pending_review_count"] == 0
    assert source.metadata_["parser_report"]["requires_review_count"] == 0


@pytest.mark.asyncio
async def test_review_ignore_cannot_bypass_blocking_quality_reasons(
    client,
    review_session,
) -> None:
    learner_id = uuid.uuid4()
    report = {**_healthy_report(1), "source_page_coverage_rate": 0.3}
    source = _source(report)
    point = _point(source.id)
    review_session.execute = AsyncMock(
        side_effect=[_one(learner_id), _one(point), _scalar(0), _one(source), _many([])]
    )

    response = await client.patch(
        f"/api/learners/{learner_id}/knowledge-base/review-items/{point.id}",
        json={"action": "ignore", "note": "不是教材词条"},
    )

    assert response.status_code == 200
    assert point.status == "ignored"
    assert source.status == "completed"
    assert source.metadata_["quality_status"] == "blocked"
    assert source.metadata_["availability_status"] == "unavailable"
    assert source.metadata_["blocking_reasons"] == [
        "Source page coverage is too low for safe learning use."
    ]
