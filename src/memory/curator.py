import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.layers import MemoryLayer
from src.memory.profile_store import ProfileStore
from src.models.error_pattern import ErrorPattern
from src.models.memory import (
    LearnerModelMemory,
    LearningEpisode,
    LearningMemoryEvent,
    TeachingStrategyMemory,
    WritingPhraseMastery,
)


ERROR_EVENT_TYPES = {
    "chat_error_observed",
    "vocabulary_mistake_recorded",
    "knowledge_exercise_answered",
    "writing_phrase_attempted",
}


class MemoryCurator:
    """Reflects raw learning evidence into durable learner state."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def curate_learner(self, learner_id: uuid.UUID, *, commit: bool = False) -> dict[str, Any]:
        return await self.reflect(learner_id, commit=commit)

    async def reflect(
        self,
        learner_id: uuid.UUID,
        *,
        session_id: uuid.UUID | None = None,
        commit: bool = False,
    ) -> dict[str, Any]:
        events = await self._recent_events(learner_id)
        if session_id:
            events = [event for event in events if event.session_id == session_id]
        await self._update_error_patterns(learner_id, events)
        await self._update_writing_phrase_mastery(learner_id, events)
        episodes = await self._reflect_learning_episodes(learner_id, events)
        learner_models = await self._reflect_learner_models(learner_id, events, episodes)
        strategies = await self._reflect_teaching_strategies(learner_id, events, episodes)
        weak_skills = await self._active_weak_skills(learner_id)
        await ProfileStore(self.db).update_weak_skills_no_commit(learner_id, weak_skills)
        if commit:
            await self.db.commit()
        return {
            "event_count": len(events),
            "episode_count": len(episodes),
            "learner_model_count": len(learner_models),
            "teaching_strategy_count": len(strategies),
            "reflection_layer": MemoryLayer.GOVERNANCE.value,
            "read_layers": [MemoryLayer.EVIDENCE.value],
            "updated_layers": [MemoryLayer.EVIDENCE.value, MemoryLayer.LEARNER_MODEL.value],
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
            mastery.recommended_drill = (
                "writing_phrase_replacement" if score < 0.8 else "writing_phrase_production"
            )
            mastery.evidence_refs = _merge_evidence(mastery.evidence_refs, [_event_ref(event)])

    async def _reflect_learning_episodes(
        self, learner_id: uuid.UUID, events: list[LearningMemoryEvent]
    ) -> list[LearningEpisode]:
        grouped: dict[tuple[str, str], list[LearningMemoryEvent]] = defaultdict(list)
        for event in events:
            if event.event_type.startswith("user_"):
                continue
            group_key = str(event.session_id) if event.session_id else f"{event.skill}:{event.event_type}"
            grouped[(group_key, event.skill)].append(event)

        episodes: list[LearningEpisode] = []
        for (group_key, skill), group_events in grouped.items():
            if not group_events:
                continue
            newest = max(group_events, key=lambda item: item.occurred_at)
            session_id = newest.session_id if group_key == str(newest.session_id) else None
            event_ids = [str(event.id) for event in sorted(group_events, key=lambda item: item.occurred_at)]
            reflection_key = (
                f"session:{session_id}:{skill}" if session_id else f"events:{skill}:{'-'.join(event_ids[-12:])}"
            )
            result = await self.db.execute(
                select(LearningEpisode).where(
                    LearningEpisode.learner_id == learner_id,
                    LearningEpisode.reflection_key == reflection_key,
                )
            )
            episode = result.scalar_one_or_none()
            observed_patterns = _observed_patterns(group_events)
            effective_feedback = _effective_feedback(group_events)
            summary = _episode_summary(skill, group_events, observed_patterns)
            next_action = _next_action(skill, observed_patterns, group_events)
            confidence = _group_confidence(group_events)
            if episode is None:
                episode = LearningEpisode(
                    learner_id=learner_id,
                    session_id=session_id,
                    reflection_key=reflection_key,
                    episode_type=_episode_type(skill, group_events),
                    skill=skill,
                    subskill=_dominant_subskill(group_events),
                    summary=summary,
                    observed_patterns=observed_patterns,
                    effective_feedback=effective_feedback,
                    next_action=next_action,
                    source_event_ids=event_ids,
                    confidence=confidence,
                )
                self.db.add(episode)
            else:
                episode.summary = summary
                episode.observed_patterns = observed_patterns
                episode.effective_feedback = effective_feedback
                episode.next_action = next_action
                episode.source_event_ids = event_ids
                episode.confidence = confidence
            episodes.append(episode)
        return episodes

    async def _reflect_learner_models(
        self,
        learner_id: uuid.UUID,
        events: list[LearningMemoryEvent],
        episodes: list[LearningEpisode],
    ) -> list[LearnerModelMemory]:
        models: list[LearnerModelMemory] = []
        pattern_events: dict[tuple[str, str, str | None], list[LearningMemoryEvent]] = defaultdict(list)
        for event in events:
            payload = event.payload or {}
            pattern = payload.get("error_type") or payload.get("pattern")
            if pattern:
                pattern_events[(event.skill, str(pattern), event.subskill)].append(event)

        for (skill, pattern, subskill), evidence in pattern_events.items():
            correct_count = sum(
                1
                for event in evidence
                if (event.payload or {}).get("correct") is True
                or (event.payload or {}).get("result") == "correct"
            )
            incorrect_count = max(0, len(evidence) - correct_count)
            if not evidence or (len(evidence) < 2 and incorrect_count == 0):
                continue
            status = "improving" if correct_count >= 2 and correct_count >= incorrect_count else "active"
            if status == "improving" and incorrect_count == 0 and correct_count >= 3:
                status = "resolved"
            claim_key = f"pattern:{pattern}"
            claim = _learner_model_claim(skill, pattern, status)
            model = await self._upsert_learner_model(
                learner_id=learner_id,
                model_type="skill_profile",
                skill=skill,
                subskill=subskill,
                claim_key=claim_key,
                claim=claim,
                status=status,
                confidence=min(0.95, 0.5 + len(evidence) * 0.08 + len(episodes) * 0.02),
                evidence_refs=_merge_evidence([], [_event_ref(event) for event in evidence]),
            )
            models.append(model)

        for event in events:
            if event.event_type != "user_deleted_memory":
                continue
            payload = event.payload or {}
            target_type = payload.get("operation_type")
            before = payload.get("before") if isinstance(payload.get("before"), dict) else {}
            pattern = before.get("pattern") or before.get("claim_key")
            if target_type == "delete" and pattern:
                model = await self._upsert_learner_model(
                    learner_id=learner_id,
                    model_type="skill_profile",
                    skill=str(before.get("skill") or event.skill),
                    subskill=None,
                    claim_key=str(pattern),
                    claim=f"用户已否认或删除 {pattern} 相关学习判断。",
                    status="dismissed",
                    confidence=1.0,
                    evidence_refs=[_event_ref(event)],
                )
                models.append(model)
        return models

    async def _upsert_learner_model(
        self,
        *,
        learner_id: uuid.UUID,
        model_type: str,
        skill: str,
        subskill: str | None,
        claim_key: str,
        claim: str,
        status: str,
        confidence: float,
        evidence_refs: list[str],
    ) -> LearnerModelMemory:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(LearnerModelMemory).where(
                LearnerModelMemory.learner_id == learner_id,
                LearnerModelMemory.model_type == model_type,
                LearnerModelMemory.skill == skill,
                LearnerModelMemory.subskill == subskill,
                LearnerModelMemory.claim_key == claim_key,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = LearnerModelMemory(
                learner_id=learner_id,
                model_type=model_type,
                skill=skill,
                subskill=subskill,
                claim_key=claim_key,
                claim=claim,
                confidence=confidence,
                status=status,
                evidence_refs=evidence_refs,
                last_reflected_at=now,
            )
            self.db.add(model)
            return model
        if model.status not in {"dismissed", "deleted", "disabled"}:
            model.claim = claim
            model.confidence = max(float(model.confidence or 0.0), confidence)
            model.status = status
            model.evidence_refs = _merge_evidence(model.evidence_refs, evidence_refs)
            model.last_reflected_at = now
        return model

    async def _reflect_teaching_strategies(
        self,
        learner_id: uuid.UUID,
        events: list[LearningMemoryEvent],
        episodes: list[LearningEpisode],
    ) -> list[TeachingStrategyMemory]:
        strategy_groups: dict[tuple[str, str], list[LearningMemoryEvent]] = defaultdict(list)
        for event in events:
            payload = event.payload or {}
            strategy = payload.get("teaching_strategy") or payload.get("feedback_strategy")
            hint_helped = payload.get("hint_used") and (
                payload.get("correct_after_hint") is True or payload.get("result") == "correct_after_hint"
            )
            if not strategy and hint_helped:
                strategy = "hint_then_retry"
            if strategy:
                strategy_groups[(event.skill, str(strategy))].append(event)

        memories: list[TeachingStrategyMemory] = []
        for (skill, strategy), evidence in strategy_groups.items():
            if not evidence:
                continue
            result = await self.db.execute(
                select(TeachingStrategyMemory).where(
                    TeachingStrategyMemory.learner_id == learner_id,
                    TeachingStrategyMemory.strategy == strategy,
                    TeachingStrategyMemory.skill == skill,
                )
            )
            memory = result.scalar_one_or_none()
            refs = _merge_evidence([], [_event_ref(event) for event in evidence])
            confidence = min(0.92, 0.55 + len(evidence) * 0.1 + len(episodes) * 0.02)
            if memory is None:
                memory = TeachingStrategyMemory(
                    learner_id=learner_id,
                    strategy=strategy,
                    skill=skill,
                    subskill=_dominant_subskill(evidence),
                    when_to_use=_strategy_when_to_use(skill, strategy),
                    steps=_strategy_steps(strategy),
                    effect_summary=_strategy_effect_summary(strategy, evidence),
                    confidence=confidence,
                    evidence_refs=refs,
                    status="active",
                )
                self.db.add(memory)
            elif memory.status not in {"dismissed", "deleted", "disabled"}:
                memory.confidence = max(float(memory.confidence or 0.0), confidence)
                memory.evidence_refs = _merge_evidence(memory.evidence_refs, refs)
                memory.effect_summary = _strategy_effect_summary(strategy, evidence)
            memories.append(memory)
        return memories

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


def _episode_type(skill: str, events: list[LearningMemoryEvent]) -> str:
    types = {event.event_type for event in events}
    if "writing_phrase_attempted" in types:
        return "writing_phrase_practice"
    if "knowledge_exercise_answered" in types:
        return "knowledge_exercise_session"
    if any(event.event_type.startswith("vocabulary") for event in events):
        return "vocabulary_session"
    if "essay_feedback_received" in types:
        return "essay_feedback"
    if skill == "grammar":
        return "grammar_micro_lesson"
    return "chat_tutoring_session"


def _observed_patterns(events: list[LearningMemoryEvent]) -> list[str]:
    patterns: list[str] = []
    for event in events:
        payload = event.payload or {}
        values = payload.get("observed_patterns") or payload.get("patterns")
        if isinstance(values, list):
            patterns.extend(str(item) for item in values if item)
        for key in ("error_type", "pattern", "mistake_type"):
            if payload.get(key):
                patterns.append(str(payload[key]))
        if payload.get("correct") is False or payload.get("result") in {"incorrect", "revealed"}:
            patterns.append("needs_practice")
    return list(dict.fromkeys(patterns))[:12]


def _effective_feedback(events: list[LearningMemoryEvent]) -> dict[str, Any]:
    strategies = []
    for event in events:
        payload = event.payload or {}
        strategy = payload.get("teaching_strategy") or payload.get("feedback_strategy")
        if strategy:
            strategies.append(str(strategy))
        if payload.get("hint_used") and (
            payload.get("correct_after_hint") is True or payload.get("result") == "correct_after_hint"
        ):
            strategies.append("hint_then_retry")
    return {"strategies": list(dict.fromkeys(strategies))[:5]} if strategies else {}


def _episode_summary(
    skill: str, events: list[LearningMemoryEvent], observed_patterns: list[str]
) -> str:
    total = len(events)
    correct = sum(
        1
        for event in events
        if (event.payload or {}).get("correct") is True
        or (event.payload or {}).get("result") in {"correct", "correct_after_hint"}
    )
    pattern_text = f"，主要模式：{', '.join(observed_patterns[:3])}" if observed_patterns else ""
    return f"{skill} 学习片段包含 {total} 条证据，{correct} 条表现为掌握或改善{pattern_text}。"


def _next_action(
    skill: str, observed_patterns: list[str], events: list[LearningMemoryEvent]
) -> str:
    if any("spelling" in pattern for pattern in observed_patterns):
        return "安排听音拼写与首字母提示后的重试。"
    if skill == "writing":
        return "继续用替换和造句检查句式能否迁移到作文中。"
    if skill == "knowledge":
        return "安排教材知识点复习，并用短题验证是否真正掌握。"
    if any((event.payload or {}).get("correct") is False for event in events):
        return "降低跨度，先做一次针对性订正再进入新任务。"
    return "保持当前节奏，并在下一次任务中抽查迁移使用。"


def _group_confidence(events: list[LearningMemoryEvent]) -> float:
    if not events:
        return 0.0
    return min(0.95, sum(float(event.confidence or 0.5) for event in events) / len(events))


def _dominant_subskill(events: list[LearningMemoryEvent]) -> str | None:
    counts = Counter(event.subskill for event in events if event.subskill)
    return counts.most_common(1)[0][0] if counts else None


def _learner_model_claim(skill: str, pattern: str, status: str) -> str:
    state = {
        "active": "仍是当前优先弱点",
        "improving": "已有改善但需要继续巩固",
        "resolved": "近期证据显示已基本解决",
    }.get(status, "需要继续观察")
    return f"用户在 {skill} 中的 {pattern} 模式{state}。"


def _strategy_when_to_use(skill: str, strategy: str) -> str:
    if strategy == "hint_then_retry":
        return f"{skill} 练习中出现错误但用户能在提示后继续尝试时使用。"
    if strategy == "teach_transition_by_replacement":
        return "写作中递进表达单一或句式位置不稳时使用。"
    return f"{skill} 学习任务需要个性化反馈时使用。"


def _strategy_steps(strategy: str) -> list[str]:
    if strategy == "hint_then_retry":
        return ["给出最小提示", "让用户重试", "答对后追加一次迁移练习"]
    if strategy == "teach_transition_by_replacement":
        return ["指出重复表达", "给出更自然替换", "替换原句", "再造一句"]
    return ["指出当前问题", "给出一个可执行提示", "让用户立即重试"]


def _strategy_effect_summary(strategy: str, events: list[LearningMemoryEvent]) -> str:
    success = sum(
        1
        for event in events
        if (event.payload or {}).get("correct_after_hint") is True
        or (event.payload or {}).get("result") in {"correct", "correct_after_hint"}
    )
    return f"{strategy} 在 {len(events)} 条证据中有 {success} 次带来正确或改善表现。"


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
