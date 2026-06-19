import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.vocabulary_rules import normalize_vocabulary_word
from src.models.vocabulary import ReviewSchedule, VocabularyItem


class VocabularyStore:
    def __init__(self, db: AsyncSession):
        self.db = db

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
            if meanings and not existing.meanings:
                existing.meanings = meanings
                changed = True
            if collocations and not existing.collocations:
                existing.collocations = collocations
                changed = True
            if examples and not existing.examples:
                existing.examples = examples
                changed = True
            if source_ref and not existing.source_ref:
                existing.source_ref = source_ref
                changed = True
            if phonetic and not existing.phonetic:
                existing.phonetic = phonetic
                changed = True
            if level and not existing.level:
                existing.level = level
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
            entry_kind="word",
            preferred_accent="auto",
            phonetic=phonetic,
            level=level,
            meanings=meanings or [],
            collocations=collocations or [],
            examples=examples or [],
            source_ref=source_ref,
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
