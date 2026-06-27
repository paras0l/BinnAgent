import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.layers import MemoryLayer
from src.memory.policies import normalize_skill
from src.memory.schemas import MemoryContext, RetrievedMemoryItem
from src.models.error_pattern import ErrorPattern
from src.models.knowledge import LearnerKnowledgeState
from src.models.memory import (
    LearnerMemorySettings,
    LearnerModelMemory,
    LearningEpisode,
    LearningMemoryEvent,
    MemoryContextLog,
    MemoryOperation,
    TeachingStrategyMemory,
    WritingPhraseMastery,
)
from src.models.vocabulary import VocabularyMasteryVector, VocabularyMistake


class MemoryRetriever:
    """Task-scoped memory reads that avoid dumping full history into prompts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def for_chat(
        self,
        *,
        learner_id: uuid.UUID,
        thread_id: uuid.UUID | None = None,
        skill: str | None = None,
        limit: int = 8,
    ) -> MemoryContext:
        return await self.retrieve_context(
            learner_id=learner_id,
            reason="chat",
            skill=skill or "general",
            thread_id=thread_id,
            limit=limit,
        )

    async def for_daily_plan(self, *, learner_id: uuid.UUID, limit: int = 8) -> MemoryContext:
        return await self.retrieve_context(
            learner_id=learner_id,
            reason="daily_plan",
            skill="general",
            limit=limit,
        )

    async def for_vocabulary_practice(
        self, *, learner_id: uuid.UUID, limit: int = 6
    ) -> MemoryContext:
        return await self.retrieve_context(
            learner_id=learner_id,
            reason="vocabulary_practice",
            skill="vocabulary",
            limit=limit,
        )

    async def for_knowledge_exercise(
        self, *, learner_id: uuid.UUID, limit: int = 6
    ) -> MemoryContext:
        return await self.retrieve_context(
            learner_id=learner_id,
            reason="knowledge_exercise",
            skill="knowledge",
            limit=limit,
        )

    async def for_essay_review(self, *, learner_id: uuid.UUID, limit: int = 6) -> MemoryContext:
        return await self.retrieve_context(
            learner_id=learner_id,
            reason="essay_review",
            skill="writing",
            limit=limit,
        )

    async def for_writing_phrasebook(
        self, *, learner_id: uuid.UUID, limit: int = 6
    ) -> MemoryContext:
        return await self.retrieve_context(
            learner_id=learner_id,
            reason="writing_phrasebook",
            skill="writing",
            limit=limit,
        )

    async def for_memory_explanation(
        self, *, learner_id: uuid.UUID, skill: str | None = None, limit: int = 10
    ) -> MemoryContext:
        return await self.retrieve_context(
            learner_id=learner_id,
            reason="memory_explanation",
            skill=skill or "general",
            limit=limit,
        )

    async def retrieve_context(
        self,
        *,
        learner_id: uuid.UUID,
        reason: str,
        skill: str | None = None,
        thread_id: uuid.UUID | None = None,
        limit: int = 8,
        log: bool = True,
    ) -> MemoryContext:
        normalized_skill = normalize_skill(skill)
        items: list[RetrievedMemoryItem] = []
        excluded: list[str] = []
        dismissed = await self._dismissed_targets(learner_id)
        include_low_confidence = await self._include_low_confidence(learner_id)

        items.extend(
            await self._learner_model_items(
                learner_id, normalized_skill, dismissed, include_low_confidence
            )
        )
        items.extend(
            await self._teaching_strategy_items(
                learner_id, normalized_skill, dismissed, include_low_confidence
            )
        )
        items.extend(
            await self._learning_episode_items(
                learner_id, normalized_skill, dismissed, include_low_confidence
            )
        )

        for item in await self._error_pattern_items(
            learner_id, normalized_skill, include_low_confidence
        ):
            if item.id in dismissed:
                excluded.append(item.id)
            else:
                items.append(item)

        if normalized_skill in {"vocabulary", "general"}:
            items.extend(await self._vocabulary_items(learner_id, dismissed))
        if normalized_skill in {"writing", "general"}:
            items.extend(await self._writing_phrase_items(learner_id, dismissed))
        if normalized_skill in {"knowledge", "general"}:
            items.extend(await self._knowledge_items(learner_id, dismissed))

        items.extend(
            await self._recent_event_items(
                learner_id, normalized_skill, dismissed, include_low_confidence
            )
        )
        selected = items[:limit]
        context = MemoryContext(
            loaded_items=selected,
            excluded_items=excluded,
            retrieval_reason=reason,
        )
        if log:
            self.db.add(
                MemoryContextLog(
                    learner_id=learner_id,
                    thread_id=thread_id,
                    retrieval_reason=reason,
                    loaded_items=[
                        {
                            "id": item.id,
                            "type": item.type,
                            "layer": item.layer,
                            "skill": item.skill,
                        }
                        for item in selected
                    ],
                    excluded_items=excluded,
                    token_cost=len(context.prompt_text()),
                )
            )
            await self.db.flush()
        return context

    async def _dismissed_targets(self, learner_id: uuid.UUID) -> set[str]:
        result = await self.db.execute(
            select(MemoryOperation).where(
                MemoryOperation.learner_id == learner_id,
                MemoryOperation.operation_type.in_(["delete", "disable"]),
            )
        )
        dismissed = set()
        for operation in result.scalars().all():
            if operation.target_id:
                dismissed.add(f"{operation.target_type}:{operation.target_id}")
                dismissed.add(f"{operation.target_type.replace('_', '-')}:{operation.target_id}")
        return dismissed

    async def _include_low_confidence(self, learner_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(LearnerMemorySettings).where(LearnerMemorySettings.learner_id == learner_id)
        )
        settings = result.scalar_one_or_none()
        return bool(settings and settings.low_confidence_memory_enabled)

    async def _error_pattern_items(
        self, learner_id: uuid.UUID, skill: str, include_low_confidence: bool
    ) -> list[RetrievedMemoryItem]:
        min_confidence = 0.0 if include_low_confidence else 0.4
        query = select(ErrorPattern).where(
            ErrorPattern.learner_id == learner_id,
            ErrorPattern.status.in_(["active", "improving"]),
            ErrorPattern.confidence >= min_confidence,
        )
        if skill != "general":
            query = query.where(ErrorPattern.skill == skill)
        result = await self.db.execute(
            query.order_by(ErrorPattern.frequency.desc(), ErrorPattern.updated_at.desc()).limit(5)
        )
        items = []
        for pattern in result.scalars().all():
            evidence = pattern.evidence_refs if isinstance(pattern.evidence_refs, list) else []
            items.append(
                RetrievedMemoryItem(
                    id=f"error_pattern:{pattern.id}",
                    type="error_pattern",
                    skill=pattern.skill,
                    summary=pattern.description or f"{pattern.pattern} 仍需练习",
                    confidence=float(pattern.confidence or 0.5),
                    layer=MemoryLayer.LEARNER_MODEL.value,
                    evidence_refs=[str(item) for item in evidence[:3]],
                    reason=pattern.recommended_drill,
                    payload={
                        "pattern": pattern.pattern,
                        "status": pattern.status,
                        "severity": pattern.severity,
                    },
                )
            )
        return items

    async def _learner_model_items(
        self,
        learner_id: uuid.UUID,
        skill: str,
        dismissed: set[str],
        include_low_confidence: bool,
    ) -> list[RetrievedMemoryItem]:
        min_confidence = 0.0 if include_low_confidence else 0.4
        query = select(LearnerModelMemory).where(
            LearnerModelMemory.learner_id == learner_id,
            LearnerModelMemory.status.in_(["active", "improving"]),
            LearnerModelMemory.confidence >= min_confidence,
        )
        if skill != "general":
            query = query.where(LearnerModelMemory.skill == skill)
        result = await self.db.execute(
            query.order_by(LearnerModelMemory.last_reflected_at.desc()).limit(5)
        )
        items = []
        for memory in result.scalars().all():
            item_id = f"learner_model_memory:{memory.id}"
            if item_id in dismissed:
                continue
            items.append(
                RetrievedMemoryItem(
                    id=item_id,
                    type="learner_model_memory",
                    skill=memory.skill,
                    summary=memory.claim,
                    confidence=float(memory.confidence or 0.5),
                    layer=MemoryLayer.LEARNER_MODEL.value,
                    evidence_refs=[str(item) for item in (memory.evidence_refs or [])[:3]],
                    reason=f"{memory.model_type}:{memory.status}",
                    payload={
                        "model_type": memory.model_type,
                        "claim_key": memory.claim_key,
                        "status": memory.status,
                    },
                )
            )
        return items

    async def _teaching_strategy_items(
        self,
        learner_id: uuid.UUID,
        skill: str,
        dismissed: set[str],
        include_low_confidence: bool,
    ) -> list[RetrievedMemoryItem]:
        min_confidence = 0.0 if include_low_confidence else 0.4
        query = select(TeachingStrategyMemory).where(
            TeachingStrategyMemory.learner_id == learner_id,
            TeachingStrategyMemory.status == "active",
            TeachingStrategyMemory.confidence >= min_confidence,
        )
        if skill != "general":
            query = query.where(TeachingStrategyMemory.skill == skill)
        result = await self.db.execute(
            query.order_by(TeachingStrategyMemory.updated_at.desc()).limit(4)
        )
        items = []
        for memory in result.scalars().all():
            item_id = f"teaching_strategy_memory:{memory.id}"
            if item_id in dismissed:
                continue
            items.append(
                RetrievedMemoryItem(
                    id=item_id,
                    type="teaching_strategy_memory",
                    skill=memory.skill,
                    summary=f"{memory.when_to_use} {memory.effect_summary}",
                    confidence=float(memory.confidence or 0.5),
                    layer=MemoryLayer.LEARNER_MODEL.value,
                    evidence_refs=[str(item) for item in (memory.evidence_refs or [])[:3]],
                    reason=memory.strategy,
                    payload={"strategy": memory.strategy, "steps": memory.steps or []},
                )
            )
        return items

    async def _learning_episode_items(
        self,
        learner_id: uuid.UUID,
        skill: str,
        dismissed: set[str],
        include_low_confidence: bool,
    ) -> list[RetrievedMemoryItem]:
        min_confidence = 0.0 if include_low_confidence else 0.4
        query = select(LearningEpisode).where(
            LearningEpisode.learner_id == learner_id,
            LearningEpisode.confidence >= min_confidence,
        )
        if skill != "general":
            query = query.where(LearningEpisode.skill == skill)
        result = await self.db.execute(query.order_by(LearningEpisode.created_at.desc()).limit(4))
        items = []
        for episode in result.scalars().all():
            item_id = f"learning_episode:{episode.id}"
            if item_id in dismissed:
                continue
            items.append(
                RetrievedMemoryItem(
                    id=item_id,
                    type="learning_episode",
                    skill=episode.skill,
                    summary=episode.summary,
                    confidence=float(episode.confidence or 0.5),
                    layer=MemoryLayer.EVIDENCE.value,
                    evidence_refs=[str(item) for item in (episode.source_event_ids or [])[:3]],
                    reason=episode.next_action,
                    payload={
                        "episode_type": episode.episode_type,
                        "observed_patterns": episode.observed_patterns or [],
                    },
                )
            )
        return items

    async def _vocabulary_items(
        self, learner_id: uuid.UUID, dismissed: set[str]
    ) -> list[RetrievedMemoryItem]:
        result = await self.db.execute(
            select(VocabularyMistake)
            .where(VocabularyMistake.learner_id == learner_id, VocabularyMistake.active.is_(True))
            .order_by(VocabularyMistake.updated_at.desc())
            .limit(3)
        )
        items = [
            RetrievedMemoryItem(
                id=f"vocabulary_mistake:{mistake.id}",
                type="vocabulary_mistake",
                skill="vocabulary",
                summary=mistake.note or f"{mistake.mistake_type} 需要复习",
                confidence=0.85,
                layer=MemoryLayer.EVIDENCE.value,
                evidence_refs=[f"vocabulary_attempt:{mistake.attempt_id}"] if mistake.attempt_id else [],
                reason="vocabulary_practice",
                payload={"mistake_type": mistake.mistake_type, "item_id": str(mistake.vocabulary_item_id)},
            )
            for mistake in result.scalars().all()
            if f"vocabulary_mistake:{mistake.id}" not in dismissed
        ]
        mastery_result = await self.db.execute(
            select(VocabularyMasteryVector)
            .where(VocabularyMasteryVector.learner_id == learner_id)
            .order_by(VocabularyMasteryVector.updated_at.desc())
            .limit(3)
        )
        for mastery in mastery_result.scalars().all():
            weakest = min(
                {
                    "recognition": mastery.recognition,
                    "recall": mastery.recall,
                    "spelling": mastery.spelling,
                    "listening": mastery.listening,
                    "context_use": mastery.context_use,
                    "production": mastery.production,
                }.items(),
                key=lambda item: item[1],
            )
            if weakest[1] < 0.5:
                items.append(
                    RetrievedMemoryItem(
                        id=f"vocabulary_mastery:{mastery.id}",
                        type="vocabulary_mastery",
                        skill="vocabulary",
                        summary=f"词汇 {weakest[0]} 掌握偏低，适合安排对应练习。",
                        confidence=0.75,
                        layer=MemoryLayer.LEARNER_MODEL.value,
                        evidence_refs=[f"vocabulary_item:{mastery.vocabulary_item_id}"],
                        reason=f"vocabulary_{weakest[0]}",
                    )
                )
        return items

    async def _writing_phrase_items(
        self, learner_id: uuid.UUID, dismissed: set[str]
    ) -> list[RetrievedMemoryItem]:
        result = await self.db.execute(
            select(WritingPhraseMastery)
            .where(
                WritingPhraseMastery.learner_id == learner_id,
                WritingPhraseMastery.status.in_(["learning", "reviewing"]),
            )
            .order_by(WritingPhraseMastery.updated_at.desc())
            .limit(3)
        )
        return [
            RetrievedMemoryItem(
                id=f"writing_phrase_mastery:{mastery.id}",
                type="writing_phrase_mastery",
                skill="writing",
                summary=f"句式掌握仍在 {mastery.status}，建议练 {mastery.recommended_drill or '造句迁移'}。",
                confidence=float(mastery.confidence or 0.5),
                layer=MemoryLayer.LEARNER_MODEL.value,
                evidence_refs=[str(item) for item in (mastery.evidence_refs or [])[:3]],
                reason=mastery.recommended_drill,
                payload={"phrase_id": str(mastery.phrase_id), "status": mastery.status},
            )
            for mastery in result.scalars().all()
            if f"writing_phrase_mastery:{mastery.id}" not in dismissed
        ]

    async def _knowledge_items(
        self, learner_id: uuid.UUID, dismissed: set[str]
    ) -> list[RetrievedMemoryItem]:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(LearnerKnowledgeState)
            .where(
                LearnerKnowledgeState.learner_id == learner_id,
                LearnerKnowledgeState.status != "mastered",
            )
            .order_by(LearnerKnowledgeState.next_review_at.asc().nullsfirst())
            .limit(4)
        )
        items = []
        for state in result.scalars().all():
            due = state.next_review_at is None or state.next_review_at <= now
            items.append(
                RetrievedMemoryItem(
                    id=f"knowledge_state:{state.id}",
                    type="knowledge_state",
                    skill="knowledge",
                    summary=(
                        f"知识点 mastery={state.mastery_score:.2f}，"
                        f"{'已到复习时间' if due else '后续复习'}。"
                    ),
                    confidence=float(state.confidence or 0.5),
                    layer=MemoryLayer.LEARNER_MODEL.value,
                    evidence_refs=[f"knowledge_point:{state.knowledge_point_id}"],
                    reason="textbook_review" if due else "knowledge_followup",
                    payload={"knowledge_point_id": str(state.knowledge_point_id), "due": due},
                )
            )
        return items

    async def _recent_event_items(
        self,
        learner_id: uuid.UUID,
        skill: str,
        dismissed: set[str],
        include_low_confidence: bool,
    ) -> list[RetrievedMemoryItem]:
        query = select(LearningMemoryEvent).where(
            LearningMemoryEvent.learner_id == learner_id,
            LearningMemoryEvent.visibility != "deleted",
        )
        if not include_low_confidence:
            query = query.where(LearningMemoryEvent.confidence >= 0.4)
        if skill != "general":
            query = query.where(LearningMemoryEvent.skill == skill)
        result = await self.db.execute(query.order_by(LearningMemoryEvent.occurred_at.desc()).limit(3))
        items = []
        for event in result.scalars().all():
            item_id = f"learning_memory_event:{event.id}"
            if item_id in dismissed:
                continue
            items.append(
                RetrievedMemoryItem(
                    id=item_id,
                    type="learning_event",
                    skill=event.skill,
                    summary=_event_summary(event),
                    confidence=float(event.confidence or 0.5),
                    layer=MemoryLayer.EVIDENCE.value,
                    evidence_refs=[f"{event.source_type}:{event.source_id}"] if event.source_id else [],
                    reason=event.event_type,
                    payload=event.payload or {},
                )
            )
        return items


def _event_summary(event: LearningMemoryEvent) -> str:
    payload = event.payload or {}
    if event.event_type == "vocabulary_attempted":
        return f"最近词汇练习结果：{payload.get('result', 'unknown')}。"
    if event.event_type == "knowledge_exercise_answered":
        return f"最近教材练习：{'正确' if payload.get('correct') else '需要订正'}。"
    if event.event_type == "writing_phrase_attempted":
        return f"最近句式练习得分 {payload.get('score', 0)}。"
    if event.event_type == "chat_learning_turn":
        return str(payload.get("summary") or "完成一次学习对话。")
    return event.event_type.replace("_", " ")
