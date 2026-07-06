from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import which

from src.documents.artifact import DocumentParseArtifact


@dataclass(frozen=True)
class OcrResult:
    engine: str
    input_path: Path
    output_path: Path | None
    languages: tuple[str, ...]
    used: bool
    available: bool
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "engine": self.engine,
            "input_path": str(self.input_path),
            "output_path": str(self.output_path) if self.output_path else None,
            "languages": list(self.languages),
            "used": self.used,
            "available": self.available,
            "error": self.error,
        }


def should_ocr_artifact(artifact: DocumentParseArtifact) -> bool:
    quality = artifact.quality_dict()
    if bool(quality.get("needs_ocr")):
        return True
    page_count = int(quality.get("page_count") or len(artifact.pages) or 0)
    text_char_count = int(quality.get("text_char_count") or len(artifact.markdown or ""))
    empty_page_ratio = float(quality.get("empty_page_ratio") or 0)
    return bool(page_count and text_char_count < max(200, page_count * 20) and empty_page_ratio >= 0.5)


def run_pdf_ocr(
    input_path: str | Path,
    *,
    languages: tuple[str, ...] = ("eng", "chi_sim"),
) -> OcrResult:
    path = Path(input_path).expanduser().resolve()
    output_path = path.with_name(f"{path.stem}.ocr{path.suffix}")
    if path.suffix.casefold() != ".pdf":
        return OcrResult(
            engine="ocrmypdf+tesseract",
            input_path=path,
            output_path=None,
            languages=languages,
            used=False,
            available=False,
            error="OCR only supports PDF files.",
        )
    if which("ocrmypdf") is None:
        return OcrResult(
            engine="ocrmypdf+tesseract",
            input_path=path,
            output_path=None,
            languages=languages,
            used=False,
            available=False,
            error="ocrmypdf executable is not installed.",
        )
    command = [
        "ocrmypdf",
        "--skip-text",
        "--rotate-pages",
        "--deskew",
        "--optimize",
        "1",
        "-l",
        "+".join(languages),
        str(path),
        str(output_path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return OcrResult(
            engine="ocrmypdf+tesseract",
            input_path=path,
            output_path=output_path,
            languages=languages,
            used=False,
            available=True,
            error=str(exc),
        )
    if completed.returncode != 0:
        return OcrResult(
            engine="ocrmypdf+tesseract",
            input_path=path,
            output_path=output_path,
            languages=languages,
            used=False,
            available=True,
            error=(completed.stderr or completed.stdout or "OCR failed.").strip()[:1000],
        )
    return OcrResult(
        engine="ocrmypdf+tesseract",
        input_path=path,
        output_path=output_path,
        languages=languages,
        used=True,
        available=True,
    )
