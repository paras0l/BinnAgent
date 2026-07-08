import logging
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.vocabulary_rules import normalize_vocabulary_word
from src.memory.vocabulary_store import VocabularyStore
from src.prompts.executor import PromptExecutionContext, PromptExecutor
from src.providers.router import ModelRouter

logger = logging.getLogger(__name__)

VOCABULARY_AGENT_NAME = "vocabulary_agent"
VOCABULARY_CONFIDENCE_THRESHOLD = 0.75


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
                learner_id=learner_id,
                user_message=user_message,
                assistant_reply=assistant_reply,
                source_ref=source_ref,
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

    async def _extract_cards(
        self,
        *,
        learner_id: uuid.UUID,
        user_message: str,
        assistant_reply: str,
        source_ref: str | None,
    ) -> dict[str, Any]:
        result = await PromptExecutor(db=self.db, model_router=self.model_router).execute(
            prompt_id="vocabulary.agent.extract",
            version="v1",
            variables={
                "user_message": user_message,
                "assistant_reply": assistant_reply,
            },
            context=PromptExecutionContext(
                learner_id=learner_id,
                source_module="agents.vocabulary_agent",
                task_id="vocabulary_agent_extract",
                target_type="vocabulary_card",
                target_id=source_ref,
            ),
        )
        if result.decision != "accepted" or result.validated_output is None:
            raise ValueError("Vocabulary agent output was not accepted")
        return result.validated_output


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
