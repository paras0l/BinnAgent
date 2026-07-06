from __future__ import annotations

import re

from src.documents.artifact import DocumentBlock, DocumentPage, DocumentQuality


def evaluate_document_quality(
    *,
    pages: list[DocumentPage],
    blocks: list[DocumentBlock],
    markdown: str,
    warnings: list[str] | None = None,
) -> DocumentQuality:
    page_count = len(pages)
    page_texts = [page.text or "" for page in pages]
    combined_text = "\n".join(page_texts).strip() or markdown.strip()
    text_char_count = len(combined_text)
    empty_pages = sum(1 for text in page_texts if len(text.strip()) < 20)
    empty_page_ratio = round(empty_pages / page_count, 3) if page_count else 0.0
    block_count = len(blocks)
    heading_count = sum(1 for block in blocks if block.type == "heading")
    if not heading_count:
        heading_count = sum(1 for line in markdown.splitlines() if re.match(r"^\s{0,3}#{1,6}\s+\S", line))

    if page_count:
        char_density = min(1.0, text_char_count / max(page_count * 500, 1))
        non_empty_ratio = 1.0 - empty_page_ratio
        text_coverage_score = round((char_density * 0.65) + (non_empty_ratio * 0.35), 3)
    else:
        text_coverage_score = round(min(1.0, text_char_count / 1000), 3)

    quality_warnings = list(warnings or [])
    if page_count and empty_page_ratio >= 0.5:
        quality_warnings.append("Many pages have little or no extracted text.")
    if page_count and text_char_count < page_count * 80:
        quality_warnings.append("Extracted text coverage is low for the page count.")
    if block_count == 0:
        quality_warnings.append("No structured text blocks were detected.")
    if heading_count == 0 and text_char_count >= 200:
        quality_warnings.append("No headings were detected; document structure may need review.")

    needs_ocr = bool(
        page_count
        and (
            text_coverage_score < 0.15
            or (empty_page_ratio >= 0.5 and text_char_count < page_count * 200)
        )
    )
    needs_review = bool(needs_ocr or text_coverage_score < 0.45 or quality_warnings)

    if needs_ocr:
        quality_warnings.append("Document likely needs OCR for better extraction.")

    deduped_warnings = list(dict.fromkeys(quality_warnings))
    return DocumentQuality(
        page_count=page_count,
        text_char_count=text_char_count,
        text_coverage_score=text_coverage_score,
        empty_page_ratio=empty_page_ratio,
        block_count=block_count,
        heading_count=heading_count,
        needs_ocr=needs_ocr,
        needs_review=needs_review,
        warnings=deduped_warnings,
    )
