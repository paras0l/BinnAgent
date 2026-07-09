import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.knowledge import CurriculumNode, KnowledgePoint, KnowledgeSource


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _rows(values: list):
    result = MagicMock()
    result.all.return_value = values
    return result


@pytest.fixture
def quality_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _source() -> KnowledgeSource:
    source = KnowledgeSource(
        title="英语 七年级上册",
        filename="七年级上册.pdf",
        grade="grade-7",
        volume="upper",
        status="review_required",
        visibility="public",
        sha256="7" * 64,
        file_size=100,
        page_count=138,
        unit_count=12,
        knowledge_count=120,
        metadata_={
            "latest_parser_run_id": str(uuid.uuid4()),
            "parser_status": "completed",
            "quality_status": "review_required",
            "quality_score": {"status": "review_required", "overall_score": 0.91},
            "blocking_reasons": [],
            "pending_review_count": 1,
            "parser_report_summary": {
                "page_count": 138,
                "unit_count": 12,
                "requires_review_count": 1,
            },
            "parser_report": {
                "warnings": ["Parser review items are still pending."],
                "requires_review_count": 1,
            },
        },
    )
    source.id = uuid.uuid4()
    source.created_at = datetime.now(timezone.utc)
    return source


def _node(source_id: uuid.UUID) -> CurriculumNode:
    node = CurriculumNode(
        source_id=source_id,
        node_type="unit",
        title="Unit 1",
        ordinal=1,
        estimated_minutes=20,
    )
    node.id = uuid.uuid4()
    return node


def _point(source_id: uuid.UUID, node_id: uuid.UUID) -> KnowledgePoint:
    point = KnowledgePoint(
        source_id=source_id,
        curriculum_node_id=node_id,
        canonical_key="vocabulary.hello",
        type="vocabulary",
        title="hello",
        summary="问候语。",
        source_page="P.1",
        status="published",
        content={"requires_review": False},
    )
    point.id = uuid.uuid4()
    point.created_at = datetime.now(timezone.utc)
    return point


@pytest.mark.asyncio
async def test_overview_exposes_quality_fields(client, quality_session) -> None:
    learner_id = uuid.uuid4()
    source = _source()
    node = _node(source.id)
    point = _point(source.id, node.id)
    quality_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _many([source]),
            _one(source),
            _many([node]),
            _many([]),
            _many([point]),
            _many([]),
            _many([]),
            _rows([]),
        ]
    )

    response = await client.get(f"/api/learners/{learner_id}/knowledge-base")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["latest_parser_run_id"] == source.metadata_["latest_parser_run_id"]
    assert payload["source"]["parser_status"] == "completed"
    assert payload["source"]["quality_status"] == "review_required"
    assert payload["source"]["quality_score"]["overall_score"] == 0.91
    assert payload["source"]["pending_review_count"] == 1
    assert payload["source"]["parser_report_summary"]["page_count"] == 138
    assert payload["parser_evidence"]["quality_status"] == "review_required"
    assert payload["parser_evidence"]["report"]["requires_review_count"] == 1
