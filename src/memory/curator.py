import uuid
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.profile_store import ProfileStore
from src.models.error_pattern import ErrorPattern
from src.models.memory import LearningMemoryEvent, WritingPhraseMastery


ERROR_EVENT_TYPES = {
    "chat_error_observed",
    "vocabulary_mistake_recorded",
    "knowledge_exercise_answered",
    "writing_phrase_attempted",
}


class MemoryCurator:
    """Consolidates raw events into durable weakness and mastery state."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def curate_learner(self, learner_id: uuid.UUID, *, commit: bool = False) -> dict[str, Any]:
        events = await self._recent_events(learner_id)
        await self._update_error_patterns(learner_id, events)
        await self._update_writing_phrase_mastery(learner_id, events)
        weak_skills = await self._active_weak_skills(learner_id)
        await ProfileStore(self.db).update_weak_skills_no_commit(learner_id, weak_skills)
        if commit:
            await self.db.commit()
        return {
            "event_count": len(events),
            "active_weaknesses": weak_skills,
        }

    async def _recent_events(self, learner_id: uuid.UUID) -> list[LearningMemoryEvent]:
        result = await self.db.execute(
            select(LearningMemoryEvent)
            .where(LearningMemoryEvent.learner_id == learner_id)
            .order_by(LearningMemoryEvent.occurred_at.desc())
            .limit(500)
        )
        return list(result.scalars().all())

    async def _update_error_patterns(
        self, learner_id: uuid.UUID, events: list[LearningMemoryEvent]
    ) -> None:
        grouped: dict[tuple[str, str, str | None], list[LearningMemoryEvent]] = defaultdict(list)
        for event in events:
            if event.event_type not in ERROR_EVENT_TYPES:
                continue
            payload = event.payload or {}
            is_negative = payload.get("correct") is False or payload.get("result") in {
                "incorrect",
                "revealed",
            }
            pattern = payload.get("error_type") or payload.get("pattern")
            if not pattern and not is_negative:
                continue
            grouped[(event.skill, str(pattern or "needs_practice"), event.subskill)].append(event)

        for (skill, pattern, subskill), evidence in grouped.items():
            latest = max(evidence, key=lambda item: item.occurred_at)
            existing = await self._get_error_pattern(learner_id, skill, pattern)
            evidence_refs = _merge_evidence(
                existing.evidence_refs if existing else [],
                [_event_ref(event) for event in evidence],
            )
            recent_total = len(evidence)
            recent_correct = sum(
                1
                for event in evidence[:10]
                if (event.payload or {}).get("correct") is True
                or (event.payload or {}).get("result") == "correct"
            )
            status = "active"
            if recent_total >= 3 and recent_correct >= max(2, recent_total // 2):
                status = "improving"
            severity = "high" if recent_total >= 5 else "medium" if recent_total >= 2 else "low"
            if existing is None:
                self.db.add(
                    ErrorPattern(
                        learner_id=learner_id,
                        skill=skill,
                        subskill=subskill,
                        pattern=pattern,
                        description=_pattern_description(skill, pattern),
                        frequency=min(32767, recent_total),
                        severity=severity,
                        confidence=min(0.95, 0.45 + recent_total * 0.1),
                        status=status,
                        evidence_refs=evidence_refs,
                        recommended_drill=_recommended_drill(skill, pattern),
                        first_seen_at=latest.occurred_at,
                        last_seen_at=latest.occurred_at,
                    )
                )
            elif existing.status not in {"dismissed", "deleted", "disabled"}:
                existing.subskill = existing.subskill or subskill
                existing.frequency = min(32767, (existing.frequency or 0) + recent_total)
                existing.severity = severity
                existing.confidence = min(0.98, max(existing.confidence or 0.5, 0.45 + recent_total * 0.1))
                existing.status = status
                existing.evidence_refs = evidence_refs
                existing.recommended_drill = existing.recommended_drill or _recommended_drill(skill, pattern)
                existing.first_seen_at = existing.first_seen_at or latest.occurred_at
                existing.last_seen_at = latest.occurred_at

    async def _get_error_pattern(
        self, learner_id: uuid.UUID, skill: str, pattern: str
    ) -> ErrorPattern | None:
        result = await self.db.execute(
            select(ErrorPattern).where(
                ErrorPattern.learner_id == learner_id,
                ErrorPattern.skill == skill,
                ErrorPattern.pattern == pattern,
            )
        )
        return result.scalar_one_or_none()

    async def _update_writing_phrase_mastery(
        self, learner_id: uuid.UUID, events: list[LearningMemoryEvent]
    ) -> None:
        phrase_events = [
            event
            for event in events
            if event.event_type == "writing_phrase_attempted" and (event.payload or {}).get("phrase_id")
        ]
        for event in phrase_events:
            payload = event.payload or {}
            phrase_id = uuid.UUID(str(payload["phrase_id"]))
            result = await self.db.execute(
                select(WritingPhraseMastery).where(
                    WritingPhraseMastery.learner_id == learner_id,
                    WritingPhraseMastery.phrase_id == phrase_id,
                )
            )
            mastery = result.scalar_one_or_none()
            if mastery is None:
                mastery = WritingPhraseMastery(
                    learner_id=learner_id,
                    phrase_id=phrase_id,
                    skill="writing",
                    subskill=_phrase_subskill(payload),
                    status="learning",
                    evidence_refs=[],
                )
                self.db.add(mastery)
            score = float(payload.get("score", 1.0 if payload.get("correct") else 0.0) or 0.0)
            delta = 0.12 if score >= 0.8 else -0.08
            dimension = _phrase_dimension(str(payload.get("exercise_type") or "production"))
            setattr(mastery, dimension, min(1.0, max(0.0, getattr(mastery, dimension) + delta)))
            mastery.confidence = min(1.0, mastery.confidence + 0.12)
            mastery.status = "mastered" if min(
                mastery.recognition, mastery.recall, mastery.context_use, mastery.production
            ) >= 0.7 else "reviewing" if score < 0.8 else "learning"
            mastery.last_seen_at = event.occurred_at
            mastery.next_review_at = event.occurred_at + timedelta(days=4 if score >= 0.8 else 1)
            mastery.recommended_drill = "writing_phrase_replacement" if score < 0.8 else "writing_phrase_production"
            mastery.evidence_refs = _merge_evidence(mastery.evidence_refs, [_event_ref(event)])

    async def _active_weak_skills(self, learner_id: uuid.UUID) -> list[str]:
        result = await self.db.execute(
            select(ErrorPattern).where(
                ErrorPattern.learner_id == learner_id,
                ErrorPattern.status.in_(["active", "improving"]),
            )
        )
        counts = Counter(pattern.skill for pattern in result.scalars().all())
        return [skill for skill, _ in counts.most_common(6)]


def _event_ref(event: LearningMemoryEvent) -> str:
    return f"learning_memory_event:{event.id}"


def _merge_evidence(existing: Any, refs: list[str]) -> list[str]:
    merged: list[str] = []
    if isinstance(existing, list):
        merged.extend(str(item) for item in existing if item)
    elif isinstance(existing, dict):
        merged.extend(str(item) for item in existing.get("refs", []) if item)
    for ref in refs:
        if ref and ref not in merged:
            merged.append(ref)
    return merged[-20:]


def _pattern_description(skill: str, pattern: str) -> str:
    labels = {
        "spelling_error": "拼写记忆不稳定，需要听音拼写和字母级反馈。",
        "needs_practice": "近期练习表现不稳定，需要继续巩固。",
        "wrong_position": "句式使用位置不稳定，需要替换和造句练习。",
    }
    return labels.get(pattern, f"{skill} 中出现 {pattern} 模式，需要针对性练习。")


def _recommended_drill(skill: str, pattern: str) -> str:
    if skill == "vocabulary":
        return "spelling" if "spelling" in pattern else "active_recall"
    if skill == "writing":
        return "writing_phrase_replacement"
    if skill == "knowledge":
        return "textbook_review"
    return "targeted_practice"


def _phrase_dimension(exercise_type: str) -> str:
    return {
        "recognition": "recognition",
        "blank": "recall",
        "replacement": "context_use",
        "production": "production",
    }.get(exercise_type, "production")


def _phrase_subskill(payload: dict[str, Any]) -> str | None:
    tags = payload.get("tags")
    if isinstance(tags, list) and tags:
        return str(tags[0]).lower()
    return payload.get("subskill")
