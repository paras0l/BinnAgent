import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.base_dictionary.enrichment import vocabulary_enrichment
from src.base_dictionary.service import get_entry as get_base_dictionary_entry
from src.memory.vocabulary_rules import normalize_vocabulary_word
from src.models.vocabulary import ReviewSchedule, VocabularyItem

BaseDictionaryLookup = Callable[[AsyncSession, str], Awaitable[dict[str, Any] | None]]


class VocabularyStore:
    def __init__(
        self,
        db: AsyncSession,
        *,
        base_dictionary_lookup: BaseDictionaryLookup = get_base_dictionary_entry,
    ):
        self.db = db
        self.base_dictionary_lookup = base_dictionary_lookup

    async def add_word(
        self,
        learner_id: uuid.UUID,
        word: str,
        phonetic: str | None = None,
        level: str | None = None,
        meanings: list | None = None,
        collocations: list | None = None,
        examples: list | None = None,
        source_ref: str | None = None,
        commit: bool = True,
    ) -> VocabularyItem:
        normalized_word = normalize_vocabulary_word(word)
        if normalized_word is None:
            raise ValueError("Invalid vocabulary word")

        shared = vocabulary_enrichment(
            await self.base_dictionary_lookup(self.db, normalized_word)
        )

        # Check if word already exists for this learner (no duplicates)
        result = await self.db.execute(
            select(VocabularyItem).where(
                VocabularyItem.learner_id == learner_id,
                func.lower(VocabularyItem.word) == normalized_word,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            changed = False
            if not existing.meanings and (shared.get("meanings") or meanings):
                existing.meanings = shared.get("meanings") or meanings
                changed = True
            if not existing.collocations and (shared.get("collocations") or collocations):
                existing.collocations = shared.get("collocations") or collocations
                changed = True
            if not existing.examples and (shared.get("examples") or examples):
                existing.examples = shared.get("examples") or examples
                changed = True
            if source_ref and not existing.source_ref:
                existing.source_ref = source_ref
                changed = True
            if not existing.phonetic and (shared.get("phonetic") or phonetic):
                existing.phonetic = shared.get("phonetic") or phonetic
                changed = True
            if level and not existing.level:
                existing.level = level
                changed = True
            for field_name in ("dictionary_senses", "word_forms", "dictionary_tags"):
                if not getattr(existing, field_name, None) and shared.get(field_name):
                    setattr(existing, field_name, shared[field_name])
                    changed = True
            if shared and existing.dictionary_provider != "base_dictionary":
                existing.dictionary_provider = "base_dictionary"
                existing.dictionary_enriched_at = datetime.now(timezone.utc)
                changed = True
            if changed and commit:
                await self.db.commit()
                await self.db.refresh(existing)
            elif changed:
                await self.db.flush()
            return existing

        item = VocabularyItem(
            learner_id=learner_id,
            word=normalized_word,
            canonical_key=normalized_word,
            entry_kind=shared.get("entry_kind", "word"),
            preferred_accent="auto",
            phonetic=phonetic or shared.get("phonetic"),
            level=level,
            meanings=meanings or shared.get("meanings") or [],
            dictionary_senses=shared.get("dictionary_senses") or [],
            word_forms=shared.get("word_forms") or {},
            dictionary_tags=shared.get("dictionary_tags") or [],
            collocations=collocations or shared.get("collocations") or [],
            examples=examples or shared.get("examples") or [],
            source_ref=source_ref,
            dictionary_provider=shared.get("dictionary_provider"),
            dictionary_enriched_at=(datetime.now(timezone.utc) if shared else None),
            status="learning",
            confidence=0.0,
            review_count=0,
            next_review_at=datetime.now(timezone.utc),
        )
        self.db.add(item)
        if commit:
            await self.db.commit()
            await self.db.refresh(item)
        else:
            await self.db.flush()
        return item

    async def get_word(self, learner_id: uuid.UUID, word: str) -> VocabularyItem | None:
        normalized_word = normalize_vocabulary_word(word)
        if normalized_word is None:
            return None
        result = await self.db.execute(
            select(VocabularyItem).where(
                VocabularyItem.learner_id == learner_id,
                func.lower(VocabularyItem.word) == normalized_word,
            )
        )
        return result.scalar_one_or_none()

    async def get_due_reviews(self, learner_id: uuid.UUID, limit: int = 20) -> list[VocabularyItem]:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(VocabularyItem)
            .where(
                VocabularyItem.learner_id == learner_id,
                VocabularyItem.next_review_at <= now,
                VocabularyItem.status != "mastered",
            )
            .order_by(VocabularyItem.next_review_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_confidence(
        self, learner_id: uuid.UUID, item_id: uuid.UUID, correct: bool, response_time_ms: int | None
    ) -> VocabularyItem:
        result = await self.db.execute(
            select(VocabularyItem).where(
                VocabularyItem.id == item_id,
                VocabularyItem.learner_id == learner_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError(f"VocabularyItem with id {item_id} not found")

        now = datetime.now(timezone.utc)
        confidence_before = item.confidence
        previous_next_review = item.next_review_at or now
        item.review_count += 1
        item.last_reviewed_at = now

        sm2_intervals = [1, 2, 4, 7, 15, 30]

        if correct:
            item.confidence = min(1.0, item.confidence + 0.1)
            if item.confidence >= 0.9:
                item.status = "mastered"
            interval_idx = min(item.review_count - 1, len(sm2_intervals) - 1)
            item.next_review_at = now + timedelta(days=sm2_intervals[interval_idx])
        else:
            item.confidence = max(0.0, item.confidence - 0.15)
            item.status = "learning"
            item.next_review_at = now + timedelta(days=1)

        review = ReviewSchedule(
            learner_id=learner_id,
            item_type="vocabulary",
            item_id=item.id,
            scheduled_at=previous_next_review,
            completed_at=now,
            result="correct" if correct else "incorrect",
            response_time_ms=response_time_ms,
            confidence_before=confidence_before,
            confidence_after=item.confidence,
            recommended_next_drill="word_review",
        )
        self.db.add(review)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def delete_word(self, learner_id: uuid.UUID, item_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(VocabularyItem).where(
                VocabularyItem.id == item_id,
                VocabularyItem.learner_id == learner_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError(f"VocabularyItem with id {item_id} not found")

        await self.db.execute(
            delete(ReviewSchedule).where(
                ReviewSchedule.learner_id == learner_id,
                ReviewSchedule.item_type == "vocabulary",
                ReviewSchedule.item_id == item_id,
            )
        )
        await self.db.delete(item)
        await self.db.commit()
