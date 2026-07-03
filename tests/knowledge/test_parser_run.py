import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.knowledge import processor
from src.knowledge.parser_profiles import ParserProfile
from src.models.knowledge import KnowledgePoint, KnowledgeSource, ParserRun


class _Page:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _Reader:
    def __init__(self, pages: list[str]) -> None:
        self.pages = [_Page(text) for text in pages]


def _source(path: str) -> KnowledgeSource:
    source = KnowledgeSource(
        title="Test Book",
        filename="test-book.pdf",
        grade="grade-7",
        status="processing",
        object_key=path,
        sha256="a" * 64,
        file_size=10,
        metadata_={},
    )
    source.id = uuid.uuid4()
    return source


def _session() -> AsyncMock:
    db = AsyncMock()
    added: list[object] = []
    db.add = MagicMock(side_effect=added.append)

    async def flush() -> None:
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    db.flush = AsyncMock(side_effect=flush)
    db.added_objects = added
    db.execute = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_process_uploaded_textbook_records_completed_parser_run(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF fake")
    source = _source(str(pdf))
    db = _session()
    profile = ParserProfile(
        id="test_profile",
        expected_unit_count=1,
        min_vocabulary_count=1,
        expected_unit_titles=("Unit X",),
        expected_core_vocabulary=("hello",),
    )
    entry = processor.ParsedVocabularyEntry(
        unit_title="Unit X",
        expression="hello",
        canonical_expression="hello",
        unit_order=1,
        raw_line="hello p.1",
        confidence=0.95,
    )

    monkeypatch.setattr(processor, "profile_for_source", lambda filename: (None, profile))
    monkeypatch.setattr(
        processor,
        "_parse_pdf",
        lambda path: processor.ParsedTextbook(
            page_count=1,
            units=(processor.ParsedUnit("Unit X", "Greetings", 1),),
            text_char_count=800,
        ),
    )
    monkeypatch.setattr(processor, "PdfReader", lambda path: _Reader(["hello " * 160]))
    monkeypatch.setattr(processor, "_parse_unit_vocabulary", lambda reader: (entry,))
    monkeypatch.setattr(processor, "build_chunks", AsyncMock(return_value=1))

    parsed = await processor.process_uploaded_textbook(db, source)

    parser_run = next(item for item in db.added_objects if isinstance(item, ParserRun))
    knowledge_point = next(item for item in db.added_objects if isinstance(item, KnowledgePoint))
    assert parsed.page_count == 1
    assert parser_run.status == "completed"
    assert parser_run.quality_report["page_count"] == 1
    assert parser_run.quality_score["status"] == "published"
    assert source.metadata_["latest_parser_run_id"] == str(parser_run.id)
    assert source.metadata_["quality_status"] == "published"
    assert source.status == "published"
    assert knowledge_point.content["parser_run_id"] == str(parser_run.id)
    assert processor.build_chunks.await_args.kwargs["parser_run_id"] == str(parser_run.id)


@pytest.mark.asyncio
async def test_process_uploaded_textbook_marks_parser_run_failed(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF fake")
    source = _source(str(pdf))
    db = _session()

    monkeypatch.setattr(processor, "profile_for_source", lambda filename: (None, None))
    monkeypatch.setattr(
        processor,
        "_parse_pdf",
        MagicMock(side_effect=ValueError("broken pdf")),
    )

    with pytest.raises(ValueError, match="broken pdf"):
        await processor.process_uploaded_textbook(db, source)

    parser_run = next(item for item in db.added_objects if isinstance(item, ParserRun))
    assert parser_run.status == "failed"
    assert parser_run.error_message == "broken pdf"
    assert parser_run.quality_score["status"] == "failed"
    assert source.status == "failed"
    assert source.metadata_["parser_status"] == "failed"
    assert source.metadata_["latest_parser_run_id"] == str(parser_run.id)
