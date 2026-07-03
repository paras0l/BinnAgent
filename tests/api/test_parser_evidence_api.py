import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.config import settings
from src.main import app
from src.models.knowledge import CurriculumNode, KnowledgePoint, KnowledgeSource, ParserReviewItem


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.fixture(autouse=True)
def parser_evidence_settings_guard():
    original = (
        settings.debug_console_enabled,
        settings.debug_console_token,
        list(settings.debug_console_allowed_origins),
    )
    yield
    (
        settings.debug_console_enabled,
        settings.debug_console_token,
        settings.debug_console_allowed_origins,
    ) = original
    app.dependency_overrides.clear()


@pytest.fixture
def evidence_session():
    session = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    return session


def _source() -> KnowledgeSource:
    source = KnowledgeSource(
        title="英语 七年级上册",
        filename="grade7-upper.pdf",
        grade="grade-7",
        status="review_required",
        visibility="public",
        sha256="a" * 64,
        file_size=1024,
        metadata_={},
    )
    source.id = uuid.uuid4()
    return source


def _point(source_id: uuid.UUID, *, raw_line: str) -> KnowledgePoint:
    point = KnowledgePoint(
        source_id=source_id,
        curriculum_node_id=uuid.uuid4(),
        canonical_key="vocabulary.hello",
        type="vocabulary",
        title="hello",
        summary="问候语。",
        source_page="P.1",
        status="published",
        content={
            "origin": "unit_wordlist_sequence_parser",
            "parser_run_id": str(uuid.uuid4()),
            "source_page": "P.1",
            "raw_line": raw_line,
            "confidence": 0.62,
            "warnings": ["low confidence"],
            "schema_version": "v1",
        },
    )
    point.id = uuid.uuid4()
    return point


def _node(source_id: uuid.UUID) -> CurriculumNode:
    node = CurriculumNode(
        source_id=source_id,
        node_type="unit",
        title="Unit 1",
        ordinal=1,
    )
    node.id = uuid.uuid4()
    return node


def _review_item(
    source_id: uuid.UUID,
    target_id: uuid.UUID | None,
    *,
    issue_type: str = "missing_source_page",
) -> ParserReviewItem:
    item = ParserReviewItem(
        source_id=source_id,
        parser_run_id=uuid.uuid4(),
        target_type="knowledge_point" if target_id else "source",
        target_id=target_id,
        issue_type=issue_type,
        severity="blocker",
        evidence_snapshot={
            "source_page": "P.1",
            "raw_line": "hello p.1",
            "confidence": 0.62,
        },
        suggested_fix={"action": "update"},
        decision="pending",
    )
    item.id = uuid.uuid4()
    item.created_at = datetime.now(timezone.utc)
    return item


@pytest.mark.asyncio
async def test_parser_evidence_api_returns_target_evidence(
    client,
    evidence_session,
) -> None:
    source = _source()
    long_raw_line = "hello " * 120
    point = _point(source.id, raw_line=long_raw_line)
    review_item = _review_item(source.id, point.id)
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    evidence_session.execute = AsyncMock(
        side_effect=[
            _one(source),
            _one(point),
            _many([review_item]),
        ]
    )

    response = await client.get(
        f"/api/debug/textbook-sources/{source.id}/evidence",
        params={"target_type": "knowledge_point", "target_id": str(point.id)},
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["warnings"] == []
    item = payload["evidence"][0]
    assert item["target_type"] == "knowledge_point"
    assert item["target_id"] == str(point.id)
    assert item["source_page"] == "P.1"
    assert item["origin"] == "unit_wordlist_sequence_parser"
    assert item["confidence"] == 0.62
    assert item["review_item_ids"] == [str(review_item.id)]
    assert item["issue_types"] == ["missing_source_page"]


@pytest.mark.asyncio
async def test_parser_evidence_api_truncates_raw_text_excerpt(
    client,
    evidence_session,
) -> None:
    source = _source()
    point = _point(source.id, raw_line="x" * 800)
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    evidence_session.execute = AsyncMock(
        side_effect=[
            _one(source),
            _one(point),
            _many([]),
        ]
    )

    response = await client.get(
        f"/api/debug/textbook-sources/{source.id}/evidence",
        params={"target_type": "knowledge_point", "target_id": str(point.id)},
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    excerpt = response.json()["evidence"][0]["raw_text_excerpt"]
    assert len(excerpt) <= 500
    assert excerpt.endswith("...")


@pytest.mark.asyncio
async def test_parser_evidence_api_returns_404_when_target_not_in_source(
    client,
    evidence_session,
) -> None:
    source = _source()
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    evidence_session.execute = AsyncMock(side_effect=[_one(source), _one(None)])

    response = await client.get(
        f"/api/debug/textbook-sources/{source.id}/evidence",
        params={"target_type": "knowledge_point", "target_id": str(uuid.uuid4())},
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_parser_evidence_api_returns_empty_evidence_with_warning(
    client,
    evidence_session,
) -> None:
    source = _source()
    node = _node(source.id)
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    evidence_session.execute = AsyncMock(
        side_effect=[
            _one(source),
            _one(node),
            _many([]),
        ]
    )

    response = await client.get(
        f"/api/debug/textbook-sources/{source.id}/evidence",
        params={"target_type": "curriculum_node", "target_id": str(node.id)},
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence"] == []
    assert payload["warnings"] == ["No parser evidence found for target."]


@pytest.mark.asyncio
async def test_parser_evidence_api_can_query_review_issue_type(
    client,
    evidence_session,
) -> None:
    source = _source()
    review_item = _review_item(source.id, None, issue_type="quality_gate_blocker")
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    evidence_session.execute = AsyncMock(
        side_effect=[
            _one(source),
            _many([review_item]),
        ]
    )

    response = await client.get(
        f"/api/debug/textbook-sources/{source.id}/evidence",
        params={"issue_type": "quality_gate_blocker"},
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence"][0]["issue_types"] == ["quality_gate_blocker"]
    assert payload["evidence"][0]["review_item_ids"] == [str(review_item.id)]
