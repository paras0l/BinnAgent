import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.memory.vocabulary_rules import normalize_vocabulary_word
from src.memory.vocabulary_store import VocabularyStore
from src.providers.base import ChatRequest as ModelChatRequest
from src.providers.router import ModelRouter

logger = logging.getLogger(__name__)

VOCABULARY_AGENT_NAME = "vocabulary_agent"
VOCABULARY_CONFIDENCE_THRESHOLD = 0.75

VOCABULARY_CARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "phonetic": {"type": "string"},
                    "definition_zh": {"type": "string"},
                    "definition_en": {"type": "string"},
                    "collocations": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "phrase": {"type": "string"},
                                "translation_zh": {"type": "string"},
                            },
                            "required": ["phrase", "translation_zh"],
                        },
                    },
                    "examples": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "sentence": {"type": "string"},
                                "translation_zh": {"type": "string"},
                            },
                            "required": ["sentence", "translation_zh"],
                        },
                    },
                    "memory_tip": {"type": "string"},
                    "exam_level": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": [
                    "word",
                    "phonetic",
                    "definition_zh",
                    "definition_en",
                    "examples",
                    "confidence",
                ],
            },
        }
    },
    "required": ["cards"],
}

VOCABULARY_AGENT_SYSTEM_PROMPT = """你是 BinnAgent 的 Vocabulary Agent，专门负责从英语学习对话中提取高质量词卡。

硬性规则：
- 只提取真实英文单词，不提取中文、短语、句子、寒暄、报错、说明标签或 markdown 标题。
- 优先提取用户明确给出的词、assistant 明确讲解的 CET-4/CET-6 高频词。
- 不确定就少提取，不要编造。
- 每个词必须有音标 phonetic、中文释义 definition_zh、英文释义 definition_en、至少 1 个英文例句和中文翻译。
- phonetic 优先使用 IPA 格式，例如 /sɪɡˈnɪfɪkənt/；不知道音标时不要返回该词。
- confidence 表示“值得自动沉淀且字段可靠”的置信度，低于 0.75 的词也可以返回，但系统不会入库。
- 严格输出符合 JSON schema 的 JSON，不要输出 markdown。"""


@dataclass(frozen=True)
class VocabularyAgentResult:
    saved_count: int = 0
    skipped_count: int = 0
    failed: bool = False


class VocabularyAgentService:
    def __init__(self, db: AsyncSession, model_router: ModelRouter):
        self.db = db
        self.model_router = model_router

    async def capture_chat_turn(
        self,
        *,
        learner_id: uuid.UUID,
        user_message: str,
        assistant_reply: str,
        source_ref: str | None,
    ) -> VocabularyAgentResult:
        try:
            structured = await self._extract_cards(
                user_message=user_message,
                assistant_reply=assistant_reply,
            )
        except (httpx.HTTPError, ValueError, TypeError):
            logger.exception("Vocabulary agent extraction failed")
            return VocabularyAgentResult(failed=True)

        cards = structured.get("cards") if isinstance(structured, dict) else None
        if not isinstance(cards, list):
            return VocabularyAgentResult(skipped_count=1)

        saved_count = 0
        skipped_count = 0
        store = VocabularyStore(self.db)
        for raw_card in cards:
            if not isinstance(raw_card, dict):
                skipped_count += 1
                continue
            card = _normalize_card(raw_card)
            if card is None:
                skipped_count += 1
                continue
            await store.add_word(
                learner_id=learner_id,
                word=card["word"],
                phonetic=card.get("phonetic"),
                level=card.get("exam_level"),
                meanings=[
                    {
                        "definition_zh": card["definition_zh"],
                        "definition_en": card["definition_en"],
                        "source": VOCABULARY_AGENT_NAME,
                    }
                ],
                collocations=card.get("collocations", []),
                examples=card["examples"],
                source_ref=source_ref,
                commit=False,
            )
            saved_count += 1

        await self.db.flush()
        return VocabularyAgentResult(saved_count=saved_count, skipped_count=skipped_count)

    async def _extract_cards(self, *, user_message: str, assistant_reply: str) -> dict[str, Any]:
        response = await self.model_router.chat(
            ModelChatRequest(
                messages=[
                    {"role": "system", "content": VOCABULARY_AGENT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "请从下面这轮英语学习对话中提取可沉淀词卡。\n\n"
                            f"用户材料：\n{user_message}\n\n"
                            f"assistant 讲解：\n{assistant_reply}"
                        ),
                    },
                ],
                task_type="vocabulary_agent_extract",
                temperature=0.1,
                max_tokens=1200,
                response_schema=VOCABULARY_CARD_SCHEMA,
                preferred_model=settings.ollama_utility_model,
            )
        )
        if response.structured is not None:
            return response.structured
        parsed = json.loads(response.content)
        if not isinstance(parsed, dict):
            raise ValueError("Vocabulary agent response must be an object")
        return parsed


def should_trigger_vocabulary_agent(*, user_message: str, skill_focus: str | None) -> bool:
    if isinstance(skill_focus, str) and skill_focus.strip().lower() == "vocabulary":
        return True
    lower = user_message.lower()
    return any(
        marker in lower
        for marker in (
            "ai 词汇讲解沉淀",
            "cet 词汇教练",
            "提炼值得记忆的重点词",
            "加入词汇本",
        )
    )


def _normalize_card(card: dict[str, Any]) -> dict[str, Any] | None:
    word_value = card.get("word")
    if not isinstance(word_value, str):
        return None
    word = normalize_vocabulary_word(word_value)
    if word is None:
        return None

    definition_zh = _clean_required_text(card.get("definition_zh"))
    definition_en = _clean_required_text(card.get("definition_en"))
    phonetic = _clean_required_text(card.get("phonetic"))
    examples = _normalize_examples(card.get("examples"))
    confidence = card.get("confidence")
    if not isinstance(confidence, int | float):
        return None
    if confidence < VOCABULARY_CONFIDENCE_THRESHOLD:
        return None
    if phonetic is None or definition_zh is None or definition_en is None or not examples:
        return None

    normalized: dict[str, Any] = {
        "word": word,
        "phonetic": phonetic,
        "definition_zh": definition_zh,
        "definition_en": definition_en,
        "examples": examples,
        "confidence": float(confidence),
    }
    exam_level = _clean_optional_text(card.get("exam_level"))
    if exam_level:
        normalized["exam_level"] = exam_level[:20]
    memory_tip = _clean_optional_text(card.get("memory_tip"))
    if memory_tip:
        normalized["memory_tip"] = memory_tip
    collocations = _normalize_collocations(card.get("collocations"))
    if collocations:
        normalized["collocations"] = collocations
    return normalized


def _clean_required_text(value: Any) -> str | None:
    text = _clean_optional_text(value)
    if text is None or len(text) < 2:
        return None
    return text


def _clean_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().split())
    return text or None


def _normalize_examples(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    examples: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        sentence = _clean_required_text(item.get("sentence"))
        translation = _clean_required_text(item.get("translation_zh"))
        if sentence and translation and normalize_vocabulary_word(sentence) is None:
            examples.append({"sentence": sentence, "translation_zh": translation})
        if len(examples) >= 3:
            break
    return examples


def _normalize_collocations(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    collocations: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        phrase = _clean_required_text(item.get("phrase"))
        translation = _clean_required_text(item.get("translation_zh"))
        if phrase and translation:
            collocations.append({"phrase": phrase, "translation_zh": translation})
        if len(collocations) >= 3:
            break
    return collocations
