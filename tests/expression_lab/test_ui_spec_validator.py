import copy
import json
import uuid

from src.expression_lab.schemas import ExpressionUiSpec
from src.expression_lab.ui_spec_validator import (
    build_fixed_fallback,
    build_text_fallback,
    expression_ui_fallback_parser,
    split_grading_spec,
    validate_ui_spec,
)
from tests.expression_lab.fixtures import expression_ui_payload


def test_validate_ui_spec_accepts_all_blocks_and_overrides_model_identity_fields() -> None:
    requested_session_id = str(uuid.uuid4())
    payload = expression_ui_payload()
    payload["source"] = {"type": "group_learning_signal", "source_id": "forged"}
    payload["intent"] = {
        "input_type": "good_sentence",
        "text": "forged input",
        "context": "forged context",
        "goal": "forged goal",
    }

    result = validate_ui_spec(
        payload,
        session_id=requested_session_id,
        input_text="I am agree with you.",
        input_type="en_draft",
        context="formal_writing",
        style_goal="natural",
        source_type="manual",
        source_ref=None,
    )

    assert result.valid is True
    assert result.spec is not None
    assert result.spec.session_id == requested_session_id
    assert result.spec.source.type == "manual"
    assert result.spec.source.source_id is None
    assert result.spec.intent.input_type == "en_draft"
    assert result.spec.intent.text == "I am agree with you."
    assert result.spec.intent.context == "formal_writing"
    assert result.spec.intent.goal == "natural"
    assert len(result.spec.blocks) == 10


def test_validate_ui_spec_removes_unknown_block_but_keeps_known_content() -> None:
    payload = expression_ui_payload(include_all_blocks=False)
    payload["blocks"].insert(
        0,
        {
            "id": "unknown-1",
            "type": "remote_admin_panel",
            "title": "危险模块",
            "data": {"endpoint": "/api/admin"},
        },
    )

    result = validate_ui_spec(payload)

    assert result.valid is True
    assert result.fallback_stage == "unsupported_removed"
    assert result.removed_block_ids == ("unknown-1",)
    assert "removed_unsupported_block:remote_admin_panel" in result.issues
    assert result.spec is not None
    assert {block.type for block in result.spec.blocks} == {
        "expression_variants",
        "micro_practice",
    }


def test_validate_ui_spec_rejects_when_no_valid_block_remains() -> None:
    payload = expression_ui_payload(include_all_blocks=False)
    payload["blocks"] = [
        {
            "id": "unknown-1",
            "type": "remote_admin_panel",
            "title": "危险模块",
            "data": {},
        }
    ]

    result = validate_ui_spec(payload)

    assert result.valid is False
    assert result.spec is None
    assert result.removed_block_ids == ("unknown-1",)
    assert any(issue.startswith("invalid_ui_spec:blocks") for issue in result.issues)


def test_validate_ui_spec_forces_save_confirmation_and_filters_editable_fields() -> None:
    payload = expression_ui_payload(include_all_blocks=False)
    save_action = payload["learning_actions"][0]
    save_action["requires_confirmation"] = False
    save_action["editable_fields"] = [
        "text",
        "chinese_meaning",
        "action_type",
        "learner_id",
        "__class__",
    ]

    result = validate_ui_spec(payload)

    assert result.valid is True
    assert result.spec is not None
    saved = next(action for action in result.spec.learning_actions if action.id == "save-phrase-1")
    assert saved.requires_confirmation is True
    assert saved.editable_fields == ["text", "chinese_meaning"]
    assert "forced_confirmation:save-phrase-1" in result.issues


def test_validate_ui_spec_sanitizes_sandbox_and_hides_practice_answers_from_render_payload() -> None:
    payload = expression_ui_payload()
    sandbox = next(block for block in payload["blocks"] if block["type"] == "sandbox_widget")
    sandbox["data"].update(
        {
            "html": '<script>alert(1)</script><button onclick="fetch(\'/collect\')">go</button>',
            "css": '@import "https://evil.example/a.css"; button { color: red; }',
            "javascript": "window.parent.postMessage(localStorage.getItem('token'), '*')",
            "allowed_events": ["interaction", "network_request"],
        }
    )

    result = validate_ui_spec(payload)

    assert result.valid is True
    assert result.payload is not None
    assert result.render_payload is not None
    assert result.grading_spec["practice-1"]["question-1"]["answer"]
    rendered_practice = next(
        block
        for block in result.render_payload["blocks"]
        if block["type"] == "micro_practice"
    )
    question = rendered_practice["data"]["questions"][0]
    assert "answer" not in question
    assert "accepted_answers" not in question
    assert "explanation" not in question
    rendered_sandbox = next(
        block
        for block in result.render_payload["blocks"]
        if block["type"] == "sandbox_widget"
    )
    assert "script" not in rendered_sandbox["data"]["html"]
    assert "onclick" not in rendered_sandbox["data"]["html"]
    assert "https://evil.example" not in rendered_sandbox["data"]["css"]
    assert rendered_sandbox["data"]["javascript"] == ""
    assert rendered_sandbox["data"]["allowed_events"] == ["interaction"]


def test_split_grading_spec_does_not_mutate_the_full_payload() -> None:
    payload = ExpressionUiSpec.model_validate(expression_ui_payload()).model_dump(mode="json")
    original = copy.deepcopy(payload)

    render_payload, grading = split_grading_spec(payload)

    assert payload == original
    assert grading["practice-1"]["question-1"]["answer"]
    rendered_question = next(
        block for block in render_payload["blocks"] if block["id"] == "practice-1"
    )["data"]["questions"][0]
    assert "answer" not in rendered_question


def test_expression_ui_fallback_parser_repairs_wrapped_valid_json() -> None:
    payload = expression_ui_payload(include_all_blocks=False)
    raw_output = f"Here is the requested JSON:\n{json.dumps(payload, ensure_ascii=False)}"

    repaired = expression_ui_fallback_parser(
        raw_output,
        session_id=payload["session_id"],
        input_text=payload["intent"]["text"],
    )

    assert repaired is not None
    assert repaired["blocks"][0]["type"] == "expression_variants"
    assert repaired["intent"]["text"] == payload["intent"]["text"]


def test_expression_ui_fallback_parser_builds_fixed_fallback_for_invalid_output() -> None:
    session_id = str(uuid.uuid4())

    fallback = expression_ui_fallback_parser(
        '{"version":"expression_ui.v1","blocks":[]}',
        session_id=session_id,
        input_text="这个观点太绝对了",
        input_type="zh_intent",
        context="group_chat",
        style_goal="polite",
    )

    assert fallback is not None
    assert fallback["session_id"] == session_id
    assert [block["type"] for block in fallback["blocks"]] == [
        "expression_variants",
        "micro_practice",
    ]
    assert fallback["learning_actions"][0]["type"] == "copy_expression"


def test_expression_ui_fallback_parser_rejects_without_any_trusted_session_id() -> None:
    assert expression_ui_fallback_parser("not json and no session") is None


def test_fixed_and_text_fallbacks_are_schema_valid_and_never_echo_markup() -> None:
    session_id = str(uuid.uuid4())
    fixed = build_fixed_fallback(
        session_id=session_id,
        input_text="<script>alert(1)</script>这个观点太绝对了",
    )
    text = build_text_fallback(
        session_id=session_id,
        input_text="<script>alert(1)</script>这个观点太绝对了",
    )

    ExpressionUiSpec.model_validate(fixed)
    ExpressionUiSpec.model_validate(text)
    assert "<script>" not in json.dumps(fixed, ensure_ascii=False)
    assert text["fallback_message"]
    assert len(text["blocks"]) == 1


def test_fixed_fallback_keeps_confirmed_asset_actions_for_every_input_type() -> None:
    session_id = str(uuid.uuid4())
    cases = [
        ("zh_intent", "这个观点太绝对了", "save_writing_phrase"),
        ("en_draft", "I am agree with you.", "save_grammar_point"),
        (
            "good_sentence",
            "What matters most is not speed, but consistency.",
            "save_writing_phrase",
        ),
        ("learning_target", "resilient", "save_vocabulary"),
        ("learning_target", "present perfect 时态", "save_grammar_point"),
    ]

    for input_type, input_text, expected_action in cases:
        fallback = build_fixed_fallback(
            session_id=session_id,
            input_type=input_type,
            input_text=input_text,
            context="group_chat",
        )
        actions = fallback["learning_actions"]
        matching = [action for action in actions if action["type"] == expected_action]
        assert matching, (input_type, expected_action)
        assert all(action["requires_confirmation"] is True for action in matching)
        assert all(action["editable_fields"] for action in matching)
        if input_type == "good_sentence":
            assert all(action["payload"]["template"] for action in matching)


def test_english_draft_fallback_explains_and_saves_recognized_grammar_error() -> None:
    fallback = build_fixed_fallback(
        session_id=str(uuid.uuid4()),
        input_type="en_draft",
        input_text="I am agree with you.",
    )

    assert {block["type"] for block in fallback["blocks"]} >= {
        "sentence_diff",
        "grammar_focus",
        "micro_practice",
    }
    grammar_action = next(
        action
        for action in fallback["learning_actions"]
        if action["type"] == "save_grammar_point"
    )
    assert grammar_action["block_id"] == "fallback-grammar-focus"
    assert grammar_action["payload"]["correction"] == "I agree with you."
