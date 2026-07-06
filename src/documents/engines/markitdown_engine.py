from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pypdf import PdfReader

from src.config import settings
from src.documents.artifact import DocumentBlock, DocumentPage, DocumentParseArtifact
from src.documents.parser_engine import (
    ParserDependencyUnavailableError,
    ParserEngine,
    ParserInputError,
    ParserParseError,
)
from src.documents.quality import evaluate_document_quality


class MarkItDownEngine(ParserEngine):
    name = "markitdown"
    supports_ocr = False
    supports_layout = False

    def __init__(self) -> None:
        try:
            self.version = version("markitdown")
        except PackageNotFoundError:
            self.version = "unavailable"

    def parse(
        self,
        file_path: str | Path,
        options: dict[str, Any] | None = None,
    ) -> DocumentParseArtifact:
        options = options or {}
        path = _local_upload_path(file_path, options)
        markitdown_cls = _load_markitdown()

        try:
            converter = markitdown_cls()
            result = converter.convert(str(path))
            markdown = _markdown_from_result(result)
        except ParserDependencyUnavailableError:
            raise
        except Exception as exc:
            raise ParserParseError(f"MarkItDown failed to parse document: {exc}") from exc

        if not markdown.strip():
            raise ParserParseError("MarkItDown returned empty markdown.")

        blocks = _blocks_from_markdown(markdown)
        pages = _pages_from_pdf_text(path) if path.suffix.casefold() == ".pdf" else []
        if not pages:
            pages = [DocumentPage(page_number=1, text=_plain_text(markdown), source=self.name)]
        warnings: list[str] = []
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
            metadata={"file_path": str(path)},
        )


def _load_markitdown() -> type:
    try:
        module = import_module("markitdown")
    except Exception as exc:
        raise ParserDependencyUnavailableError("MarkItDown dependency is not available.") from exc
    markitdown_cls = getattr(module, "MarkItDown", None)
    if markitdown_cls is None:
        raise ParserDependencyUnavailableError("MarkItDown class is not available.")
    return markitdown_cls


def _local_upload_path(file_path: str | Path, options: dict[str, Any]) -> Path:
    raw = str(file_path)
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        raise ParserInputError("MarkItDownEngine refuses remote URLs.")
    path = Path(file_path).expanduser().resolve()
    upload_dir = Path(options.get("upload_dir") or settings.knowledge_upload_dir).expanduser().resolve()
    if not _is_relative_to(path, upload_dir):
        raise ParserInputError("MarkItDownEngine only parses files from the upload directory.")
    if not path.exists() or not path.is_file():
        raise ParserInputError(f"Local uploaded file does not exist: {path}")
    return path


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _markdown_from_result(result: Any) -> str:
    for attr in ("markdown", "text_content", "text"):
        value = getattr(result, attr, None)
        if isinstance(value, str):
            return value
    if isinstance(result, str):
        return result
    return str(result)


def _blocks_from_markdown(markdown: str) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    for index, chunk in enumerate(_markdown_chunks(markdown)):
        stripped = chunk.strip()
        if not stripped:
            continue
        block_type = "heading" if stripped.startswith("#") else "paragraph"
        text = stripped.lstrip("#").strip() if block_type == "heading" else stripped
        blocks.append(
            DocumentBlock(
                id=f"md-b{index + 1}",
                page_number=None,
                type=block_type,
                text=text,
                reading_order=index,
                confidence=0.82,
                source="markitdown",
            )
        )
    return blocks


def _markdown_chunks(markdown: str) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    for line in markdown.replace("\r\n", "\n").splitlines():
        if line.strip():
            current.append(line)
            continue
        if current:
            chunks.append("\n".join(current))
            current = []
    if current:
        chunks.append("\n".join(current))
    return chunks


def _plain_text(markdown: str) -> str:
    lines = [line.lstrip("#").strip() for line in markdown.splitlines()]
    return "\n".join(line for line in lines if line)


def _pages_from_pdf_text(path: Path) -> list[DocumentPage]:
    try:
        reader = PdfReader(path)
        return [
            DocumentPage(page_number=page_number, text=page.extract_text() or "", source="pypdf")
            for page_number, page in enumerate(reader.pages, start=1)
        ]
    except Exception:
        return []
