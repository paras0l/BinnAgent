from __future__ import annotations

import pytest

from src.extraction.writing_phrase import writing_phrase_regex_fallback_payload
from src.prompts import PromptExecutionContext, PromptExecutor


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt_id", "variables", "raw_output"),
    [
        (
            "vocabulary.agent.extract",
            {"user_message": "讲一下 significant", "assistant_reply": "significant 表示重要的。"},
            (
                '{"cards":[{"word":"significant","phonetic":"/sɪɡˈnɪfɪkənt/",'
                '"definition_zh":"重要的","definition_en":"important",'
                '"examples":[{"sentence":"This is significant."}],"confidence":0.92}]}'
            ),
        ),
        (
            "writing_phrase.import",
            {"topic": "online learning", "task_type": "generate"},
            (
                '{"candidates":[{"text":"What matters most is that...",'
                '"examples":[{"sentence":"What matters most is that we keep learning."}],'
                '"quality_score":0.86}]}'
            ),
        ),
        (
            "exercise.generate",
            {
                "count": 1,
                "target_type": "grammar_topic",
                "target_id": "simple-present",
                "target_label": "一般现在时",
                "allowed_types": "grammar_fill_blank, single_choice, fill_blank",
                "context_text": "学习者水平：junior",
            },
            (
                '{"items":[{"skill":"grammar","type":"grammar_fill_blank",'
                '"prompt":"She ____ English every day.","options":[],'
                '"correctAnswer":"studies","acceptedAnswers":["studies"],'
                '"explanation":"主语 She 是第三人称单数，一般现在时动词用 studies。",'
                '"difficulty":"easy"}]}'
            ),
        ),
        (
            "grammar.micro_lesson.structured",
            {"topic_title": "一般现在时"},
            (
                '{"machine_data":{"topic":"一般现在时","core_rules":["动词随主语变化。"],'
                '"examples":[{"sentence":"She likes English."}],"mistakes":["漏掉 s"],'
                '"exercises":['
                '{"type":"grammar_fill_blank","prompt":"She ___ English.","answer":"likes",'
                '"accepted_answers":["likes"],"explanation":"主语是第三人称单数。"},'
                '{"type":"grammar_fill_blank","prompt":"He ___ to school every day.","answer":"goes",'
                '"accepted_answers":["goes"],"explanation":"一般现在时第三人称单数加 es。"}'
                ']},'
                '"display_html":"<section>一般现在时</section>"}'
            ),
        ),
        (
            "explore.capability_rerank",
            {
                "context": {"target_label": "significant", "learning_skill": "vocabulary"},
                "candidates": [{"capability_id": "vocabulary-detail", "title": "词汇详解"}],
            },
            (
                '{"recommendations":[{"capability_id":"vocabulary-detail",'
                '"priority_score":0.91,"reason":"significant 是真实词汇，适合详解。"}]}'
            ),
        ),
    ],
)
async def test_registered_structured_prompts_accept_schema_valid_output(
    prompt_id: str,
    variables: dict[str, object],
    raw_output: str,
) -> None:
    result = await PromptExecutor().execute_with_raw_output(
        prompt_id=prompt_id,
        version="v1",
        variables=variables,
        raw_output=raw_output,
        context=PromptExecutionContext(source_module="tests.prompt_regression"),
    )

    assert result.schema_validation_status == "passed"
    assert result.decision == "accepted"
    assert result.validated_output is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt_id", "variables", "raw_output"),
    [
        (
            "vocabulary.agent.extract",
            {"user_message": "deposit", "assistant_reply": "deposit 表示押金。"},
            (
                'Sure:\n{"cards":[{"word":"deposit","phonetic":"/dɪˈpɑːzɪt/",'
                '"definition_zh":"押金","definition_en":"money paid as security",'
                '"examples":[{"sentence":"I paid a deposit."}],"confidence":0.88}]}'
            ),
        ),
        (
            "writing_phrase.import",
            {"topic": "environment", "task_type": "generate"},
            (
                'Result:\n{"candidates":[{"text":"It is widely acknowledged that...",'
                '"examples":[{"sentence":"It is widely acknowledged that daily action matters."}],'
                '"quality_score":0.84}]}'
            ),
        ),
        (
            "exercise.generate",
            {
                "count": 1,
                "target_type": "vocabulary_item",
                "target_id": "significant",
                "target_label": "significant",
                "allowed_types": "single_choice, fill_blank",
                "context_text": "例子：The result is significant.",
            },
            (
                'Sure:\n{"items":[{"skill":"vocabulary","type":"single_choice",'
                '"prompt":"What does significant mean?","options":["important","tiny","silent","ancient"],'
                '"correctAnswer":"important","acceptedAnswers":["important"],'
                '"explanation":"significant 表示重要的、显著的。","difficulty":"easy"}]}'
            ),
        ),
        (
            "grammar.micro_lesson.structured",
            {"topic_title": "冠词"},
            (
                'Sure, here is the structured lesson:\n{"machine_data":{"topic":"冠词","core_rules":["a/an 泛指。"],'
                '"examples":[{"sentence":"I have a pen."}],"mistakes":["an 用错"],'
                '"exercises":['
                '{"type":"grammar_fill_blank","prompt":"I have ___ apple.","answer":"an",'
                '"accepted_answers":["an"],"explanation":"apple 以元音音素开头。"},'
                '{"type":"grammar_fill_blank","prompt":"She is ___ teacher.","answer":"a",'
                '"accepted_answers":["a"],"explanation":"teacher 以辅音音素开头。"}'
                ']},'
                '"display_html":"<section>冠词</section>"}'
            ),
        ),
        (
            "explore.capability_rerank",
            {
                "context": {"target_label": "一般现在时", "learning_skill": "grammar"},
                "candidates": [{"capability_id": "grammar-explain", "title": "语法微课"}],
            },
            (
                'JSON:\n{"recommendations":[{"capability_id":"grammar-explain",'
                '"priority_score":0.92,"reason":"错因是语法规则混淆，适合语法微课。"}]}'
            ),
        ),
    ],
)
async def test_registered_structured_prompts_accept_repaired_json(
    prompt_id: str,
    variables: dict[str, object],
    raw_output: str,
) -> None:
    result = await PromptExecutor().execute_with_raw_output(
        prompt_id=prompt_id,
        version="v1",
        variables=variables,
        raw_output=raw_output,
        context=PromptExecutionContext(source_module="tests.prompt_regression"),
    )

    assert result.schema_validation_status == "repaired"
    assert result.repair_used is True
    assert result.decision == "accepted"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt_id", "variables", "raw_output"),
    [
        ("vocabulary.agent.extract", {"user_message": "hi"}, '{"cards":[{"word":"hi"}]}'),
        ("writing_phrase.import", {"topic": "online learning"}, '{"candidates":"bad"}'),
        ("exercise.generate", {"count": 1}, '{"items":[{"prompt":"I have ___ apple."}]}'),
        (
            "grammar.micro_lesson.structured",
            {"topic_title": "代词"},
            '{"machine_data":{"topic":"代词"},"display_html":"<section></section>"}',
        ),
        (
            "explore.capability_rerank",
            {"context": {"target_label": "Alice"}, "candidates": []},
            '{"recommendations":[{"capability_id":"word-roots-affixes"}]}',
        ),
    ],
)
async def test_registered_structured_prompts_reject_schema_invalid_output(
    prompt_id: str,
    variables: dict[str, object],
    raw_output: str,
) -> None:
    result = await PromptExecutor().execute_with_raw_output(
        prompt_id=prompt_id,
        version="v1",
        variables=variables,
        raw_output=raw_output,
        context=PromptExecutionContext(source_module="tests.prompt_regression"),
    )

    assert result.schema_validation_status == "failed"
    assert result.decision == "rejected"
    assert result.validated_output is None


@pytest.mark.asyncio
async def test_writing_phrase_fallback_is_review_required() -> None:
    raw_output = (
        "英文句式：What matters most is that...\n"
        "例句：What matters most is that technology should serve learning."
    )

    result = await PromptExecutor().execute_with_raw_output(
        prompt_id="writing_phrase.import",
        version="v1",
        variables={"topic": "technology", "task_type": "extract_phrases"},
        raw_output=raw_output,
        context=PromptExecutionContext(source_module="tests.prompt_regression"),
        fallback_parser=lambda value: writing_phrase_regex_fallback_payload(value, "technology"),
    )

    assert result.schema_validation_status == "fallback"
    assert result.fallback_used is True
    assert result.decision == "review_required"
    assert result.decision != "accepted"
