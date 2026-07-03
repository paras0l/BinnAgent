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
            "grammar.micro_lesson.structured",
            {"topic_title": "一般现在时"},
            (
                '{"machine_data":{"topic":"一般现在时","core_rules":["动词随主语变化。"],'
                '"examples":[{"sentence":"She likes English."}],"mistakes":["漏掉 s"],'
                '"exercises":[{"question":"She ___ English.","answer":"likes"}]},'
                '"display_html":"<section>一般现在时</section>"}'
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
            "grammar.micro_lesson.structured",
            {"topic_title": "冠词"},
            (
                'Sure, here is the structured lesson:\n{"machine_data":{"topic":"冠词","core_rules":["a/an 泛指。"],'
                '"examples":[{"sentence":"I have a pen."}],"mistakes":["an 用错"],'
                '"exercises":[{"question":"___ apple","answer":"an"}]},'
                '"display_html":"<section>冠词</section>"}'
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
        (
            "grammar.micro_lesson.structured",
            {"topic_title": "代词"},
            '{"machine_data":{"topic":"代词"},"display_html":"<section></section>"}',
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
