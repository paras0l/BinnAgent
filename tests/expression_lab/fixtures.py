import uuid
from typing import Any


def expression_ui_payload(
    *,
    session_id: str | None = None,
    input_type: str = "zh_intent",
    text: str = "这个观点太绝对了",
    include_all_blocks: bool = True,
) -> dict[str, Any]:
    session_id = session_id or str(uuid.uuid4())
    blocks: list[dict[str, Any]] = [
        {
            "id": "variants-1",
            "type": "expression_variants",
            "title": "更自然的表达",
            "data": {
                "variants": [
                    {
                        "id": "variant-polite",
                        "text": "That claim may be a little too absolute.",
                        "chinese_explanation": "委婉指出这个说法可能过于绝对。",
                        "context": "群聊讨论",
                        "tone_tags": ["委婉", "自然"],
                        "naturalness": 94,
                        "difficulty": 2,
                        "action_id": "save-phrase-1",
                    },
                    {
                        "id": "variant-formal",
                        "text": "That position seems overly categorical.",
                        "chinese_explanation": "较正式地指出立场缺少余地。",
                        "context": "考试写作",
                        "tone_tags": ["正式"],
                        "naturalness": 87,
                        "difficulty": 4,
                    },
                ]
            },
        },
        {
            "id": "practice-1",
            "type": "micro_practice",
            "title": "马上练一次",
            "data": {
                "instructions": "把直接判断改写得更委婉。",
                "questions": [
                    {
                        "id": "question-1",
                        "type": "translation",
                        "prompt": "翻译：这个结论可能有些绝对。",
                        "answer": "This conclusion may be a little too absolute.",
                        "accepted_answers": [
                            "This conclusion may be a bit too absolute."
                        ],
                        "target_expression": "may be a little too absolute",
                        "explanation": "may 和 a little 可以降低语气强度。",
                        "skill": "writing",
                    }
                ],
            },
        },
    ]
    if include_all_blocks:
        blocks[1:1] = [
            {
                "id": "tone-1",
                "type": "tone_spectrum",
                "title": "语气强度",
                "data": {
                    "dimension": "directness",
                    "left_label": "委婉",
                    "right_label": "直接",
                    "points": [
                        {
                            "id": "tone-soft",
                            "label": "委婉",
                            "expression": "That claim may be a little too absolute.",
                            "position": 20,
                            "explanation": "适合讨论。",
                        },
                        {
                            "id": "tone-direct",
                            "label": "直接",
                            "expression": "That claim is too absolute.",
                            "position": 85,
                            "explanation": "关系熟悉时使用。",
                        },
                    ],
                },
            },
            {
                "id": "diff-1",
                "type": "sentence_diff",
                "title": "原句修复",
                "data": {
                    "original": "I am agree with you.",
                    "corrected": "I agree with you.",
                    "changes": [
                        {
                            "operation": "delete",
                            "original": "am",
                            "replacement": "",
                            "explanation": "agree 是动词，前面不需要 be。",
                        }
                    ],
                    "summary": "删除多余的 be 动词。",
                },
            },
            {
                "id": "pattern-1",
                "type": "pattern_diagram",
                "title": "句型结构",
                "data": {
                    "pattern": "What matters most is not [A], but [B].",
                    "nodes": [
                        {"id": "fixed", "label": "What matters most is not", "kind": "fixed"},
                        {"id": "slot-a", "label": "A", "kind": "slot"},
                        {"id": "connector", "label": "but", "kind": "connector"},
                        {"id": "slot-b", "label": "B", "kind": "slot"},
                    ],
                    "edges": [
                        {"source": "fixed", "target": "slot-a"},
                        {"source": "slot-a", "target": "connector"},
                        {"source": "connector", "target": "slot-b"},
                    ],
                    "example": "What matters most is not speed, but consistency.",
                },
            },
            {
                "id": "usage-1",
                "type": "usage_comparison",
                "title": "近义表达对比",
                "data": {
                    "items": [
                        {
                            "id": "absolute",
                            "expression": "too absolute",
                            "meaning": "过于绝对",
                            "register": "中性",
                            "context": "日常讨论",
                            "common_collocations": ["claim", "view"],
                            "avoid_when": "需要非常正式的论文语气时。",
                        },
                        {
                            "id": "categorical",
                            "expression": "overly categorical",
                            "meaning": "过于武断、绝对",
                            "register": "正式",
                            "context": "正式写作",
                            "common_collocations": ["statement", "position"],
                            "avoid_when": "轻松口语场景。",
                        },
                    ]
                },
            },
            {
                "id": "vocabulary-1",
                "type": "vocabulary_focus",
                "title": "关键词",
                "data": {
                    "entries": [
                        {
                            "id": "vocab-absolute",
                            "word": "absolute",
                            "meaning": "绝对的；不留余地的",
                            "collocations": ["absolute certainty", "absolute claim"],
                            "examples": ["The claim sounds too absolute."],
                            "synonyms": ["categorical"],
                            "action_id": "save-vocabulary-1",
                        }
                    ]
                },
            },
            {
                "id": "grammar-1",
                "type": "grammar_focus",
                "title": "语法焦点",
                "data": {
                    "topic": "agree 不与 be 连用",
                    "rule": "agree 本身是实义动词，直接随主语变形。",
                    "error": "I am agree with you.",
                    "correction": "I agree with you.",
                    "minimal_pairs": [
                        {
                            "wrong": "She is agrees.",
                            "correct": "She agrees.",
                            "explanation": "第三人称单数直接使用 agrees。",
                        }
                    ],
                    "action_id": "save-grammar-1",
                },
            },
            {
                "id": "transfer-1",
                "type": "transfer_builder",
                "title": "迁移造句",
                "data": {
                    "template": "What matters most is not [A], but [B].",
                    "slots": [
                        {"id": "A", "label": "不重要的表面因素", "examples": ["speed"]},
                        {"id": "B", "label": "真正重要的因素", "examples": ["consistency"]},
                    ],
                    "example": "What matters most is not talent, but deliberate practice.",
                    "preview_prefix": "你的句子：",
                },
            },
            {
                "id": "sandbox-1",
                "type": "sandbox_widget",
                "title": "互动语气轴",
                "data": {
                    "html": "<main><button id='soft'>委婉</button></main>",
                    "css": "main { display: grid; gap: 8px; }",
                    "javascript": "document.querySelector('#soft')?.addEventListener('click',()=>binnagent.emit('interaction',{value:'soft'}));",
                    "allowed_events": ["interaction"],
                    "height": 240,
                    "timeout_ms": 5000,
                },
            },
        ]

    return {
        "version": "expression_ui.v1",
        "session_id": session_id,
        "source": {"type": "manual", "source_id": None},
        "intent": {
            "input_type": input_type,
            "text": text,
            "context": "group_chat",
            "goal": "polite_disagreement",
        },
        "layout": "tone_spectrum",
        "blocks": blocks,
        "suggested_assets": [
            {
                "type": "writing_phrase",
                "label": "收藏委婉表达",
                "action_id": "save-phrase-1",
                "reason": "适合讨论时表达不同意见。",
            }
        ],
        "learning_actions": [
            {
                "id": "save-phrase-1",
                "type": "save_writing_phrase",
                "label": "收藏这个表达",
                "block_id": "variants-1",
                "requires_confirmation": True,
                "editable_fields": ["text", "chinese_meaning"],
                "payload": {
                    "text": "That claim may be a little too absolute.",
                    "chinese_meaning": "这个说法可能有些过于绝对。",
                    "usage_scene": "群聊讨论",
                    "register": "polite",
                    "tags": ["委婉反驳"],
                },
            },
            {
                "id": "save-vocabulary-1",
                "type": "save_vocabulary",
                "label": "加入词汇本",
                "block_id": "vocabulary-1",
                "requires_confirmation": True,
                "editable_fields": ["meaning"],
                "payload": {
                    "word": "absolute",
                    "meaning": "绝对的；不留余地的",
                    "source_expression": "That claim may be a little too absolute.",
                },
            },
            {
                "id": "save-grammar-1",
                "type": "save_grammar_point",
                "label": "记录语法点",
                "block_id": "grammar-1",
                "requires_confirmation": True,
                "editable_fields": ["rule"],
                "payload": {
                    "topic": "agree 不与 be 连用",
                    "rule": "agree 本身是实义动词。",
                    "error": "I am agree with you.",
                    "correction": "I agree with you.",
                },
            },
            {
                "id": "create-practice-1",
                "type": "create_practice",
                "label": "再生成两题",
                "block_id": "practice-1",
                "payload": {"count": 2, "focus": "委婉表达"},
            },
            {
                "id": "copy-1",
                "type": "copy_expression",
                "label": "复制表达",
                "block_id": "variants-1",
                "payload": {"text": "That claim may be a little too absolute."},
            },
            {
                "id": "dismiss-1",
                "type": "dismiss_suggestion",
                "label": "不适合我",
                "payload": {"reason": "语气仍然太正式"},
            },
            {
                "id": "complete-1",
                "type": "mark_completed",
                "label": "完成本次学习",
                "payload": {"note": "已理解委婉程度差异"},
            },
        ],
    }

