from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from src.config import settings
from src.providers.base import ChatRequest
from src.providers.router import router

logger = logging.getLogger(__name__)


DETAIL_HTML_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "phonetic": {"type": ["string", "null"]},
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
        "examples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "en": {"type": "string"},
                    "zh": {"type": "string"},
                },
                "required": ["en", "zh"],
            },
        },
        "collocations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["phonetic", "meanings", "dictionary_senses", "examples", "collocations"],
}


@dataclass(frozen=True)
class DetailHtmlExtraction:
    phonetic: str | None = None
    meanings: list[dict[str, str]] = field(default_factory=list)
    dictionary_senses: list[dict[str, Any]] = field(default_factory=list)
    examples: list[dict[str, str]] = field(default_factory=list)
    collocations: list[str] = field(default_factory=list)
    provider: str = "vocabulary_detail_html"


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._current: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "iframe", "object", "embed", "form"}:
            self._skip_depth += 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "blockquote", "tr", "div", "section"}:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "iframe", "object", "embed", "form"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "blockquote", "tr", "div", "section"}:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self._current.append(text)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        text = " ".join(self._current).strip()
        self._current.clear()
        if text and text not in self.blocks:
            self.blocks.append(text)


def html_to_text_blocks(html: str) -> list[str]:
    parser = _TextParser()
    parser.feed(html)
    parser.close()
    return parser.blocks


async def extract_vocabulary_detail_html(term: str, html: str) -> DetailHtmlExtraction:
    blocks = html_to_text_blocks(html)
    text = "\n".join(blocks)
    try:
        response = await router.chat(
            ChatRequest(
                messages=[
                    {
                        "role": "system",
                        "content": "你是英语词汇详解 HTML 的结构化抽取器，只输出 JSON。",
                    },
                    {"role": "user", "content": _build_prompt(term, text)},
                ],
                task_type="vocabulary_detail_html_extract",
                temperature=0.0,
                max_tokens=1000,
                response_schema=DETAIL_HTML_SCHEMA,
                preferred_model=settings.ollama_utility_model,
                local_only=True,
            )
        )
        payload = response.structured if response.structured is not None else json.loads(response.content)
        if not isinstance(payload, dict):
            raise ValueError("detail html extraction response must be an object")
        parsed = _parse_payload(term, payload)
        return DetailHtmlExtraction(
            phonetic=parsed.phonetic or _first_phonetic(text),
            meanings=parsed.meanings,
            dictionary_senses=parsed.dictionary_senses,
            examples=parsed.examples,
            collocations=parsed.collocations,
            provider=f"vocabulary_detail_html+{response.provider}:{response.model}",
        )
    except Exception as exc:
        logger.warning("Falling back to heuristic vocabulary detail HTML extraction: %s", exc)
        return fallback_extract_vocabulary_detail_html(term, blocks)


def _build_prompt(term: str, text: str) -> str:
    clipped = text[:12_000]
    return (
        f"请从下面的词汇详解 HTML 文本中抽取词库字段，目标词条是：{term}\n\n"
        "严格要求：\n"
        "1. meanings 要保留核心中文义项，definition_zh 要简洁，不要塞入整段文章。\n"
        "2. dictionary_senses 按词性分组，例如 n. / v. / phrase，每组 meanings_zh 是短义项数组。\n"
        "3. examples 只能是完整英文例句及其中文翻译；不要把标题、词源段、搭配列表、等级标记当例句。\n"
        "4. collocations 只放搭配短语，例如 pencil case / pencil in，不要包含说明文字。\n"
        "5. phonetic 只从文本中已有音标抽取，不要编造。\n"
        "6. 不确定的字段返回空数组或 null。\n\n"
        f"HTML 文本：\n{clipped}"
    )


def _parse_payload(term: str, payload: dict[str, Any]) -> DetailHtmlExtraction:
    return DetailHtmlExtraction(
        phonetic=_clean_optional_text(payload.get("phonetic")),
        meanings=_normalize_meanings(payload.get("meanings")),
        dictionary_senses=_normalize_senses(payload.get("dictionary_senses")),
        examples=_normalize_examples(term, payload.get("examples")),
        collocations=_normalize_string_list(payload.get("collocations"), max_len=80)[:10],
    )


def fallback_extract_vocabulary_detail_html(
    term: str, blocks: list[str]
) -> DetailHtmlExtraction:
    text = "\n".join(blocks)
    summary = _extract_summary(term, blocks)
    return DetailHtmlExtraction(
        phonetic=_first_phonetic(text),
        meanings=[
            {"part_of_speech": "detail", "definition": "", "definition_zh": summary}
        ]
        if summary
        else [],
        dictionary_senses=[
            {"part_of_speech": "detail", "meanings_zh": [summary]}
        ]
        if summary
        else [],
        examples=_extract_examples(term, blocks),
        collocations=_extract_collocations(blocks),
    )


def _clean_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _normalize_meanings(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        definition = str(item.get("definition") or "").strip()
        definition_zh = str(item.get("definition_zh") or "").strip()
        if not definition and not definition_zh:
            continue
        if definition_zh and not _contains_cjk(definition_zh):
            continue
        rows.append(
            {
                "part_of_speech": str(item.get("part_of_speech") or "word").strip(),
                "definition": definition,
                "definition_zh": definition_zh[:260],
            }
        )
    return rows[:6]


def _normalize_senses(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        meanings = _normalize_string_list(item.get("meanings_zh"), max_len=60)
        meanings = [meaning for meaning in meanings if _contains_cjk(meaning)]
        if meanings:
            rows.append(
                {
                    "part_of_speech": str(item.get("part_of_speech") or "word").strip(),
                    "meanings_zh": meanings[:8],
                }
            )
    return rows[:8]


def _normalize_examples(term: str, value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    lower_term = term.casefold()
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        en = str(item.get("en") or "").strip()
        zh = str(item.get("zh") or "").strip()
        if not en or not zh:
            continue
        if not _looks_like_sentence(en):
            continue
        if lower_term not in en.casefold() and len(en.split()) > 2:
            continue
        if _looks_like_non_example(en):
            continue
        row = {"en": en[:260], "zh": zh[:260]}
        if row not in rows:
            rows.append(row)
        if len(rows) >= 6:
            break
    return rows


def _looks_like_non_example(value: str) -> bool:
    lowered = value.casefold()
    if lowered.startswith(("🔹", "🔸", "▪", "•")):
        return True
    return any(marker in lowered for marker in ("词源", "搭配", "核心义项", "常见错误", "近义词"))


def _looks_like_sentence(value: str) -> bool:
    stripped = value.strip()
    if len(stripped.split()) < 3:
        return False
    return bool(re.search(r"[.!?]$", stripped)) or bool(
        re.match(r"^(can|could|would|will|i|you|he|she|we|they|the|a|an)\b", stripped, re.I)
    )


def _normalize_string_list(value: Any, *, max_len: int) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip(" -•:：")
        if 1 <= len(text) <= max_len and text not in rows:
            rows.append(text)
    return rows


def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def _first_phonetic(text: str) -> str | None:
    match = re.search(r"/[^/\n]{2,80}/", text)
    return match.group(0) if match else None


def _extract_summary(term: str, blocks: list[str]) -> str:
    keywords = ("义项", "释义", "含义", "意思", "核心")
    candidates = [
        block for block in blocks if any(keyword in block for keyword in keywords) and len(block) >= 8
    ]
    if not candidates:
        candidates = [
            block for block in blocks if term.casefold() in block.casefold() and len(block) >= 8
        ]
    summary = "；".join(candidates[:3])
    return summary[:500]


def _extract_examples(term: str, blocks: list[str]) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    lower_term = term.casefold()
    for block in blocks:
        if lower_term not in block.casefold() or _first_phonetic(block):
            continue
        if len(block) < 8 or len(block) > 420:
            continue
        en, zh = _split_example(block)
        if not en or not zh or not _looks_like_sentence(en) or _looks_like_non_example(en):
            continue
        row = {"en": en, "zh": zh}
        if row not in examples:
            examples.append(row)
        if len(examples) >= 6:
            break
    return examples


def _split_example(value: str) -> tuple[str, str]:
    cleaned = value.strip(" -•0123456789.、")
    parts = re.split(r"\s+(?:—|–|-|：|:)\s+", cleaned, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    match = re.search(r"[\u4e00-\u9fff]", cleaned)
    if match:
        return cleaned[: match.start()].strip(), cleaned[match.start() :].strip()
    return cleaned, ""


def _extract_collocations(blocks: list[str]) -> list[str]:
    values: list[str] = []
    for block in blocks:
        if not any(keyword in block for keyword in ("搭配", "collocation", "短语")):
            continue
        normalized = (
            block.replace("常用搭配", "")
            .replace("搭配", "")
            .replace("collocations", "")
            .replace("collocation", "")
        )
        for chunk in normalized.replace("；", ",").replace("，", ",").split(","):
            text = chunk.strip(" -•:：")
            if 2 <= len(text) <= 80 and text not in values:
                values.append(text)
            if len(values) >= 8:
                return values
    return values
