from src.documents.artifact import DocumentBlock, DocumentPage
from src.documents.quality import evaluate_document_quality


def test_quality_uses_multiple_metrics_and_marks_ocr_without_failed_status() -> None:
    quality = evaluate_document_quality(
        pages=[
            DocumentPage(page_number=1, text=""),
            DocumentPage(page_number=2, text="Unit 1\nA short text layer."),
        ],
        blocks=[
            DocumentBlock(
                id="p2-b1",
                page_number=2,
                type="heading",
                text="Unit 1",
                reading_order=0,
                confidence=0.7,
                source="pypdf",
            )
        ],
        markdown="Unit 1\nA short text layer.",
    )

    assert quality.page_count == 2
    assert quality.text_char_count > 0
    assert quality.empty_page_ratio == 0.5
    assert quality.block_count == 1
    assert quality.heading_count == 1
    assert quality.needs_ocr is True
    assert "failed" not in quality.to_dict()

