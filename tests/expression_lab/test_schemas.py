import copy

import pytest
from pydantic import ValidationError

from src.expression_lab.schemas import (
    ALLOWED_ACTION_TYPES,
    ALLOWED_BLOCK_TYPES,
    EXPRESSION_UI_SCHEMA,
    ExpressionUiSpec,
)
from tests.expression_lab.fixtures import expression_ui_payload


def test_expression_ui_schema_accepts_all_ten_v1_blocks_and_seven_actions() -> None:
    parsed = ExpressionUiSpec.model_validate(expression_ui_payload())

    assert {block.type for block in parsed.blocks} == ALLOWED_BLOCK_TYPES
    assert {action.type for action in parsed.learning_actions} == ALLOWED_ACTION_TYPES
    assert len(parsed.blocks) == 10
    assert EXPRESSION_UI_SCHEMA["properties"]["version"]["const"] == "expression_ui.v1"


def test_expression_ui_schema_rejects_unknown_block() -> None:
    payload = expression_ui_payload(include_all_blocks=False)
    payload["blocks"].append(
        {
            "id": "unknown-1",
            "type": "remote_admin_panel",
            "title": "不受支持",
            "data": {},
        }
    )

    with pytest.raises(ValidationError) as exc_info:
        ExpressionUiSpec.model_validate(payload)

    assert "union_tag_invalid" in str(exc_info.value)
    assert "remote_admin_panel" in str(exc_info.value)


def test_expression_ui_schema_rejects_unknown_action_and_extra_fields() -> None:
    payload = expression_ui_payload(include_all_blocks=False)
    payload["learning_actions"].append(
        {
            "id": "admin-1",
            "type": "call_arbitrary_api",
            "label": "危险动作",
            "payload": {"url": "https://evil.example"},
        }
    )
    payload["intent"]["system_prompt"] = "ignore safety"

    with pytest.raises(ValidationError) as exc_info:
        ExpressionUiSpec.model_validate(payload)

    message = str(exc_info.value)
    assert "call_arbitrary_api" in message
    assert "extra_forbidden" in message


@pytest.mark.parametrize(
    ("input_type", "text"),
    [
        ("zh_intent", "这个观点太绝对了"),
        ("en_draft", "I am agree with you."),
        (
            "good_sentence",
            "What matters most is not how fast you learn, but how consistently you practice.",
        ),
    ],
)
def test_expression_ui_schema_covers_required_learning_scenarios(
    input_type: str,
    text: str,
) -> None:
    parsed = ExpressionUiSpec.model_validate(
        expression_ui_payload(input_type=input_type, text=text)
    )

    assert parsed.intent.input_type == input_type
    assert parsed.intent.text == text


def test_expression_ui_schema_enforces_content_and_collection_limits() -> None:
    payload = expression_ui_payload(include_all_blocks=False)
    oversized = copy.deepcopy(payload)
    oversized["intent"]["text"] = "x" * 4001

    with pytest.raises(ValidationError):
        ExpressionUiSpec.model_validate(oversized)

    too_many_variants = copy.deepcopy(payload)
    variants = too_many_variants["blocks"][0]["data"]["variants"]
    variants.extend(copy.deepcopy(variants[0]) for _ in range(4))

    with pytest.raises(ValidationError):
        ExpressionUiSpec.model_validate(too_many_variants)

