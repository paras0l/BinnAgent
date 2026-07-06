from src.documents.artifact import DocumentBlock, DocumentPage, DocumentParseArtifact
from src.knowledge.textbook_extractor import LayoutLine, _extract_vocabulary_from_layout_lines, extract_textbook_candidates


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
    assert result.vocabulary[0].evidence.block_id == "b2"


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


def test_textbook_extractor_uses_page_lines_for_pypdf_wordlist() -> None:
    artifact = DocumentParseArtifact(
        source_id="source-1",
        parser_engine="pypdf",
        parser_version="1.0",
        markdown="<!-- page:1 -->\nUnit 1\nMy name's Gina.",
        pages=[
            DocumentPage(page_number=1, text="Unit 1\nMy name's Gina."),
            DocumentPage(
                page_number=2,
                text="""Words and Expressions in Each Unit
9594
Unit 1
name /neim/ n. 名字 p.1
Page PB
telephone number 电话号码 p.4
Vocabulary Index""",
            ),
        ],
        blocks=[
            DocumentBlock(
                "p1-b1",
                1,
                "paragraph",
                "Unit 1 My name's Gina.",
                0,
                0.78,
                "pypdf",
            ),
            DocumentBlock(
                "p2-b1",
                2,
                "paragraph",
                "Words and Expressions in Each Unit 9594 Unit 1 name /neim/ n. 名字 p.1",
                1,
                0.78,
                "pypdf",
            ),
        ],
        warnings=[],
        quality={
            "page_count": 2,
            "text_char_count": 200,
            "text_coverage_score": 0.5,
            "empty_page_ratio": 0,
            "block_count": 2,
            "heading_count": 0,
            "needs_ocr": False,
            "needs_review": False,
            "warnings": [],
        },
    )

    result = extract_textbook_candidates(artifact)

    assert [item.expression for item in result.vocabulary] == ["name", "telephone number"]
    assert result.vocabulary[0].evidence.block_id == "page-2"


def test_textbook_extractor_uses_layout_lines_for_two_column_wordlist() -> None:
    lines = [
        LayoutLine(1, 0, 700, "Words and Expressions in Each Unit", "l1"),
        LayoutLine(1, 0, 680, "Unit 1 guitar /gita:/ n. 吉他 p.1", "l2"),
        LayoutLine(1, 0, 660, "nF", "l3"),
        LayoutLine(1, 0, 640, "elephant/elifont/ n. 大象 p.2", "l4"),
        LayoutLine(1, 0, 620, "telephone/phone number 电话号码 p.4", "l4b"),
        LayoutLine(1, 0, 600, "first name 名字 p.5 grandparent /graenpeorant/ n. 祖父", "l4c"),
        LayoutLine(1, 1, 680, "Unit $ scary /skeori/ adj. 吓人的 p.37", "l5"),
        LayoutLine(1, 1, 660, "Unit", "l6"),
        LayoutLine(1, 1, 640, "Vocabulary Index", "l7"),
    ]

    result = _extract_vocabulary_from_layout_lines(lines, "pypdf")

    assert [(item.unit_title, item.expression) for item in result] == [
        ("Unit 1", "guitar"),
        ("Unit 1", "elephant"),
        ("Unit 1", "telephone number"),
        ("Unit 1", "first name"),
        ("Unit 5", "scary"),
    ]


def test_textbook_extractor_extracts_appendix_knowledge_candidates() -> None:
    artifact = DocumentParseArtifact(
        source_id="source-1",
        parser_engine="pypdf",
        parser_version="1.0",
        markdown="",
        pages=[
            DocumentPage(page_number=1, text="Unit 6\nDo you like bananas?"),
            DocumentPage(
                page_number=108,
                text="""Grammar
I. 词类（Parts of Speech）
II. 名词（Nouns）
1. 动词 be（Verb to be）
Pronunciation
Unit 6 Do you like bananas?
Words and Expressions in Each Unit""",
            ),
        ],
        blocks=[],
        warnings=[],
        quality={
            "page_count": 2,
            "text_char_count": 200,
            "text_coverage_score": 0.5,
            "empty_page_ratio": 0,
            "block_count": 0,
            "heading_count": 0,
            "needs_ocr": False,
            "needs_review": False,
            "warnings": [],
        },
    )

    result = extract_textbook_candidates(artifact)
    knowledge = {(item.type, item.title) for item in result.knowledge}

    assert ("grammar", "词类（Parts of Speech）") in knowledge
    assert ("grammar", "名词（Nouns）") in knowledge
    assert ("grammar", "动词 be（Verb to be）") in knowledge
    assert ("pronunciation", "Unit 6 pronunciation") in knowledge


def test_textbook_extractor_extracts_notes_on_the_text_by_unit_and_number() -> None:
    artifact = DocumentParseArtifact(
        source_id="source-1",
        parser_engine="ocrmypdf+tesseract",
        parser_version="1.0",
        markdown="",
        pages=[
            DocumentPage(
                page_number=83,
                text=(
                    "Noteson the Textsss Notes on the Text Unit 1 Can you play the guitar? "
                    "1. I want to join the art club. 我想参加美术社团。"
                ),
            ),
            DocumentPage(
                page_number=84,
                text=(
                    "Unit 2 What time do you go to school? "
                    "1. That’s a funny time for breakfast! 那个时间吃早饭真有意思哟!"
                ),
            ),
            DocumentPage(page_number=98, text="Tapescripts\nUnit 1\nConversation 1"),
        ],
        blocks=[],
        warnings=[],
        quality={
            "page_count": 3,
            "text_char_count": 300,
            "text_coverage_score": 0.5,
            "empty_page_ratio": 0,
            "block_count": 0,
            "heading_count": 0,
            "needs_ocr": False,
            "needs_review": False,
            "warnings": [],
        },
    )

    result = extract_textbook_candidates(artifact)
    knowledge = {(item.type, item.title, item.summary) for item in result.knowledge}

    assert any(item[0] == "text_note" and item[1] == "Unit 1 note 1" for item in knowledge)
    assert any(item[0] == "text_note" and item[1] == "Unit 2 note 1" for item in knowledge)
    assert all("Tapescripts" not in item[2] for item in knowledge)


def test_textbook_extractor_extracts_ocr_grade7_lower_grammar_and_pronunciation_topics() -> None:
    artifact = DocumentParseArtifact(
        source_id="source-1",
        parser_engine="ocrmypdf+tesseract",
        parser_version="1.0",
        markdown="",
        pages=[
            DocumentPage(
                page_number=106,
                text="""Pronunciation:
I 在 单词 中 的 读音
字母 和 元 音字 母 组 合在 重读 音节 中 的 读音 归 类""",
            ),
            DocumentPage(
                page_number=112,
                text="""Pronunciation
Unit 1 Can you play the guitar?
1. Listen and read.""",
            ),
            DocumentPage(
                page_number=120,
                text="工 “情态动词(ModalVerbs ) 情态动词 表示说话人 对所说动作的观点。",
            ),
            DocumentPage(
                page_number=121,
                text="工 现在进行时(PresentProgressiveTense ) 1. 正在进行或发生的动作。",
            ),
            DocumentPage(
                page_number=123,
                text="III. 一般过去时 ( Simple Past Tense ) 1. 一般过去时表示过去发生的动作。",
            ),
        ],
        blocks=[],
        warnings=[],
        quality={
            "page_count": 5,
            "text_char_count": 300,
            "text_coverage_score": 0.5,
            "empty_page_ratio": 0,
            "block_count": 0,
            "heading_count": 0,
            "needs_ocr": False,
            "needs_review": False,
            "warnings": [],
        },
    )

    result = extract_textbook_candidates(artifact)
    knowledge = {(item.type, item.title) for item in result.knowledge}

    assert ("pronunciation", "Pronunciation: 在 单词 中 的 读音") in knowledge
    assert ("pronunciation", "Unit 1 pronunciation") in knowledge
    assert ("grammar", "情态动词(ModalVerbs )") in knowledge
    assert ("grammar", "现在进行时(PresentProgressiveTense )") in knowledge
    assert ("grammar", "一般过去时 ( Simple Past Tense )") in knowledge


def test_textbook_extractor_extracts_unit_marked_non_vocabulary_points() -> None:
    artifact = DocumentParseArtifact(
        source_id="source-1",
        parser_engine="pypdf",
        parser_version="1.0",
        markdown="",
        pages=[
            DocumentPage(
                page_number=12,
                text="""STARTER UNIT 1
Listen and repeat. 听录音并跟读。1b
1c Practice the conversations in the picture. Then greet your partner.
Good morning, Helen!
How are you?
Language Goals: Letters A-H; Greet people""",
            ),
        ],
        blocks=[],
        warnings=[],
        quality={
            "page_count": 1,
            "text_char_count": 200,
            "text_coverage_score": 0.5,
            "empty_page_ratio": 0,
            "block_count": 0,
            "heading_count": 0,
            "needs_ocr": False,
            "needs_review": False,
            "warnings": [],
        },
    )

    result = extract_textbook_candidates(artifact)
    knowledge = {(item.type, item.title) for item in result.knowledge}

    assert ("text_note", "Starter Unit 1 language goals") in knowledge
    assert ("text_note", "Starter Unit 1 activity 1b") in knowledge
    assert ("text_note", "Starter Unit 1 activity 1c") in knowledge
    assert ("sentence_pattern", "Good morning, Helen!") in knowledge
    assert ("sentence_pattern", "How are you?") in knowledge


def test_textbook_extractor_does_not_turn_tapescripts_into_unit_sentence_patterns() -> None:
    artifact = DocumentParseArtifact(
        source_id="source-1",
        parser_engine="ocrmypdf+tesseract",
        parser_version="1.0",
        markdown="",
        pages=[
            DocumentPage(
                page_number=98,
                text="""Tapescripts
Unit 1 Can you play the guitar?
Bob: I want to join the English club.
Mary: What club do you want to join, Bob?""",
            )
        ],
        blocks=[],
        warnings=[],
        quality={
            "page_count": 1,
            "text_char_count": 160,
            "text_coverage_score": 0.5,
            "empty_page_ratio": 0,
            "block_count": 0,
            "heading_count": 0,
            "needs_ocr": False,
            "needs_review": False,
            "warnings": [],
        },
    )

    result = extract_textbook_candidates(artifact)

    assert all(item.type != "sentence_pattern" for item in result.knowledge)
