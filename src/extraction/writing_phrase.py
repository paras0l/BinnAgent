import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WritingPhraseExtractionCandidate:
    text: str
    chinese_meaning: str | None = None
    usage_scene: str | None = None
    usage_position: str | None = None
    tags: list[str] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    usage_notes: list[str] = field(default_factory=list)
    mistakes: list[str] = field(default_factory=list)
    quality_score: float = 0.7
    warnings: list[str] = field(default_factory=list)
    parse_mode: str = "regex_fallback"
    confidence: float = 0.7


@dataclass(frozen=True)
class WritingPhraseExtractionResult:
    candidates: list[WritingPhraseExtractionCandidate]
    parse_mode: str
    warnings: list[str] = field(default_factory=list)
    repair_used: bool = False
    confidence: float = 0.7


def extract_writing_phrase_candidates(raw_text: str, topic: str | None = None) -> WritingPhraseExtractionResult:
    json_payload, repair_used = _extract_json_object(raw_text)
    if isinstance(json_payload, dict):
        candidates = _candidates_from_json(json_payload, topic)
        if candidates:
            confidence = min(candidate.confidence for candidate in candidates)
            return WritingPhraseExtractionResult(
                candidates=candidates[:20],
                parse_mode="json_schema",
                repair_used=repair_used,
                confidence=confidence,
            )
    fallback = _parse_regex_candidates(raw_text, topic)
    warnings = ["未识别到合法 JSON，已使用正则 fallback；请人工确认字段。"]
    return WritingPhraseExtractionResult(
        candidates=fallback[:20],
        parse_mode="regex_fallback",
        warnings=warnings,
        confidence=0.55 if fallback else 0,
    )


def _extract_json_object(raw_text: str) -> tuple[dict[str, Any] | None, bool]:
    text = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S | re.I)
    if fenced:
        text = fenced.group(1)
    for candidate, repaired in ((text, False), (_slice_json_object(text), True)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed, repaired
    return None, False


def _slice_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    return text[start : end + 1]


def _candidates_from_json(payload: dict[str, Any], topic: str | None) -> list[WritingPhraseExtractionCandidate]:
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        return []
    candidates: list[WritingPhraseExtractionCandidate] = []
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            continue
        text = _clean_required(raw.get("text"))
        if text is None:
            continue
        warnings = _clean_list(raw.get("warnings"))
        examples = _clean_examples(raw.get("examples"))
        quality_score = _clamp_score(raw.get("quality_score"), default=0.8)
        if not examples:
            warnings.append("缺少例句，保存前建议补充。")
            quality_score = min(quality_score, 0.68)
        tags = _clean_list(raw.get("tags"))
        if topic and topic not in tags:
            tags.append(topic)
        candidates.append(
            WritingPhraseExtractionCandidate(
                text=text,
                chinese_meaning=_clean_optional(raw.get("chinese_meaning")),
                usage_scene=_clean_optional(raw.get("usage_scene")),
                usage_position=_normalize_usage_position(raw.get("usage_position")),
                tags=tags[:8],
                examples=examples,
                usage_notes=_clean_list(raw.get("usage_notes") or raw.get("notes")),
                mistakes=_clean_list(raw.get("mistakes")),
                quality_score=quality_score,
                warnings=warnings,
                parse_mode="json_schema",
                confidence=quality_score,
            )
        )
    return candidates


def _field(block: str, names: tuple[str, ...]) -> str | None:
    joined = "|".join(re.escape(name) for name in names)
    prefix = r"(?:[-*]\s*|\d+[.)、]\s*)?"
    pattern = rf"(?:^|\n)\s*{prefix}(?:{joined})\s*[:：]\s*(.+?)(?=\n\s*{prefix}(?:[\u4e00-\u9fa5A-Za-z ]{{2,24}})\s*[:：]|\Z)"
    match = re.search(pattern, block, flags=re.S)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip(" -*\n")


def _split_import_blocks(raw_text: str) -> list[str]:
    normalized = raw_text.replace("\r\n", "\n").strip()
    blocks = re.split(r"\n(?=\s*(?:\d+[.)、]|[-*]\s*(?:英文句式|原句|句式|表达)))", normalized)
    if len(blocks) <= 1:
        blocks = re.split(r"\n{2,}", normalized)
    return [block.strip() for block in blocks if block.strip()]


def _parse_regex_candidates(raw_text: str, topic: str | None) -> list[WritingPhraseExtractionCandidate]:
    candidates: list[WritingPhraseExtractionCandidate] = []
    for block in _split_import_blocks(raw_text):
        text = _field(block, ("英文句式", "句式", "原句", "表达", "可替换模板", "Useful expression", "Template"))
        if not text:
            first_line = block.splitlines()[0].strip(" -*")
            if re.search(r"[A-Za-z]{3,}", first_line):
                text = first_line
        if not text or len(text) < 6:
            continue
        example = _field(block, ("例句", "CET 写作例句", "一个新的 CET 写作例句", "Example"))
        examples = [{"sentence": example}] if example else []
        warnings = ["使用正则 fallback 提取，请人工确认。"]
        if not examples:
            warnings.append("缺少例句。")
        if "不建议收藏" in block or "不推荐" in block:
            warnings.append("外部模型标注为不建议收藏，请谨慎保存。")
        candidates.append(
            WritingPhraseExtractionCandidate(
                text=text,
                chinese_meaning=_field(block, ("中文含义", "含义", "Meaning")),
                usage_scene=_field(block, ("适用场景", "使用场景", "When to use")),
                usage_position=_normalize_usage_position(
                    _field(block, ("适合放在开头/主体/结尾哪个位置", "适用位置", "使用位置"))
                ),
                tags=_infer_tags(block, topic),
                examples=examples,
                usage_notes=_clean_list([_field(block, ("使用注意事项", "注意事项", "Usage notes"))]),
                mistakes=_clean_list([_field(block, ("常见错误", "常见误用", "Common misuse"))]),
                quality_score=0.72 if examples else 0.6,
                warnings=warnings,
                parse_mode="regex_fallback",
                confidence=0.55,
            )
        )
    return candidates


def _infer_tags(block: str, topic: str | None) -> list[str]:
    tags: list[str] = []
    tag_text = _field(block, ("标签", "句式功能", "功能"))
    if tag_text:
        tags.extend(re.split(r"[/,，、\s]+", tag_text))
    if topic:
        tags.append(topic)
    return _clean_list(tags)[:6]


def _clean_required(value: Any) -> str | None:
    text = _clean_optional(value)
    return text if text and len(text) >= 3 else None


def _clean_optional(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", value.strip())
    return text or None


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    cleaned: list[str] = []
    for item in values:
        text = _clean_optional(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _clean_examples(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    examples: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            sentence = _clean_required(item)
            if sentence:
                examples.append({"sentence": sentence})
            continue
        if not isinstance(item, dict):
            continue
        sentence = _clean_required(item.get("sentence"))
        if not sentence:
            continue
        example = {"sentence": sentence}
        translation = _clean_optional(item.get("translation") or item.get("translation_zh"))
        if translation:
            example["translation"] = translation
        examples.append(example)
    return examples[:3]


def _normalize_usage_position(value: Any) -> str | None:
    text = _clean_optional(value)
    if not text:
        return None
    lower = text.casefold()
    if "开头" in text or "opening" in lower:
        return "opening"
    if "结尾" in text or "closing" in lower:
        return "closing"
    if "翻译" in text or "translation" in lower:
        return "translation"
    if "主体" in text or "body" in lower:
        return "body"
    return text[:40]


def _clamp_score(value: Any, *, default: float) -> float:
    if not isinstance(value, int | float):
        return default
    return max(0.0, min(float(value), 1.0))
