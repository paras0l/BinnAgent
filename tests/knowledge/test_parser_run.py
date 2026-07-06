import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.documents.artifact import DocumentBlock, DocumentPage, DocumentParseArtifact
from src.documents.ocr import OcrResult
from src.documents.parser_router import ParserAttempt, ParserRouterResult
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
        expected_unit_titles=("Unit 1",),
        expected_core_vocabulary=("hello",),
    )
    artifact = DocumentParseArtifact(
        source_id=str(source.id),
        parser_engine="pypdf",
        parser_version="test",
        markdown="Unit 1\nGreetings\n\nWords and Expressions in Each Unit\nUnit 1\nhello /həˈləʊ/ interj. 你好 p.1\nVocabulary Index",
        pages=[DocumentPage(page_number=1, text="hello " * 160)],
        blocks=[
            DocumentBlock("b1", 1, "heading", "Unit 1\nGreetings", 0, 0.9, "pypdf"),
            DocumentBlock(
                "b2",
                1,
                "paragraph",
                "Words and Expressions in Each Unit\nUnit 1\nhello /həˈləʊ/ interj. 你好 p.1\nVocabulary Index",
                1,
                0.9,
                "pypdf",
            ),
        ],
        warnings=[],
        quality={
            "page_count": 1,
            "text_char_count": 960,
            "text_coverage_score": 1.0,
            "empty_page_ratio": 0.0,
            "block_count": 2,
            "heading_count": 1,
            "needs_ocr": False,
            "needs_review": False,
            "warnings": [],
        },
    )
    router_result = ParserRouterResult(
        artifact=artifact,
        attempted_engines=["markitdown", "pypdf"],
        attempts=[
            ParserAttempt("markitdown", "failed", "missing"),
            ParserAttempt("pypdf", "selected"),
        ],
        selected_engine="pypdf",
        fallback_used=True,
    )

    monkeypatch.setattr(processor, "profile_for_source", lambda filename: (None, profile))
    monkeypatch.setattr(
        processor,
        "ParserRouter",
        lambda: MagicMock(parse=MagicMock(return_value=router_result)),
    )
    monkeypatch.setattr(processor, "build_chunks", AsyncMock(return_value=1))

    parsed = await processor.process_uploaded_textbook(db, source)

    parser_run = next(item for item in db.added_objects if isinstance(item, ParserRun))
    knowledge_points = [item for item in db.added_objects if isinstance(item, KnowledgePoint)]
    vocabulary_point = next(item for item in knowledge_points if item.type == "vocabulary")
    assert parsed.page_count == 1
    assert parser_run.status == "completed"
    assert parser_run.stage == "completed"
    assert parser_run.progress == 100
    assert parser_run.quality_report["page_count"] == 1
    assert parser_run.quality_score["status"] == "review_required"
    assert source.metadata_["latest_parser_run_id"] == str(parser_run.id)
    assert source.metadata_["quality_status"] == "review_required"
    assert source.metadata_["availability_status"] == "needs_review"
    assert source.metadata_["selected_engine"] == "pypdf"
    assert source.metadata_["fallback_used"] is True
    assert source.status == parser_run.quality_score["status"]
    assert vocabulary_point.status == "published"
    assert vocabulary_point.content["requires_review"] is False
    assert vocabulary_point.content["parser_run_id"] == str(parser_run.id)
    assert processor.build_chunks.await_args.kwargs["parser_run_id"] == str(parser_run.id)


@pytest.mark.asyncio
async def test_parse_with_optional_ocr_reruns_parser_for_scanned_pdf(tmp_path, monkeypatch) -> None:
    source_id = uuid.uuid4()
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF fake")
    ocr_pdf = tmp_path / "book.ocr.pdf"
    ocr_pdf.write_bytes(b"%PDF searchable")
    scanned_artifact = DocumentParseArtifact(
        source_id=str(source_id),
        parser_engine="pypdf",
        parser_version="test",
        markdown="",
        pages=[DocumentPage(page_number=1, text="")],
        blocks=[],
        warnings=["PDF has no usable extracted text layer."],
        quality={
            "page_count": 1,
            "text_char_count": 0,
            "text_coverage_score": 0.0,
            "empty_page_ratio": 1.0,
            "block_count": 0,
            "heading_count": 0,
            "needs_ocr": True,
            "needs_review": True,
            "warnings": [],
        },
    )
    searchable_artifact = DocumentParseArtifact(
        source_id=str(source_id),
        parser_engine="markitdown",
        parser_version="test",
        markdown="Unit 1\nHello",
        pages=[DocumentPage(page_number=1, text="Unit 1\nHello")],
        blocks=[DocumentBlock("b1", 1, "heading", "Unit 1\nHello", 0, 0.9, "markitdown")],
        warnings=[],
        quality={
            "page_count": 1,
            "text_char_count": 12,
            "text_coverage_score": 0.8,
            "empty_page_ratio": 0.0,
            "block_count": 1,
            "heading_count": 1,
            "needs_ocr": False,
            "needs_review": False,
            "warnings": [],
        },
    )
    first_result = ParserRouterResult(
        artifact=scanned_artifact,
        attempted_engines=["markitdown", "pypdf"],
        attempts=[ParserAttempt("pypdf", "selected")],
        selected_engine="pypdf",
        fallback_used=True,
    )
    second_result = ParserRouterResult(
        artifact=searchable_artifact,
        attempted_engines=["markitdown"],
        attempts=[ParserAttempt("markitdown", "selected")],
        selected_engine="markitdown",
        fallback_used=False,
    )
    parser = MagicMock()
    parser.parse = MagicMock(side_effect=[first_result, second_result])
    monkeypatch.setattr(processor, "ParserRouter", lambda: parser)
    monkeypatch.setattr(
        processor,
        "run_pdf_ocr",
        lambda path: OcrResult(
            engine="ocrmypdf+tesseract",
            input_path=Path(path),
            output_path=ocr_pdf,
            languages=("eng", "chi_sim"),
            used=True,
            available=True,
        ),
    )

    result, ocr = await processor._parse_with_optional_ocr(pdf, source_id=source_id)

    assert result is second_result
    assert ocr is not None
    assert ocr.used is True
    assert parser.parse.call_args_list[1].args[0] == ocr_pdf


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
        "ParserRouter",
        lambda: MagicMock(parse=MagicMock(side_effect=ValueError("broken pdf"))),
    )

    with pytest.raises(ValueError, match="broken pdf"):
        await processor.process_uploaded_textbook(db, source)

    parser_run = next(item for item in db.added_objects if isinstance(item, ParserRun))
    assert parser_run.status == "failed"
    assert parser_run.stage == "failed"
    assert parser_run.error_message == "broken pdf"
    assert parser_run.quality_score["status"] == "failed"
    assert source.status == "failed"
    assert source.metadata_["parser_status"] == "failed"
    assert source.metadata_["latest_parser_run_id"] == str(parser_run.id)
