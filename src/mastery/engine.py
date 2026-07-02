import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.mastery.types import AttemptSignal, MasteryUpdateResult
from src.models.knowledge import KnowledgePoint, LearnerKnowledgeState
from src.models.memory import WritingPhraseMastery
from src.models.vocabulary import VocabularyItem, VocabularyMasteryVector


class MasteryEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_from_attempt(self, signal: AttemptSignal) -> MasteryUpdateResult:
        if signal.target_type in {"knowledge_point", "curriculum_node"}:
            return await self._update_knowledge(signal)
        if signal.target_type in {"vocabulary_item", "vocabulary"}:
            return await self._update_vocabulary(signal)
        if signal.target_type == "writing_phrase":
            return await self._update_writing_phrase(signal)
        return _fallback_result(signal, previous_score=None, previous_confidence=None)

    async def _update_knowledge(self, signal: AttemptSignal) -> MasteryUpdateResult:
        learner_id = uuid.UUID(signal.learner_id)
        knowledge_point_id = await self._knowledge_point_id_for_signal(signal)
        if knowledge_point_id is None:
            return _fallback_result(signal, previous_score=None, previous_confidence=None)

        state_result = await self.db.execute(
            select(LearnerKnowledgeState).where(
                LearnerKnowledgeState.learner_id == learner_id,
                LearnerKnowledgeState.knowledge_point_id == knowledge_point_id,
            )
        )
        state = state_result.scalar_one_or_none()
        if state is None:
            state = LearnerKnowledgeState(
                learner_id=learner_id,
                knowledge_point_id=knowledge_point_id,
                status="learning",
                mastery_score=0.0,
                confidence=0.0,
                exposure_count=0,
                correct_count=0,
                evidence_summary={},
            )
            self.db.add(state)

        now = datetime.now(timezone.utc)
        previous_score = state.mastery_score or 0.0
        previous_confidence = state.confidence or 0.0
        new_score = _next_score(previous_score, signal)
        new_confidence = min(1.0, 0.2 + (state.exposure_count + 1) * 0.12)
        state.mastery_score = new_score
        state.confidence = new_confidence
        state.exposure_count = (state.exposure_count or 0) + 1
        state.correct_count = (state.correct_count or 0) + int(signal.correct)
        state.status = "mastered" if new_score >= 0.8 else "reviewing" if not signal.correct else "learning"
        state.last_seen_at = now
        state.next_review_at = _next_review_at(now, signal.correct, new_score)
        state.evidence_summary = {
            "last_result": "correct" if signal.correct else "incorrect",
            "score": signal.score,
            "error_type": signal.error_type,
            "response_time_ms": signal.response_time_ms,
            "hint_count": signal.hint_count,
            "retry_count": signal.retry_count,
            "source": signal.source,
            "evidence_refs": [ref.model_dump(mode="json") for ref in signal.evidence_refs],
            **signal.metadata,
        }
        await self.db.flush()
        return _result(
            signal,
            target_id=str(knowledge_point_id),
            previous_score=previous_score,
            new_score=new_score,
            previous_confidence=previous_confidence,
            new_confidence=new_confidence,
            next_review_at=state.next_review_at,
            status=state.status,
            metadata={"state_id": str(state.id)},
        )

    async def _knowledge_point_id_for_signal(self, signal: AttemptSignal) -> uuid.UUID | None:
        target_id = _safe_uuid(signal.target_id)
        if target_id is None:
            return None
        if signal.target_type == "knowledge_point":
            return target_id
        point_result = await self.db.execute(
            select(KnowledgePoint.id)
            .where(KnowledgePoint.curriculum_node_id == target_id, KnowledgePoint.status == "published")
            .order_by(KnowledgePoint.created_at.asc())
            .limit(1)
        )
        return point_result.scalar_one_or_none()

    async def _update_vocabulary(self, signal: AttemptSignal) -> MasteryUpdateResult:
        learner_id = uuid.UUID(signal.learner_id)
        item_id = _safe_uuid(signal.target_id)
        if item_id is None:
            return _fallback_result(signal, previous_score=None, previous_confidence=None)
        item_result = await self.db.execute(
            select(VocabularyItem).where(
                VocabularyItem.id == item_id,
                VocabularyItem.learner_id == learner_id,
            )
        )
        item = item_result.scalar_one_or_none()
        previous = item.confidence if item is not None else 0.0
        new_score = _next_score(previous or 0.0, signal)
        next_review_at = _next_review_at(datetime.now(timezone.utc), signal.correct, new_score)
        if item is not None:
            item.confidence = new_score
            item.review_count = (item.review_count or 0) + 1
            item.last_reviewed_at = datetime.now(timezone.utc)
            item.next_review_at = next_review_at
            item.status = "mastered" if new_score >= 0.8 else "learning"
        vector_result = await self.db.execute(
            select(VocabularyMasteryVector).where(
                VocabularyMasteryVector.vocabulary_item_id == item_id,
                VocabularyMasteryVector.learner_id == learner_id,
            )
        )
        vector = vector_result.scalar_one_or_none()
        if vector is None and item is not None:
            vector = VocabularyMasteryVector(
                learner_id=learner_id,
                vocabulary_item_id=item_id,
                recognition=0.0,
                recall=0.0,
                spelling=0.0,
                listening=0.0,
                context_use=0.0,
                production=0.0,
            )
            self.db.add(vector)
        if vector is not None:
            for field in ("recognition", "recall", "spelling", "context_use", "production"):
                setattr(vector, field, new_score)
        await self.db.flush()
        return _result(
            signal,
            target_id=str(item_id),
            previous_score=previous,
            new_score=new_score,
            previous_confidence=previous,
            new_confidence=new_score,
            next_review_at=next_review_at,
            status=item.status if item is not None else None,
        )

    async def _update_writing_phrase(self, signal: AttemptSignal) -> MasteryUpdateResult:
        learner_id = uuid.UUID(signal.learner_id)
        phrase_id = _safe_uuid(signal.target_id)
        if phrase_id is None:
            return _fallback_result(signal, previous_score=None, previous_confidence=None)
        mastery_result = await self.db.execute(
            select(WritingPhraseMastery).where(
                WritingPhraseMastery.learner_id == learner_id,
                WritingPhraseMastery.phrase_id == phrase_id,
            )
        )
        mastery = mastery_result.scalar_one_or_none()
        if mastery is None:
            mastery = WritingPhraseMastery(
                learner_id=learner_id,
                phrase_id=phrase_id,
                status="learning",
                recognition=0.0,
                recall=0.0,
                context_use=0.0,
                production=0.0,
                confidence=0.0,
                evidence_refs=[],
            )
            self.db.add(mastery)
        previous = mastery.production or mastery.confidence or 0.0
        new_score = _next_score(previous, signal)
        now = datetime.now(timezone.utc)
        mastery.recognition = max(mastery.recognition, new_score)
        mastery.recall = new_score
        mastery.context_use = new_score
        mastery.production = new_score
        mastery.confidence = min(1.0, (mastery.confidence or 0.0) + 0.12)
        mastery.status = "mastered" if new_score >= 0.8 else "reviewing" if not signal.correct else "learning"
        mastery.last_seen_at = now
        mastery.next_review_at = _next_review_at(now, signal.correct, new_score)
        mastery.evidence_refs = [ref.model_dump(mode="json") for ref in signal.evidence_refs]
        await self.db.flush()
        return _result(
            signal,
            target_id=str(phrase_id),
            previous_score=previous,
            new_score=new_score,
            previous_confidence=previous,
            new_confidence=mastery.confidence,
            next_review_at=mastery.next_review_at,
            status=mastery.status,
        )


def _next_score(previous: float, signal: AttemptSignal) -> float:
    base_change = 0.18 if signal.correct else -0.12
    score_bonus = _clamp(signal.score or 0.0) * 0.04 if signal.correct else 0.0
    hint_penalty = min(signal.hint_count * 0.02, 0.08)
    retry_penalty = min(signal.retry_count * 0.03, 0.09)
    return _clamp(previous + base_change + score_bonus - hint_penalty - retry_penalty)


def _next_review_at(now: datetime, correct: bool, score: float) -> datetime:
    if not correct:
        return now + timedelta(days=1)
    if score >= 0.8:
        return now + timedelta(days=7)
    return now + timedelta(days=4)


def _result(
    signal: AttemptSignal,
    *,
    target_id: str,
    previous_score: float | None,
    new_score: float,
    previous_confidence: float | None,
    new_confidence: float,
    next_review_at: datetime | None,
    status: str | None,
    metadata: dict | None = None,
) -> MasteryUpdateResult:
    return MasteryUpdateResult(
        learner_id=signal.learner_id,
        target_type=signal.target_type,
        target_id=target_id,
        previous_score=previous_score,
        new_score=new_score,
        previous_confidence=previous_confidence,
        new_confidence=new_confidence,
        mastery_delta=new_score - (previous_score or 0.0),
        weakness_tags=[] if signal.correct else [signal.error_type or "needs_review"],
        forgetting_risk=max(0.0, 1.0 - new_score),
        next_review_at=next_review_at,
        status=status,
        evidence_refs=signal.evidence_refs,
        metadata=metadata or {},
    )


def _fallback_result(
    signal: AttemptSignal,
    *,
    previous_score: float | None,
    previous_confidence: float | None,
) -> MasteryUpdateResult:
    new_score = _next_score(previous_score or 0.0, signal)
    return _result(
        signal,
        target_id=signal.target_id,
        previous_score=previous_score,
        new_score=new_score,
        previous_confidence=previous_confidence,
        new_confidence=_clamp(new_score),
        next_review_at=_next_review_at(datetime.now(timezone.utc), signal.correct, new_score),
        status="learning" if signal.correct else "reviewing",
    )


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _safe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None
