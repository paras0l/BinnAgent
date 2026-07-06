import inspect

from src.documents.artifact import DocumentBlock, DocumentPage, DocumentParseArtifact
from src.knowledge import textbook_extractor
from src.knowledge.textbook_extractor import extract_textbook_candidates


def test_textbook_extractor_consumes_artifact_and_keeps_evidence() -> None:
    artifact = DocumentParseArtifact(
        source_id="source-1",
        parser_engine="markitdown",
        parser_version="1.0",
        markdown="# Unit 1\nMy name's Gina.\n\nWords and Expressions in Each Unit\nUnit 1\nname /neim/ n. 名字 p.1\nVocabulary Index",
        pages=[DocumentPage(page_number=1, text="Unit 1\nMy name's Gina.")],
        blocks=[
            DocumentBlock("b1", 1, "heading", "Unit 1\nMy name's Gina.", 0, 0.9, "markitdown"),
            DocumentBlock(
                "b2",
                1,
                "paragraph",
                "Words and Expressions in Each Unit\nUnit 1\nname /neim/ n. 名字 p.1\nVocabulary Index",
                1,
                0.86,
                "markitdown",
            ),
        ],
        warnings=[],
        quality={
            "page_count": 1,
            "text_char_count": 100,
            "text_coverage_score": 0.5,
            "empty_page_ratio": 0,
            "block_count": 2,
            "heading_count": 1,
            "needs_ocr": False,
            "needs_review": False,
            "warnings": [],
        },
    )

    result = extract_textbook_candidates(artifact)

    assert result.curriculum[0].title == "Unit 1"
    assert result.curriculum[0].evidence.parser_engine == "markitdown"
    assert result.knowledge[0].evidence.block_id == "b1"
    assert result.vocabulary[0].expression == "name"
    assert result.vocabulary[0].evidence.page_number == 1
    assert "pypdf" not in inspect.getsource(textbook_extractor)


def test_textbook_extractor_compacts_long_unit_heading_rest() -> None:
    long_line = "Unit 1 " + ("very long " * 80)
    artifact = DocumentParseArtifact(
        source_id="source-1",
        parser_engine="markitdown",
        parser_version="1.0",
        markdown=long_line,
        pages=[DocumentPage(page_number=1, text=long_line)],
        blocks=[DocumentBlock("b1", 1, "paragraph", long_line, 0, 0.8, "markitdown")],
        warnings=[],
        quality={
            "page_count": 1,
            "text_char_count": len(long_line),
            "text_coverage_score": 1,
            "empty_page_ratio": 0,
            "block_count": 1,
            "heading_count": 0,
            "needs_ocr": False,
            "needs_review": False,
            "warnings": [],
        },
    )

    result = extract_textbook_candidates(artifact)

    assert result.curriculum[0].title == "Unit 1"
    assert len(result.curriculum[0].subtitle) <= 120
