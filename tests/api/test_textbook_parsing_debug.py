import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import debug as debug_api
from src.api import deps
from src.config import settings
from src.main import app
from src.models.knowledge import KnowledgeSource, ParserReviewItem, ParserRun


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _count(value: int):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


class _Summary:
    pending_review_count = 0
    pending_blocker_count = 0
    review_warning_count = 0


@pytest.fixture(autouse=True)
def debug_textbook_settings_guard():
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
def debug_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    return session


def _source() -> KnowledgeSource:
    now = datetime.now(timezone.utc)
    source = KnowledgeSource(
        title="英语 七年级上册",
        filename="grade7-upper.pdf",
        grade="grade-7",
        status="review_required",
        visibility="public",
        sha256="a" * 64,
        file_size=1024,
        page_count=138,
        unit_count=12,
        knowledge_count=120,
        metadata_={
            "latest_parser_run_id": str(uuid.uuid4()),
            "parser_status": "completed",
            "quality_status": "review_required",
            "quality_score": {
                "overall_score": 0.88,
                "status": "review_required",
                "blocking_reasons": ["Parser review blockers are still pending."],
                "warnings": ["Parser review items are still pending."],
            },
            "blocking_reasons": ["Parser review blockers are still pending."],
            "pending_review_count": 2,
            "pending_blocker_count": 1,
            "review_warning_count": 1,
            "parser_report": _quality_report(),
        },
    )
    source.id = uuid.uuid4()
    source.created_at = now - timedelta(days=1)
    source.updated_at = now
    return source


def _parser_run(source_id: uuid.UUID, *, status: str = "completed") -> ParserRun:
    now = datetime.now(timezone.utc)
    run = ParserRun(
        source_id=source_id,
        parser_id="pypdf+manifest-profile",
        parser_version="v1",
        status=status,
        started_at=now - timedelta(seconds=2),
        completed_at=now,
        quality_report=_quality_report(),
        quality_score={
            "overall_score": 0.88,
            "status": "review_required",
            "blocking_reasons": ["Parser review blockers are still pending."],
            "warnings": ["Parser review items are still pending."],
        },
        artifact_refs={
            "curriculum_node_count": 12,
            "knowledge_point_count": 120,
            "rag_chunk_count": 42,
            "review_item_count": 2,
        },
    )
    run.id = uuid.uuid4()
    run.created_at = now - timedelta(seconds=3)
    run.updated_at = now
    return run


def _review_item(
    source_id: uuid.UUID,
    parser_run_id: uuid.UUID,
    *,
    severity: str = "warning",
    issue_type: str = "low_confidence",
) -> ParserReviewItem:
    item = ParserReviewItem(
        source_id=source_id,
        parser_run_id=parser_run_id,
        target_type="knowledge_point",
        target_id=uuid.uuid4(),
        issue_type=issue_type,
        severity=severity,
        evidence_snapshot={"source_page": "P.1", "raw_line": "hello p.1"},
        suggested_fix={"action": "confirm_or_update"},
        decision="pending",
    )
    item.id = uuid.uuid4()
    item.created_at = datetime.now(timezone.utc)
    return item


def _quality_report() -> dict:
    return {
        "page_count": 138,
        "text_char_count": 24000,
        "avg_text_chars_per_page": 173.9,
        "empty_page_ratio": 0.01,
        "has_text_layer": True,
        "is_scanned_pdf_suspected": False,
        "unit_count": 12,
        "expected_unit_count": 12,
        "unit_title_match_rate": 1.0,
        "unit_order_valid": True,
        "section_count": 18,
        "section_coverage_rate": 1.0,
        "vocabulary_entry_count": 320,
        "expected_min_vocabulary_count": 300,
        "core_vocabulary_hit_rate": 0.96,
        "low_confidence_vocabulary_ratio": 0.03,
        "dirty_token_entry_count": 0,
        "knowledge_count_by_type": {"vocabulary": 100, "grammar": 20},
        "source_page_coverage_rate": 0.98,
        "evidence_ref_coverage_rate": 0.92,
        "duplicate_knowledge_count": 0,
        "requires_review_count": 2,
        "pending_blocker_count": 1,
        "review_warning_count": 1,
        "rag_chunk_count": 42,
        "rag_page_coverage_rate": 0.97,
        "chunk_avg_size": 360,
        "warnings": ["Parser review items are still pending."],
    }


@pytest.mark.asyncio
async def test_debug_textbook_sources_requires_debug_access(client, debug_session) -> None:
    settings.debug_console_enabled = False

    response = await client.get("/api/debug/textbook-sources")

    assert response.status_code == 404
    debug_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_debug_textbook_sources_list_returns_quality_summary(
    client,
    debug_session,
) -> None:
    source = _source()
    run = _parser_run(source.id)
    source.metadata_["latest_parser_run_id"] = str(run.id)
    blocker = _review_item(
        source.id,
        run.id,
        severity="blocker",
        issue_type="missing_source_page",
    )
    warning = _review_item(source.id, run.id)
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    debug_session.execute = AsyncMock(
        side_effect=[
            _count(1),
            _many([source]),
            _many([run]),
            _many([blocker, warning]),
        ]
    )

    response = await client.get(
        "/api/debug/textbook-sources",
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    summary = payload["sources"][0]
    assert summary["source_id"] == str(source.id)
    assert summary["quality_status"] == "review_required"
    assert summary["overall_score"] == 0.88
    assert summary["latest_parser_run_id"] == str(run.id)
    assert summary["latest_parser_version"] == "v1"
    assert summary["pending_review_count"] == 2
    assert summary["pending_blocker_count"] == 1


@pytest.mark.asyncio
async def test_debug_parsing_report_returns_quality_report_score_and_metric_groups(
    client,
    debug_session,
) -> None:
    source = _source()
    run = _parser_run(source.id)
    source.metadata_["latest_parser_run_id"] = str(run.id)
    blocker = _review_item(
        source.id,
        run.id,
        severity="blocker",
        issue_type="missing_source_page",
    )
    warning = _review_item(source.id, run.id)
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    debug_session.execute = AsyncMock(
        side_effect=[
            _one(source),
            _one(run),
            _many([blocker, warning]),
        ]
    )

    response = await client.get(
        f"/api/debug/textbook-sources/{source.id}/parsing-report",
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["quality_score"]["overall_score"] == 0.88
    assert payload["quality_report"]["page_count"] == 138
    assert payload["quality_metrics_by_group"]["intake"]["page_count"] == 138
    assert payload["quality_metrics_by_group"]["rag"]["rag_chunk_count"] == 42
    assert payload["review_summary_by_issue_type"]["missing_source_page"] == 1
    assert payload["review_summary_by_severity"]["blocker"] == 1
    assert payload["parser_artifacts"]["rag_chunk_count"] == 42
    assert payload["evidence_coverage"]["evidence_ref_coverage_rate"] == 0.92


@pytest.mark.asyncio
async def test_debug_batch_review_confirm_decides_selected_items(
    client,
    debug_session,
    monkeypatch,
) -> None:
    source = _source()
    run = _parser_run(source.id)
    first = _review_item(source.id, run.id)
    second = _review_item(source.id, run.id, issue_type="missing_source_page")
    first.target_id = None
    second.target_id = None
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    monkeypatch.setattr(
        debug_api,
        "recalculate_quality_gate_from_queue",
        AsyncMock(return_value=_Summary()),
    )
    debug_session.execute = AsyncMock(side_effect=[_one(source), _many([first, second])])

    response = await client.post(
        f"/api/debug/textbook-sources/{source.id}/review-items/batch",
        headers={"X-Debug-Token": "dev"},
        json={
            "action": "confirm",
            "review_item_ids": [str(first.id), str(second.id)],
            "review_note": "bulk checked",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decided_count"] == 2
    assert first.decision == "confirmed"
    assert second.decision == "confirmed"
    assert first.review_note == "bulk checked"
    assert debug_session.flush.await_count == 1


@pytest.mark.asyncio
async def test_debug_batch_review_ignore_blocker_requires_note(
    client,
    debug_session,
) -> None:
    source = _source()
    run = _parser_run(source.id)
    blocker = _review_item(source.id, run.id, severity="blocker")
    blocker.target_id = None
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    debug_session.execute = AsyncMock(side_effect=[_one(source), _many([blocker])])

    response = await client.post(
        f"/api/debug/textbook-sources/{source.id}/review-items/batch",
        headers={"X-Debug-Token": "dev"},
        json={
            "action": "ignore",
            "review_item_ids": [str(blocker.id)],
            "allow_blocker_ignore": True,
        },
    )

    assert response.status_code == 422
    assert blocker.decision == "pending"


@pytest.mark.asyncio
async def test_debug_parser_runs_list_returns_source_scoped_runs(
    client,
    debug_session,
) -> None:
    source = _source()
    run = _parser_run(source.id)
    review_item = _review_item(source.id, run.id)
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    debug_session.execute = AsyncMock(
        side_effect=[
            _one(source),
            _many([run]),
            _many([review_item]),
        ]
    )

    response = await client.get(
        f"/api/debug/textbook-sources/{source.id}/parser-runs",
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["parser_runs"]) == 1
    assert payload["parser_runs"][0]["parser_run_id"] == str(run.id)
    assert payload["parser_runs"][0]["pending_review_count"] == 1
    assert payload["parser_runs"][0]["duration_ms"] == 2000


@pytest.mark.asyncio
async def test_debug_parser_run_detail_returns_404_for_source_mismatch(
    client,
    debug_session,
) -> None:
    source = _source()
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    debug_session.execute = AsyncMock(side_effect=[_one(source), _one(None)])

    response = await client.get(
        f"/api/debug/textbook-sources/{source.id}/parser-runs/{uuid.uuid4()}",
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 404
