from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class DocumentPage:
    page_number: int
    text: str
    source: str = "text"


@dataclass(frozen=True)
class DocumentBlock:
    id: str
    page_number: int | None
    type: str
    text: str
    reading_order: int
    confidence: float
    source: str


@dataclass(frozen=True)
class DocumentQuality:
    page_count: int
    text_char_count: int
    text_coverage_score: float
    empty_page_ratio: float
    block_count: int
    heading_count: int
    needs_ocr: bool
    needs_review: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentParseArtifact:
    source_id: str
    parser_engine: str
    parser_version: str
    markdown: str
    pages: list[DocumentPage]
    blocks: list[DocumentBlock]
    warnings: list[str]
    quality: DocumentQuality | dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def quality_dict(self) -> dict[str, Any]:
        if isinstance(self.quality, DocumentQuality):
            return self.quality.to_dict()
        return dict(self.quality)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["quality"] = self.quality_dict()
        payload["created_at"] = self.created_at.isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DocumentParseArtifact":
        created_at = payload.get("created_at")
        if isinstance(created_at, str):
            parsed_created_at = datetime.fromisoformat(created_at)
        elif isinstance(created_at, datetime):
            parsed_created_at = created_at
        else:
            parsed_created_at = datetime.now(timezone.utc)
        quality_payload = payload.get("quality") or {}
        quality = DocumentQuality(**quality_payload)
        return cls(
            source_id=str(payload.get("source_id", "")),
            parser_engine=str(payload.get("parser_engine", "unknown")),
            parser_version=str(payload.get("parser_version", "unknown")),
            markdown=str(payload.get("markdown", "")),
            pages=[
                DocumentPage(**page)
                for page in payload.get("pages", [])
                if isinstance(page, dict)
            ],
            blocks=[
                DocumentBlock(**block)
                for block in payload.get("blocks", [])
                if isinstance(block, dict)
            ],
            warnings=list(payload.get("warnings") or []),
            quality=quality,
            metadata=dict(payload.get("metadata") or {}),
            created_at=parsed_created_at,
        )
