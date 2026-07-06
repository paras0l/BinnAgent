from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import settings
from src.documents.artifact import DocumentParseArtifact
from src.documents.engines.markitdown_engine import MarkItDownEngine
from src.documents.engines.pypdf_engine import PyPdfEngine
from src.documents.parser_engine import ParserEngine, ParserEngineError


@dataclass(frozen=True)
class ParserAttempt:
    engine: str
    status: str
    error: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"engine": self.engine, "status": self.status, "error": self.error}


@dataclass(frozen=True)
class ParserRouterResult:
    artifact: DocumentParseArtifact
    attempted_engines: list[str]
    attempts: list[ParserAttempt]
    selected_engine: str
    fallback_used: bool

    def quality_summary(self) -> dict[str, Any]:
        return self.artifact.quality_dict()

    def metadata(self) -> dict[str, Any]:
        return {
            "attempted_engines": self.attempted_engines,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "selected_engine": self.selected_engine,
            "fallback_used": self.fallback_used,
            "quality_summary": self.quality_summary(),
        }


class ParserRouter:
    def __init__(self, engines: list[ParserEngine] | None = None) -> None:
        self.engines = engines or [MarkItDownEngine(), PyPdfEngine()]

    def parse(
        self,
        file_path: str | Path,
        options: dict[str, Any] | None = None,
    ) -> ParserRouterResult:
        options = {"upload_dir": settings.knowledge_upload_dir, **(options or {})}
        attempts: list[ParserAttempt] = []
        first_error: ParserEngineError | None = None
        for index, engine in enumerate(self.engines):
            try:
                artifact = engine.parse(file_path, options)
            except ParserEngineError as exc:
                if first_error is None:
                    first_error = exc
                attempts.append(ParserAttempt(engine=engine.name, status="failed", error=str(exc)))
                continue
            attempts.append(ParserAttempt(engine=engine.name, status="selected"))
            return ParserRouterResult(
                artifact=artifact,
                attempted_engines=[attempt.engine for attempt in attempts],
                attempts=attempts,
                selected_engine=engine.name,
                fallback_used=index > 0,
            )
        errors = "; ".join(
            f"{attempt.engine}: {attempt.error}" for attempt in attempts if attempt.error
        )
        if first_error is not None:
            raise ParserEngineError(f"All parser engines failed. {errors}") from first_error
        raise ParserEngineError("No parser engines are configured.")
