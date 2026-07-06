import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.api import knowledge as knowledge_api
from src.main import app
from src.models.knowledge import KnowledgeSource, ParserRun


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.fixture
def knowledge_session():
    session = AsyncMock()
    added: list[object] = []
    session.add = MagicMock(side_effect=added.append)

    async def flush():
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    session.flush = AsyncMock(side_effect=flush)
    session.added_objects = added
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _source(learner_id: uuid.UUID) -> KnowledgeSource:
    source = KnowledgeSource(
        owner_learner_id=learner_id,
        title="英语教材",
        filename="book.pdf",
        grade="grade-7",
        status="uploaded",
        visibility="private",
        sha256="a" * 64,
        file_size=100,
        page_count=2,
        unit_count=0,
        knowledge_count=0,
        metadata_={"processing_status": "uploaded", "availability_status": "unavailable"},
    )
    source.id = uuid.uuid4()
    source.created_at = datetime.now(timezone.utc)
    return source


@pytest.mark.asyncio
async def test_ingest_job_returns_202_and_router_parser_run(client, knowledge_session, monkeypatch) -> None:
    learner_id = uuid.uuid4()
    source = _source(learner_id)
    source.metadata_.update(
        {
            "processing_status": "failed",
            "parse_quality_status": "failed",
            "quality_status": "failed",
            "error": "old parser failure",
            "parser_report": {"warnings": ["old failure"]},
            "parser_report_summary": {"warnings": ["old failure"]},
            "blocking_reasons": ["old failure"],
        }
    )
    scheduled: list[tuple[uuid.UUID, uuid.UUID]] = []

    def fake_schedule(background_tasks, *, source_id, parser_run_id):
        scheduled.append((source_id, parser_run_id))

    monkeypatch.setattr(knowledge_api, "_schedule_ingest_background_task", fake_schedule)
    knowledge_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(source), _one(None)])

    response = await client.post(
        f"/api/knowledge/sources/{source.id}/ingest?learner_id={learner_id}"
    )

    assert response.status_code == 202
    parser_run = next(item for item in knowledge_session.added_objects if isinstance(item, ParserRun))
    payload = response.json()
    assert parser_run.parser_id == "document-parser-router"
    assert payload["parser_run_id"] == str(parser_run.id)
    assert payload["processing_status"] == "queued"
    assert payload["quality_status"] is None
    assert source.metadata_["processing_status"] == "queued"
    assert source.metadata_["parse_quality_status"] == "pending"
    assert "error" not in source.metadata_
    assert "parser_report" not in source.metadata_
    assert "quality_status" not in source.metadata_
    assert "blocking_reasons" not in source.metadata_
    knowledge_session.commit.assert_awaited_once()
    assert scheduled == [(source.id, parser_run.id)]


@pytest.mark.asyncio
async def test_ingest_status_exposes_engine_and_quality_summary(client, knowledge_session) -> None:
    learner_id = uuid.uuid4()
    source = _source(learner_id)
    source.status = "completed"
    source.metadata_ = {
        "processing_status": "completed",
        "parse_quality_status": "needs_ocr",
        "availability_status": "partially_available",
        "selected_engine": "pypdf",
        "attempted_engines": ["markitdown", "pypdf"],
        "fallback_used": True,
        "document_quality": {
            "page_count": 2,
            "text_char_count": 40,
            "text_coverage_score": 0.12,
            "empty_page_ratio": 0.5,
            "block_count": 1,
            "heading_count": 0,
            "needs_ocr": True,
            "needs_review": True,
            "warnings": ["Document likely needs OCR for better extraction."],
        },
        "parser_report_summary": {"warnings": ["Document likely needs OCR for better extraction."]},
    }
    parser_run = ParserRun(
        source_id=source.id,
        parser_id="document-parser-router",
        parser_version="v1",
        status="completed",
        stage="completed",
        progress=100,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        quality_report={"selected_engine": "pypdf"},
    )
    parser_run.id = uuid.uuid4()
    knowledge_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(source), _one(parser_run)])

    response = await client.get(
        f"/api/knowledge/sources/{source.id}/ingest-status?learner_id={learner_id}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parse_quality_status"] == "needs_ocr"
    assert payload["availability_status"] == "partially_available"
    assert payload["selected_engine"] == "pypdf"
    assert payload["attempted_engines"] == ["markitdown", "pypdf"]
    assert payload["fallback_used"] is True
    assert payload["quality_summary"]["needs_ocr"] is True
    assert "文本层较弱" in payload["message"]
