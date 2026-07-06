from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.documents.artifact import DocumentParseArtifact


class ParserEngineError(RuntimeError):
    """Base class for recognizable parser engine failures."""


class ParserDependencyUnavailableError(ParserEngineError):
    """Raised when an optional parser dependency is not installed or loadable."""


class ParserInputError(ParserEngineError):
    """Raised when an engine refuses an unsafe or unsupported input."""


class ParserParseError(ParserEngineError):
    """Raised when an engine is available but cannot parse the file."""


class ParserEngine(ABC):
    name: str
    version: str
    supports_ocr: bool
    supports_layout: bool

    @abstractmethod
    def parse(self, file_path: str | Path, options: dict[str, Any] | None = None) -> DocumentParseArtifact:
        """Parse a local document into a normalized artifact."""
