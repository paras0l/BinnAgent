from pathlib import Path

import pytest

from src.documents.engines import markitdown_engine
from src.documents.engines.markitdown_engine import MarkItDownEngine
from src.documents.parser_engine import ParserInputError


class _Result:
    text_content = "# Unit 1\n\nHello world"


class _FakeMarkItDown:
    def convert(self, path: str) -> _Result:
        assert Path(path).exists()
        return _Result()


def test_markitdown_engine_converts_uploaded_local_file(monkeypatch, tmp_path) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    document = upload_dir / "book.pdf"
    document.write_text("fake", encoding="utf-8")
    monkeypatch.setattr(markitdown_engine, "_load_markitdown", lambda: _FakeMarkItDown)

    artifact = MarkItDownEngine().parse(
        document,
        {"source_id": "source-1", "upload_dir": str(upload_dir)},
    )

    assert artifact.source_id == "source-1"
    assert artifact.parser_engine == "markitdown"
    assert artifact.markdown.startswith("# Unit 1")
    assert artifact.blocks[0].type == "heading"


def test_markitdown_engine_keeps_pdf_page_text_when_available(monkeypatch, tmp_path) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    document = upload_dir / "book.pdf"
    document.write_text("fake", encoding="utf-8")
    monkeypatch.setattr(markitdown_engine, "_load_markitdown", lambda: _FakeMarkItDown)
    monkeypatch.setattr(
        markitdown_engine,
        "_pages_from_pdf_text",
        lambda path: [
            markitdown_engine.DocumentPage(page_number=1, text="Unit 1\nHello", source="pypdf"),
            markitdown_engine.DocumentPage(page_number=2, text="Words and Expressions", source="pypdf"),
        ],
    )

    artifact = MarkItDownEngine().parse(
        document,
        {"source_id": "source-1", "upload_dir": str(upload_dir)},
    )

    assert artifact.parser_engine == "markitdown"
    assert [page.source for page in artifact.pages] == ["pypdf", "pypdf"]
    assert artifact.quality_dict()["page_count"] == 2


def test_markitdown_engine_refuses_remote_urls(tmp_path) -> None:
    with pytest.raises(ParserInputError, match="remote URLs"):
        MarkItDownEngine().parse(
            "https://example.com/book.pdf",
            {"upload_dir": str(tmp_path)},
        )


def test_markitdown_engine_refuses_files_outside_upload_dir(tmp_path) -> None:
    outside = tmp_path / "outside.pdf"
    outside.write_text("fake", encoding="utf-8")
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    with pytest.raises(ParserInputError, match="upload directory"):
        MarkItDownEngine().parse(outside, {"upload_dir": str(upload_dir)})
