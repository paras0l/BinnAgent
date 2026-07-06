from pathlib import Path
from typing import Any

from src.documents.artifact import DocumentParseArtifact
from src.documents.parser_engine import ParserDependencyUnavailableError, ParserEngine
from src.documents.parser_router import ParserRouter


class FailingEngine(ParserEngine):
    name = "markitdown"
    version = "test"
    supports_ocr = False
    supports_layout = False

    def parse(self, file_path: str | Path, options: dict[str, Any] | None = None) -> DocumentParseArtifact:
        raise ParserDependencyUnavailableError("missing")


class PassingEngine(ParserEngine):
    name = "pypdf"
    version = "test"
    supports_ocr = False
    supports_layout = False

    def parse(self, file_path: str | Path, options: dict[str, Any] | None = None) -> DocumentParseArtifact:
        return DocumentParseArtifact(
            source_id="source-1",
            parser_engine=self.name,
            parser_version=self.version,
            markdown="Unit 1\nHello",
            pages=[],
            blocks=[],
            warnings=[],
            quality={
                "page_count": 0,
                "text_char_count": 12,
                "text_coverage_score": 0.012,
                "empty_page_ratio": 0.0,
                "block_count": 0,
                "heading_count": 0,
                "needs_ocr": False,
                "needs_review": True,
                "warnings": [],
            },
        )


def test_router_falls_back_and_records_attempted_engines(tmp_path) -> None:
    result = ParserRouter([FailingEngine(), PassingEngine()]).parse(tmp_path / "book.pdf")

    assert result.selected_engine == "pypdf"
    assert result.attempted_engines == ["markitdown", "pypdf"]
    assert result.fallback_used is True
    assert result.attempts[0].status == "failed"
    assert result.metadata()["quality_summary"]["needs_review"] is True
