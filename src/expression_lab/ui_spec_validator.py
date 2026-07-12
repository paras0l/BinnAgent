from __future__ import annotations

import copy
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter, ValidationError

from src.expression_lab.renderer_policy import sanitize_html, sanitize_sandbox_widget
from src.expression_lab.schemas import (
    ALLOWED_ACTION_TYPES,
    ALLOWED_BLOCK_TYPES,
    SAVE_ACTION_TYPES,
    ExpressionBlock,
    ExpressionUiSpec,
    LearningAction,
)
from src.prompts.repair import parse_json_object_with_repair


_BLOCK_ADAPTER = TypeAdapter(ExpressionBlock)
_ACTION_ADAPTER = TypeAdapter(LearningAction)
_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,119}$")
_EDITABLE_FIELDS: dict[str, frozenset[str]] = {
    "save_writing_phrase": frozenset(
        {
            "text",
            "chinese_meaning",
            "explanation",
            "usage_scene",
            "register",
            "template",
            "examples",
            "tags",
        }
    ),
    "save_vocabulary": frozenset(
        {"word", "meaning", "collocations", "examples", "source_expression", "reason"}
    ),
    "save_grammar_point": frozenset(
        {"topic", "rule", "error", "correction", "minimal_pairs"}
    ),
}


@dataclass(frozen=True)
class UiSpecValidationResult:
    valid: bool
    spec: ExpressionUiSpec | None
    payload: dict[str, Any] | None
    render_payload: dict[str, Any] | None
    grading_spec: dict[str, Any]
    issues: tuple[str, ...]
    removed_block_ids: tuple[str, ...] = ()
    removed_action_ids: tuple[str, ...] = ()
    fallback_stage: str | None = None


def validate_ui_spec(
    payload: dict[str, Any],
    *,
    session_id: str | uuid.UUID | None = None,
    input_text: str | None = None,
    input_type: str = "zh_intent",
    context: str | None = None,
    style_goal: str | None = None,
    source_type: str = "manual",
    source_ref: str | None = None,
) -> UiSpecValidationResult:
    """Validate, sanitize and normalize model-produced Expression UI DSL.

    Unsupported or malformed individual blocks/actions are removed. The function is
    pure and deliberately does not execute any proposed action.
    """

    candidate = copy.deepcopy(payload) if isinstance(payload, dict) else {}
    issues: list[str] = []
    removed_blocks: list[str] = []
    removed_actions: list[str] = []

    normalized_session_id = _valid_session_id(session_id or candidate.get("session_id"))
    if normalized_session_id is None:
        return UiSpecValidationResult(
            valid=False,
            spec=None,
            payload=None,
            render_payload=None,
            grading_spec={},
            issues=("invalid_session_id",),
        )
    candidate["version"] = "expression_ui.v1"
    candidate["session_id"] = normalized_session_id
    candidate["source"] = {
        "type": source_type if source_type in {"manual", "group_learning_signal"} else "manual",
        "source_id": source_ref,
    }
    raw_intent = candidate.get("intent") if isinstance(candidate.get("intent"), dict) else {}
    normalized_input_type = input_type if input_type in {
        "zh_intent",
        "en_draft",
        "good_sentence",
        "learning_target",
    } else "zh_intent"
    candidate["intent"] = {
        "input_type": normalized_input_type,
        "text": (input_text or raw_intent.get("text") or "需要更自然的英语表达")[:4000],
        "context": context if context is not None else raw_intent.get("context"),
        "goal": style_goal if style_goal is not None else raw_intent.get("goal"),
    }
    candidate.setdefault("layout", "adaptive")
    candidate.setdefault("suggested_assets", [])
    candidate.setdefault("learning_actions", [])

    clean_blocks: list[dict[str, Any]] = []
    seen_block_ids: set[str] = set()
    raw_blocks = candidate.get("blocks") if isinstance(candidate.get("blocks"), list) else []
    for index, raw_block in enumerate(raw_blocks):
        if not isinstance(raw_block, dict):
            removed_blocks.append(f"block-{index + 1}")
            issues.append("removed_non_object_block")
            continue
        block_id = str(raw_block.get("id") or f"block-{index + 1}")[:120]
        block_type = raw_block.get("type")
        if block_type not in ALLOWED_BLOCK_TYPES:
            removed_blocks.append(block_id)
            issues.append(f"removed_unsupported_block:{block_type}")
            continue
        if not _SAFE_ID.fullmatch(block_id) or block_id in seen_block_ids:
            removed_blocks.append(block_id)
            issues.append("removed_duplicate_or_invalid_block_id")
            continue
        normalized_block = copy.deepcopy(raw_block)
        normalized_block["id"] = block_id
        if block_type == "sandbox_widget":
            data = normalized_block.get("data")
            if isinstance(data, dict):
                sanitized = sanitize_sandbox_widget(
                    str(data.get("html") or ""),
                    str(data.get("css") or ""),
                    str(data.get("javascript") or ""),
                )
                data["html"] = sanitized.html
                data["css"] = sanitized.css
                data["javascript"] = sanitized.javascript
                allowed = set(data.get("allowed_events") or [])
                data["allowed_events"] = sorted(
                    allowed.intersection(
                        {
                            "selection_changed",
                            "answer_submitted",
                            "interaction",
                            "action",
                            "answer",
                            "change",
                        }
                    )
                )
                issues.extend(f"sandbox:{issue}" for issue in sanitized.issues)
        elif block_type == "pattern_diagram":
            data = normalized_block.get("data")
            if isinstance(data, dict) and data.get("svg"):
                data["svg"], svg_issues = sanitize_html(str(data["svg"]))
                issues.extend(f"svg:{issue}" for issue in svg_issues)
        try:
            block = _BLOCK_ADAPTER.validate_python(normalized_block)
        except ValidationError:
            removed_blocks.append(block_id)
            issues.append(f"removed_invalid_block:{block_id}")
            continue
        seen_block_ids.add(block_id)
        clean_blocks.append(block.model_dump(mode="json", by_alias=True))
    candidate["blocks"] = clean_blocks

    clean_actions: list[dict[str, Any]] = []
    seen_action_ids: set[str] = set()
    raw_actions = (
        candidate.get("learning_actions")
        if isinstance(candidate.get("learning_actions"), list)
        else []
    )
    for index, raw_action in enumerate(raw_actions):
        if not isinstance(raw_action, dict):
            removed_actions.append(f"action-{index + 1}")
            issues.append("removed_non_object_action")
            continue
        action_id = str(raw_action.get("id") or f"action-{index + 1}")[:120]
        action_type = raw_action.get("type")
        if action_type not in ALLOWED_ACTION_TYPES:
            removed_actions.append(action_id)
            issues.append(f"removed_unsupported_action:{action_type}")
            continue
        if not _SAFE_ID.fullmatch(action_id) or action_id in seen_action_ids:
            removed_actions.append(action_id)
            issues.append("removed_duplicate_or_invalid_action_id")
            continue
        normalized_action = copy.deepcopy(raw_action)
        normalized_action["id"] = action_id
        if action_type in SAVE_ACTION_TYPES:
            if not normalized_action.get("requires_confirmation"):
                issues.append(f"forced_confirmation:{action_id}")
            normalized_action["requires_confirmation"] = True
        allowed_editable = _EDITABLE_FIELDS.get(str(action_type), frozenset())
        if "editable_fields" in normalized_action:
            editable = normalized_action.get("editable_fields") or []
        else:
            action_payload = normalized_action.get("payload")
            editable = list(action_payload) if isinstance(action_payload, dict) else []
        normalized_action["editable_fields"] = [
            field for field in editable if isinstance(field, str) and field in allowed_editable
        ]
        block_id = normalized_action.get("block_id")
        if block_id is not None and block_id not in seen_block_ids:
            normalized_action["block_id"] = None
            issues.append(f"cleared_unknown_action_block:{action_id}")
        try:
            action = _ACTION_ADAPTER.validate_python(normalized_action)
        except ValidationError:
            removed_actions.append(action_id)
            issues.append(f"removed_invalid_action:{action_id}")
            continue
        seen_action_ids.add(action_id)
        clean_actions.append(action.model_dump(mode="json", by_alias=True))
    candidate["learning_actions"] = clean_actions

    valid_action_ids = {action["id"] for action in clean_actions}
    clean_assets = []
    for raw_asset in candidate.get("suggested_assets") or []:
        if isinstance(raw_asset, dict) and raw_asset.get("action_id") in valid_action_ids:
            clean_assets.append(raw_asset)
    candidate["suggested_assets"] = clean_assets

    try:
        spec = ExpressionUiSpec.model_validate(candidate)
    except ValidationError as exc:
        issues.append(f"invalid_ui_spec:{_summarize_validation_error(exc)}")
        return UiSpecValidationResult(
            valid=False,
            spec=None,
            payload=None,
            render_payload=None,
            grading_spec={},
            issues=tuple(dict.fromkeys(issues)),
            removed_block_ids=tuple(removed_blocks),
            removed_action_ids=tuple(removed_actions),
        )

    full_payload = spec.model_dump(mode="json", by_alias=True)
    render_payload, grading_spec = split_grading_spec(full_payload)
    return UiSpecValidationResult(
        valid=True,
        spec=spec,
        payload=full_payload,
        render_payload=render_payload,
        grading_spec=grading_spec,
        issues=tuple(dict.fromkeys(issues)),
        removed_block_ids=tuple(removed_blocks),
        removed_action_ids=tuple(removed_actions),
        fallback_stage="unsupported_removed" if removed_blocks or removed_actions else None,
    )


def split_grading_spec(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Remove answers/rubrics from the learner-visible payload."""

    render_payload = copy.deepcopy(payload)
    grading: dict[str, Any] = {}
    for block in render_payload.get("blocks", []):
        if block.get("type") != "micro_practice":
            continue
        block_grading: dict[str, Any] = {}
        for question in block.get("data", {}).get("questions", []):
            question_id = str(question.get("id") or "")
            block_grading[question_id] = {
                "answer": question.pop("answer", ""),
                "accepted_answers": question.pop("accepted_answers", []),
                "target_expression": question.pop("target_expression", None),
                "explanation": question.pop("explanation", ""),
                "hint": question.get("hint", ""),
                "type": question.get("type"),
                "skill": question.get("skill", "writing"),
                "prompt": question.get("prompt", ""),
            }
        grading[str(block.get("id"))] = block_grading
    return render_payload, grading


def expression_ui_fallback_parser(
    raw_output: str,
    *,
    session_id: str | uuid.UUID | None = None,
    input_text: str = "需要更自然的英语表达",
    input_type: str = "zh_intent",
    context: str | None = None,
    style_goal: str | None = None,
    source_type: str = "manual",
    source_ref: str | None = None,
) -> dict[str, Any] | None:
    """PromptExecutor fallback: parse JSON, prune unsafe nodes, then fixed fallback."""

    parsed = parse_json_object_with_repair(raw_output)
    effective_session_id = _valid_session_id(
        session_id or (parsed.payload or {}).get("session_id")
    )
    if effective_session_id is None:
        return None
    if parsed.payload is not None:
        result = validate_ui_spec(
            parsed.payload,
            session_id=effective_session_id,
            input_text=input_text,
            input_type=input_type,
            context=context,
            style_goal=style_goal,
            source_type=source_type,
            source_ref=source_ref,
        )
        if result.valid and result.payload is not None:
            return result.payload
    return build_fixed_fallback(
        session_id=effective_session_id,
        input_text=input_text,
        input_type=input_type,
        context=context,
        style_goal=style_goal,
        source_type=source_type,
        source_ref=source_ref,
    )


def build_fixed_fallback(
    *,
    session_id: str | uuid.UUID,
    input_text: str,
    input_type: str = "zh_intent",
    context: str | None = None,
    style_goal: str | None = None,
    source_type: str = "manual",
    source_ref: str | None = None,
) -> dict[str, Any]:
    text = _plain_text(input_text)[:800] or "this idea"
    first, second, first_zh, second_zh = _fallback_variants(text, input_type)
    extra_blocks = _fallback_extra_blocks(text, input_type, first, second)
    target_expression = _fallback_target_expression(first, second, input_type)
    payload = {
        "version": "expression_ui.v1",
        "session_id": str(session_id),
        "source": {"type": source_type, "source_id": source_ref},
        "intent": {
            "input_type": input_type,
            "text": text,
            "context": context,
            "goal": style_goal,
        },
        "layout": "adaptive",
        "blocks": [
            {
                "id": "fallback-variants",
                "type": "expression_variants",
                "title": "可先使用的表达",
                "description": "生成内容已安全降级，你仍可比较并继续练习。",
                "data": {
                    "variants": [
                        {
                            "id": "fallback-neutral",
                            "text": first,
                            "chinese_explanation": first_zh,
                            "context": context or "通用",
                            "tone_tags": ["中性"],
                            "naturalness": 88,
                            "difficulty": 2,
                            "why_it_works": first_zh,
                            "use_when": _fallback_use_when(context, "neutral"),
                            "avoid_when": "",
                            "key_pattern": target_expression,
                            "example": first,
                            "example_translation": first_zh,
                            "action_id": "fallback-copy-neutral",
                        },
                        {
                            "id": "fallback-soft",
                            "text": second,
                            "chinese_explanation": second_zh,
                            "context": context or "通用",
                            "tone_tags": ["委婉"],
                            "naturalness": 91,
                            "difficulty": 2,
                            "why_it_works": second_zh,
                            "use_when": _fallback_use_when(context, "soft"),
                            "avoid_when": "需要明确纠正事实错误或安全风险时。",
                            "key_pattern": target_expression,
                            "example": second,
                            "example_translation": second_zh,
                            "action_id": "fallback-copy-soft",
                        },
                    ]
                },
                "ui": {"collapsible": False, "emphasis": "primary"},
            },
            *extra_blocks,
            {
                "id": "fallback-practice",
                "type": "micro_practice",
                "title": "马上练一下",
                "description": "用更委婉的框架重写输入。",
                "data": {
                    "instructions": "用更自然或更委婉的英语改写。",
                    "questions": [
                        {
                            "id": "fallback-question-1",
                            "type": "rewrite",
                            "prompt": f"请改写：{text}",
                            "options": [],
                            "answer": second,
                            "accepted_answers": [first, second],
                            "target_expression": target_expression,
                            "hint": f"尝试使用：{target_expression}",
                            "explanation": "先保留原意，再根据语境、语气和句型结构完成迁移。",
                            "skill": "writing",
                        }
                    ],
                },
                "ui": {"collapsible": False, "emphasis": "secondary"},
            },
        ],
        "suggested_assets": [],
        "learning_actions": [
            {
                "id": "fallback-copy-neutral",
                "type": "copy_expression",
                "label": "复制中性表达",
                "block_id": "fallback-variants",
                "payload": {"text": first},
                "requires_confirmation": False,
                "editable_fields": [],
            },
            {
                "id": "fallback-copy-soft",
                "type": "copy_expression",
                "label": "复制委婉表达",
                "block_id": "fallback-variants",
                "payload": {"text": second},
                "requires_confirmation": False,
                "editable_fields": [],
            },
            *_fallback_save_actions(
                input_type=input_type,
                input_text=text,
                context=context,
                first=first,
                second=second,
                first_zh=first_zh,
                second_zh=second_zh,
            ),
        ],
    }
    return ExpressionUiSpec.model_validate(payload).model_dump(mode="json", by_alias=True)


def _fallback_use_when(context: str | None, tone: str) -> str:
    scene = {
        "daily_chat": "日常聊天",
        "group_chat": "群聊讨论",
        "exam_writing": "考试写作",
        "formal_communication": "正式沟通",
    }.get(context or "", "一般交流")
    if tone == "soft":
        return f"在{scene}中想保留意见、同时降低对抗感时。"
    return f"在{scene}中需要清楚表达核心意思时。"


def _fallback_variants(
    text: str, input_type: str
) -> tuple[str, str, str, str]:
    if input_type == "zh_intent":
        if "绝对" in text or "太强" in text:
            return (
                "That point may be too absolute.",
                "That claim may be a little too strong.",
                "中性地指出观点过于绝对，适合讨论或写作。",
                "更委婉，先用 may 和 a little 降低对抗感。",
            )
        if "不同意" in text or "不赞同" in text:
            return (
                "I'm not sure I completely agree.",
                "I see your point, but I have a different view.",
                "清楚表达保留意见，但不过度强硬。",
                "先承认对方观点，再提出不同看法，更适合群聊讨论。",
            )
        if "建议" in text or "考虑" in text:
            return (
                "It might be worth considering another approach.",
                "Perhaps we could look at this from a different angle.",
                "用 might be worth 提出克制、可执行的建议。",
                "用 perhaps/could 让建议更有合作感。",
            )
        return (
            "Here's another way to look at it.",
            "I'd put it a little differently.",
            "用于自然引出另一种看法，不假装已经完成逐字翻译。",
            "适合先礼貌接话，再补充自己的具体表达。",
        )
    if input_type == "en_draft":
        corrected = _repair_common_english_draft(text)
        alternative = (
            "I agree with the main idea, though I'd add one qualification."
            if re.search(r"\bagree\b", corrected, flags=re.IGNORECASE)
            else f"I'd express it this way: {corrected}"
        )
        return (
            corrected,
            alternative,
            "保留原意并修复可确定的常见语法问题。",
            "提供更自然、语气更完整的替代表达。",
        )
    if input_type == "good_sentence":
        return (
            text,
            "What stands out is not only the idea itself, but also how clearly it is expressed.",
            "保留原好句，避免降级时擅自覆盖用户素材。",
            "提供可迁移的 not only ... but also ... 结构。",
        )
    example = _learning_target_example(text)
    return (
        example,
        f"Try using “{text}” in a sentence about a real experience.",
        "先给出一个完整、可观察的目标表达例句。",
        "把学习目标迁移到自己的真实经历中。",
    )


def _fallback_extra_blocks(
    text: str,
    input_type: str,
    first: str,
    second: str,
) -> list[dict[str, Any]]:
    if input_type == "en_draft":
        blocks = [
            {
                "id": "fallback-sentence-diff",
                "type": "sentence_diff",
                "title": "草稿修正",
                "description": "先看确定性较高的常见语法修复。",
                "data": {
                    "original": text,
                    "corrected": first,
                    "changes": [
                        {
                            "operation": "replace",
                            "original": text,
                            "replacement": first,
                            "explanation": _draft_repair_explanation(text, first),
                        }
                    ],
                    "summary": "修复结构后，再比较更自然的替代表达。",
                },
                "ui": {"collapsible": False, "emphasis": "primary"},
            }
        ]
        if re.search(r"\b(?:am|is|are)\s+agree\b", text, flags=re.IGNORECASE):
            blocks.append(
                {
                    "id": "fallback-grammar-focus",
                    "type": "grammar_focus",
                    "title": "agree 作为动词",
                    "description": "用最小对比看清 agree 与 be 动词的关系。",
                    "data": {
                        "topic": "agree 作为动词",
                        "rule": "agree 在这里是实义动词，直接说 I agree，不使用 be + agree。",
                        "error": text,
                        "correction": first,
                        "minimal_pairs": [
                            {
                                "wrong": "I am agree with you.",
                                "correct": "I agree with you.",
                                "explanation": "删除 am，让 agree 直接作谓语。",
                            }
                        ],
                    },
                    "ui": {"collapsible": False, "emphasis": "secondary"},
                }
            )
        return blocks
    if input_type == "good_sentence":
        return [
            {
                "id": "fallback-pattern",
                "type": "pattern_diagram",
                "title": "抽出可迁移结构",
                "description": "把好句从一次性素材变成可以复用的模板。",
                "data": {
                    "pattern": "What stands out is not only + [idea A] + but also + [idea B]",
                    "nodes": [
                        {"id": "fixed", "label": "What stands out is not only", "kind": "fixed"},
                        {"id": "idea-a", "label": "idea A", "kind": "slot"},
                        {"id": "connector", "label": "but also", "kind": "connector"},
                        {"id": "idea-b", "label": "idea B", "kind": "slot"},
                    ],
                    "edges": [
                        {"source": "fixed", "target": "idea-a", "label": ""},
                        {"source": "idea-a", "target": "connector", "label": ""},
                        {"source": "connector", "target": "idea-b", "label": ""},
                    ],
                    "example": second,
                },
                "ui": {"collapsible": False, "emphasis": "secondary"},
            },
            {
                "id": "fallback-transfer",
                "type": "transfer_builder",
                "title": "换内容继续用",
                "description": "替换两个槽位，生成自己的新句子。",
                "data": {
                    "template": "What stands out is not only [idea A], but also [idea B].",
                    "slots": [
                        {
                            "id": "idea-a",
                            "label": "第一个亮点",
                            "placeholder": "the idea itself",
                            "examples": ["the result", "the argument"],
                        },
                        {
                            "id": "idea-b",
                            "label": "第二个亮点",
                            "placeholder": "how clearly it is expressed",
                            "examples": ["the process behind it", "its practical value"],
                        },
                    ],
                    "example": second,
                    "preview_prefix": "迁移句：",
                },
                "ui": {"collapsible": False, "emphasis": "primary"},
            },
        ]
    if input_type == "learning_target":
        normalized = text.casefold()
        grammar_target = any(
            marker in normalized
            for marker in ("grammar", "tense", "语法", "时态", "从句", "present perfect")
        )
        if grammar_target:
            return [
                {
                    "id": "fallback-grammar-focus",
                    "type": "grammar_focus",
                    "title": "语法目标",
                    "description": "先用最小对比确认结构，再进入练习。",
                    "data": {
                        "topic": text,
                        "rule": "先确认时间、主语和谓语形式，再把规则放回完整语境中使用。",
                        "error": "I have studied English since three years.",
                        "correction": "I have studied English for three years.",
                        "minimal_pairs": [
                            {
                                "wrong": "I have studied English since three years.",
                                "correct": "I have studied English for three years.",
                                "explanation": "for 接时间段；since 接起点。",
                            }
                        ],
                    },
                    "ui": {"collapsible": False, "emphasis": "primary"},
                }
            ]
        return [
            {
                "id": "fallback-vocabulary-focus",
                "type": "vocabulary_focus",
                "title": "词汇目标",
                "description": "从完整例句、搭配和近义词开始建立用法。",
                "data": {
                    "entries": [
                        {
                            "id": "fallback-target-word",
                            "word": text[:255],
                            "meaning": "当前学习目标；请结合生成恢复后的上下文确认精确词义。",
                            "collocations": ["use it naturally", "in context"],
                            "examples": [first],
                            "synonyms": [],
                        }
                    ]
                },
                "ui": {"collapsible": False, "emphasis": "primary"},
            }
        ]
    return []


def _fallback_save_actions(
    *,
    input_type: str,
    input_text: str,
    context: str | None,
    first: str,
    second: str,
    first_zh: str,
    second_zh: str,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if input_type in {"zh_intent", "en_draft", "good_sentence"}:
        for suffix, expression, meaning, register in (
            ("neutral", first, first_zh, "neutral"),
            ("soft", second, second_zh, "polite"),
        ):
            actions.append(
                {
                    "id": f"fallback-save-{suffix}",
                    "type": "save_writing_phrase",
                    "label": "收藏这个表达",
                    "block_id": "fallback-variants",
                    "payload": {
                        "text": expression,
                        "chinese_meaning": meaning,
                        "explanation": meaning,
                        "usage_scene": context or "通用",
                        "register": register,
                        "template": (
                            "What matters most is not [idea A], but [idea B]."
                            if input_type == "good_sentence" and suffix == "neutral"
                            else "What stands out is not only [idea A], but also [idea B]."
                            if input_type == "good_sentence"
                            else None
                        ),
                        "examples": [expression],
                        "tags": ["Expression Lab", "fallback"],
                    },
                    "requires_confirmation": True,
                    "editable_fields": [
                        "text",
                        "chinese_meaning",
                        "explanation",
                        "usage_scene",
                        "register",
                        "examples",
                        "tags",
                    ],
                }
            )

    if input_type == "en_draft" and re.search(
        r"\b(?:am|is|are)\s+agree\b", input_text, flags=re.IGNORECASE
    ):
        actions.append(
            {
                "id": "fallback-save-grammar-agree",
                "type": "save_grammar_point",
                "label": "记录这个语法知识点",
                "block_id": "fallback-grammar-focus",
                "payload": {
                    "topic": "agree 作为动词",
                    "rule": "agree 在这里是实义动词，直接说 I agree，不使用 be + agree。",
                    "error": input_text,
                    "correction": first,
                    "minimal_pairs": [
                        {
                            "wrong": "I am agree with you.",
                            "correct": "I agree with you.",
                            "explanation": "删除 am，让 agree 直接作谓语。",
                        }
                    ],
                },
                "requires_confirmation": True,
                "editable_fields": ["topic", "rule", "error", "correction", "minimal_pairs"],
            }
        )

    if input_type == "learning_target":
        normalized = input_text.casefold()
        grammar_target = any(
            marker in normalized
            for marker in ("grammar", "tense", "语法", "时态", "从句", "present perfect")
        )
        if grammar_target:
            actions.append(
                {
                    "id": "fallback-save-grammar-target",
                    "type": "save_grammar_point",
                    "label": "记录这个语法知识点",
                    "block_id": "fallback-grammar-focus",
                    "payload": {
                        "topic": input_text[:255],
                        "rule": "先确认时间、主语和谓语形式，再把规则放回完整语境中使用。",
                        "error": "I have studied English since three years.",
                        "correction": "I have studied English for three years.",
                        "minimal_pairs": [
                            {
                                "wrong": "I have studied English since three years.",
                                "correct": "I have studied English for three years.",
                                "explanation": "for 接时间段；since 接起点。",
                            }
                        ],
                    },
                    "requires_confirmation": True,
                    "editable_fields": ["topic", "rule", "error", "correction", "minimal_pairs"],
                }
            )
        else:
            actions.append(
                {
                    "id": "fallback-save-vocabulary-target",
                    "type": "save_vocabulary",
                    "label": "加入词汇本",
                    "block_id": "fallback-vocabulary-focus",
                    "payload": {
                        "word": input_text[:255],
                        "meaning": "当前学习目标；请结合语境确认精确词义。",
                        "collocations": ["use it naturally", "in context"],
                        "examples": [first],
                        "source_expression": first,
                        "reason": "Expression Lab 学习目标",
                    },
                    "requires_confirmation": True,
                    "editable_fields": [
                        "word",
                        "meaning",
                        "collocations",
                        "examples",
                        "source_expression",
                        "reason",
                    ],
                }
            )
    return actions


def _repair_common_english_draft(text: str) -> str:
    repaired = re.sub(r"\bI\s+am\s+agree\b", "I agree", text, flags=re.IGNORECASE)
    repaired = re.sub(r"\b(we|they|you)\s+are\s+agree\b", r"\1 agree", repaired, flags=re.I)
    repaired = re.sub(r"\b(he|she|it)\s+is\s+agree\b", r"\1 agrees", repaired, flags=re.I)
    repaired = re.sub(r"\bdiscuss\s+about\b", "discuss", repaired, flags=re.IGNORECASE)
    repaired = re.sub(r"\bmore\s+better\b", "better", repaired, flags=re.IGNORECASE)
    return repaired.strip() or text


def _draft_repair_explanation(original: str, corrected: str) -> str:
    if re.search(r"\b(?:am|is|are)\s+agree\b", original, flags=re.IGNORECASE):
        return "agree 在这里是动词，直接说 I agree，不使用 be + agree。"
    if re.search(r"\bdiscuss\s+about\b", original, flags=re.IGNORECASE):
        return "discuss 是及物动词，后面直接接讨论对象，不再加 about。"
    if original != corrected:
        return "修复了可确定的常见结构问题，同时保留原意。"
    return "未擅自改写无法确定的内容；请比较替代表达并按真实语境确认。"


def _learning_target_example(text: str) -> str:
    examples = {
        "resilient": "She remained resilient even after several setbacks.",
        "nuance": "This translation misses an important nuance in the original sentence.",
        "perspective": "The discussion helped me see the issue from a different perspective.",
        "present perfect": "I have studied English for three years.",
    }
    return examples.get(text.casefold().strip(), f'I am learning how to use “{text}” in context.')


def _fallback_target_expression(first: str, second: str, input_type: str) -> str:
    if input_type == "en_draft" and "agree" in first.casefold():
        return "agree"
    if input_type == "good_sentence":
        return "not only"
    if input_type == "learning_target":
        return "in context"
    words = second.strip().split()
    return " ".join(words[: min(5, len(words))]).strip(".,")


def build_text_fallback(
    *,
    session_id: str | uuid.UUID,
    input_text: str,
    input_type: str = "zh_intent",
    context: str | None = None,
    style_goal: str | None = None,
    source_type: str = "manual",
    source_ref: str | None = None,
) -> dict[str, Any]:
    payload = build_fixed_fallback(
        session_id=session_id,
        input_text=input_text,
        input_type=input_type,
        context=context,
        style_goal=style_goal,
        source_type=source_type,
        source_ref=source_ref,
    )
    payload["blocks"] = payload["blocks"][:1]
    payload["fallback_message"] = (
        "这次没有生成完整互动模块。页面已隐藏模型原始内容，并提供安全的文本表达框架；"
        "你可以稍后重试生成。"
    )
    return ExpressionUiSpec.model_validate(payload).model_dump(mode="json", by_alias=True)


def _valid_session_id(value: Any) -> str | None:
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError):
        return None


def _plain_text(value: str) -> str:
    return re.sub(r"[<>]", "", str(value)).strip()


def _summarize_validation_error(exc: ValidationError) -> str:
    first = exc.errors(include_url=False)[0]
    location = ".".join(str(part) for part in first.get("loc", ())) or "$"
    return f"{location}: {first.get('msg', 'invalid')}"[:400]


def canonical_fixture_json() -> str:
    """Useful for prompt/eval tooling without duplicating private fallback logic."""

    return json.dumps(
        build_fixed_fallback(
            session_id="00000000-0000-0000-0000-000000000001",
            input_text="这个观点太绝对了",
            context="group_chat",
            style_goal="polite",
        ),
        ensure_ascii=False,
    )
