from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.config import settings
from src.providers.base import ChatRequest
from src.providers.router import router
from src.tools.free_dictionary import FreeDictionaryEntry


@dataclass(frozen=True)
class LocalVocabularyEntry:
    meanings: list[dict[str, str]] = field(default_factory=list)
    dictionary_senses: list[dict[str, Any]] = field(default_factory=list)
    word_forms: dict[str, list[str]] = field(default_factory=dict)
    dictionary_tags: list[str] = field(default_factory=list)
    examples: list[Any] = field(default_factory=list)
    collocations: list[str] = field(default_factory=list)
    provider: str = "local_llm"


LOCAL_VOCABULARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "meanings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_of_speech": {"type": "string"},
                    "definition": {"type": "string"},
                    "definition_zh": {"type": "string"},
                },
                "required": ["part_of_speech", "definition", "definition_zh"],
            },
        },
        "dictionary_senses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_of_speech": {"type": "string"},
                    "meanings_zh": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["part_of_speech", "meanings_zh"],
            },
        },
        "word_forms": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
        "dictionary_tags": {"type": "array", "items": {"type": "string"}},
        "examples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"en": {"type": "string"}, "zh": {"type": "string"}},
                "required": ["en", "zh"],
            },
        },
        "collocations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "meanings",
        "dictionary_senses",
        "word_forms",
        "dictionary_tags",
        "examples",
        "collocations",
    ],
}


def build_vocabulary_enrichment_prompt(
    expression: str, free_dictionary_entry: FreeDictionaryEntry
) -> str:
    is_single_letter = len(expression.strip()) == 1 and expression.strip().isupper()
    free_dictionary_payload = {
        "word": free_dictionary_entry.word,
        "phonetic": free_dictionary_entry.phonetic,
        "phonetic_uk": free_dictionary_entry.phonetic_uk,
        "phonetic_us": free_dictionary_entry.phonetic_us,
        "entry_kind": "single_letter" if is_single_letter else "word_or_phrase",
        "meanings": [] if is_single_letter else free_dictionary_entry.meanings,
        "examples": [] if is_single_letter else free_dictionary_entry.examples,
    }
    return (
        "请为七年级英语教材词汇生成结构化词典字段。\n"
        "数据来源约束：发音音标和音频只来自 Free Dictionary API；"
        "你只补全语义、中文释义、例句、词形、标签和搭配。\n"
        "如果输入是人名、缩写、问候句或短语，请按教材学习场景解释，不要强行当普通单词处理。\n"
        "如果输入是单个大写英文字母，请只解释为字母本身及其读音课堂用法；"
        "忽略便士、页码等普通词典义项；例句使用 This is the letter X. "
        "这类安全课堂句，不要说 first/last 等字母顺序判断，除非该字母确实是 A/Z。\n"
        "请只输出 JSON，不要 Markdown，不要额外说明。\n\n"
        f"教材词条：{expression}\n"
        "Free Dictionary API 可参考信息：\n"
        f"{json.dumps(free_dictionary_payload, ensure_ascii=False)}\n\n"
        "字段要求：\n"
        "- meanings: 1-3 条，含 part_of_speech、definition 英文释义、definition_zh 中文释义。\n"
        "- dictionary_senses: 按词性分组的中文义项，"
        "如 {'part_of_speech':'n.','meanings_zh':['书']}。\n"
        "- word_forms: 只填真实词形，键可用 word_pl、word_third、word_ing、"
        "word_past、word_done、comparative、superlative。\n"
        "- dictionary_tags: 只填教材/考试标签，如 grade-7、starter、CET4；不知道则 []。\n"
        "- examples: 1-3 条七年级可理解英文例句，每条含 en 和 zh。\n"
        "- collocations: 常见搭配或课堂表达，不确定则 []。"
    )


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _as_word_forms(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    forms: dict[str, list[str]] = {}
    for key, raw_values in value.items():
        if not isinstance(key, str):
            continue
        values = _as_list_of_strings(raw_values)
        if values:
            forms[key] = values
    return forms


def parse_local_vocabulary_payload(payload: dict[str, Any]) -> LocalVocabularyEntry:
    return LocalVocabularyEntry(
        meanings=[
            {
                "part_of_speech": str(item.get("part_of_speech") or "word"),
                "definition": str(item.get("definition") or ""),
                "definition_zh": str(item.get("definition_zh") or ""),
            }
            for item in _as_list_of_dicts(payload.get("meanings"))
            if item.get("definition") or item.get("definition_zh")
        ],
        dictionary_senses=[
            {
                "part_of_speech": str(item.get("part_of_speech") or "word"),
                "meanings_zh": _as_list_of_strings(item.get("meanings_zh")),
            }
            for item in _as_list_of_dicts(payload.get("dictionary_senses"))
            if _as_list_of_strings(item.get("meanings_zh"))
        ],
        word_forms=_as_word_forms(payload.get("word_forms")),
        dictionary_tags=_as_list_of_strings(payload.get("dictionary_tags")),
        examples=[
            {"en": str(item.get("en") or ""), "zh": str(item.get("zh") or "")}
            for item in _as_list_of_dicts(payload.get("examples"))
            if item.get("en") or item.get("zh")
        ],
        collocations=_as_list_of_strings(payload.get("collocations")),
    )


def _sanitize_single_letter_entry(
    expression: str, entry: LocalVocabularyEntry
) -> LocalVocabularyEntry:
    letter = expression.strip()
    examples = [
        example
        for example in entry.examples
        if isinstance(example, dict)
        and "first" not in str(example.get("en", "")).casefold()
        and "last" not in str(example.get("en", "")).casefold()
    ]
    if not examples:
        examples = [{"en": f"This is the letter {letter}.", "zh": f"这是字母 {letter}。"}]
    return LocalVocabularyEntry(
        meanings=[
            {
                "part_of_speech": "letter",
                "definition": f"The English letter {letter}.",
                "definition_zh": f"英文字母 {letter}。",
            }
        ],
        dictionary_senses=[
            {"part_of_speech": "letter", "meanings_zh": [f"字母 {letter}"]}
        ],
        word_forms={},
        dictionary_tags=entry.dictionary_tags,
        examples=examples[:3],
        collocations=entry.collocations,
        provider=entry.provider,
    )


async def enrich_vocabulary_with_local_model(
    expression: str, free_dictionary_entry: FreeDictionaryEntry
) -> LocalVocabularyEntry:
    response = await router.chat(
        ChatRequest(
            messages=[
                {
                    "role": "system",
                    "content": "你是七年级英语教材词汇整理助手。严格输出符合 schema 的 JSON。",
                },
                {
                    "role": "user",
                    "content": build_vocabulary_enrichment_prompt(
                        expression, free_dictionary_entry
                    ),
                },
            ],
            task_type="vocabulary_local_enrichment",
            temperature=0.1,
            max_tokens=900,
            response_schema=LOCAL_VOCABULARY_SCHEMA,
            preferred_model=settings.ollama_utility_model,
            local_only=True,
        )
    )
    payload = response.structured
    if payload is None:
        payload = json.loads(response.content)
    if not isinstance(payload, dict):
        raise ValueError("Local vocabulary enrichment response must be a JSON object")
    entry = parse_local_vocabulary_payload(payload)
    if len(expression.strip()) == 1 and expression.strip().isupper():
        entry = _sanitize_single_letter_entry(expression, entry)
    return LocalVocabularyEntry(
        meanings=entry.meanings,
        dictionary_senses=entry.dictionary_senses,
        word_forms=entry.word_forms,
        dictionary_tags=entry.dictionary_tags,
        examples=entry.examples,
        collocations=entry.collocations,
        provider=f"{response.provider}:{response.model}",
    )
