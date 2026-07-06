from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.documents.artifact import DocumentBlock, DocumentPage, DocumentParseArtifact
from src.documents.parser_engine import ParserEngine, ParserInputError, ParserParseError
from src.documents.quality import evaluate_document_quality


class PyPdfEngine(ParserEngine):
    name = "pypdf"
    supports_ocr = False
    supports_layout = False

    def __init__(self) -> None:
        try:
            self.version = version("pypdf")
        except PackageNotFoundError:
            self.version = "unknown"

    def parse(
        self,
        file_path: str | Path,
        options: dict[str, Any] | None = None,
    ) -> DocumentParseArtifact:
        options = options or {}
        path = Path(file_path)
        if path.suffix.casefold() != ".pdf":
            raise ParserInputError("PyPdfEngine only supports local PDF files.")
        if not path.exists() or not path.is_file():
            raise ParserInputError(f"Local PDF file does not exist: {path}")

        try:
            reader = PdfReader(path)
            pages: list[DocumentPage] = []
            blocks: list[DocumentBlock] = []
            markdown_pages: list[str] = []
            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                pages.append(DocumentPage(page_number=page_number, text=text, source=self.name))
                markdown_pages.append(f"<!-- page:{page_number} -->\n{text.strip()}")
                order = len(blocks)
                for paragraph in _paragraphs(text):
                    block_type = "heading" if _looks_like_heading(paragraph) else "paragraph"
                    blocks.append(
                        DocumentBlock(
                            id=f"p{page_number}-b{order + 1}",
                            page_number=page_number,
                            type=block_type,
                            text=paragraph,
                            reading_order=order,
                            confidence=0.78,
                            source=self.name,
                        )
                    )
                    order += 1
        except Exception as exc:
            raise ParserParseError(f"pypdf failed to parse document: {exc}") from exc

        warnings: list[str] = []
        if pages and all(not page.text.strip() for page in pages):
            warnings.append("PDF has no usable extracted text layer.")
        markdown = "\n\n".join(markdown_pages).strip()
        quality = evaluate_document_quality(
            pages=pages,
            blocks=blocks,
            markdown=markdown,
            warnings=warnings,
        )
        return DocumentParseArtifact(
            source_id=str(options.get("source_id") or path.stem),
            parser_engine=self.name,
            parser_version=self.version,
            markdown=markdown,
            pages=pages,
            blocks=blocks,
            warnings=list(dict.fromkeys([*warnings, *quality.warnings])),
            quality=quality,
        )


def _paragraphs(text: str) -> list[str]:
    return [
        " ".join(part.split())
        for part in text.replace("\r\n", "\n").split("\n\n")
        if " ".join(part.split())
    ]


def _looks_like_heading(text: str) -> bool:
    normalized = " ".join(text.split())
    if len(normalized) > 90:
        return False
    return normalized.casefold().startswith(("unit ", "starter unit ", "chapter ", "lesson "))
