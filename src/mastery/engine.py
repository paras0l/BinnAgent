import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adaptive import (
    AssessmentEvidenceInput,
    DKTShadowPredictor,
    FSRSState,
    TeachingPolicyCompiler,
    evaluate_evidence,
    schedule_review,
    update_ability,
)
from src.adaptive.clock import Clock, SystemClock
from src.adaptive.fsrs import infer_rating
from src.config import settings
from src.mastery.types import AttemptSignal, MasteryUpdateResult
from src.models.adaptive import (
    AssessmentEvidence,
    DecisionTrace,
    DKTShadowPrediction,
    FSRSReviewState,
    KnowledgeStateUpdate,
    TeachingPolicyDecision,
)
from src.models.knowledge import KnowledgePoint, LearnerKnowledgeState
from src.models.memory import WritingPhraseMastery
from src.models.vocabulary import VocabularyItem, VocabularyMasteryVector


class MasteryEngine:
    def __init__(self, db: AsyncSession, *, clock: Clock | None = None):
        self.db = db
        self.clock = clock or SystemClock()

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

        now = self.clock.now()
        previous_score = state.mastery_score or 0.0
        previous_confidence = state.confidence or 0.0
        adaptive_context = await self._adaptive_evidence(
            signal=signal,
            learner_id=learner_id,
            knowledge_point_id=knowledge_point_id,
        )
        if adaptive_context is not None and adaptive_context[1] == "non_assessment":
            return _result(
                signal,
                target_id=str(knowledge_point_id),
                previous_score=previous_score,
                new_score=previous_score,
                previous_confidence=previous_confidence,
                new_confidence=previous_confidence,
                next_review_at=state.next_review_at,
                status=state.status,
                metadata={
                    "update_blocked": True,
                    "reason": "interaction_is_not_assessment",
                    "assessment_evidence_created": False,
                },
            )
        if adaptive_context is not None and adaptive_context[1] is None:
            evidence = adaptive_context[0]
            return _result(
                signal,
                target_id=str(knowledge_point_id),
                previous_score=previous_score,
                new_score=previous_score,
                previous_confidence=previous_confidence,
                new_confidence=previous_confidence,
                next_review_at=state.next_review_at,
                status=state.status,
                metadata={
                    "state_id": str(state.id) if state.id else None,
                    "evidence_id": str(evidence.id),
                    "update_blocked": True,
                    "reason": evidence.decision_reason,
                },
            )
        if adaptive_context is not None and adaptive_context[1] == "duplicate":
            evidence = adaptive_context[0]
            return _result(
                signal,
                target_id=str(knowledge_point_id),
                previous_score=previous_score,
                new_score=previous_score,
                previous_confidence=previous_confidence,
                new_confidence=previous_confidence,
                next_review_at=state.next_review_at,
                status=state.status,
                metadata={"evidence_id": str(evidence.id), "idempotent_replay": True},
            )

        irt_result = None
        if adaptive_context is not None:
            evidence = adaptive_context[0]
            irt_result = update_ability(
                previous_score,
                outcome_score=evidence.outcome_score,
                item_difficulty=evidence.item_difficulty_prior,
                independent=evidence.independent,
                hint_count=evidence.hint_count,
                retry_count=evidence.retry_count,
            )
            new_score = irt_result.ability
        else:
            new_score = _next_score(previous_score, signal)
        new_confidence = min(1.0, 0.2 + (state.exposure_count + 1) * 0.12)
        state.mastery_score = new_score
        state.confidence = new_confidence
        state.exposure_count = (state.exposure_count or 0) + 1
        state.correct_count = (state.correct_count or 0) + int(signal.correct)
        state.status = "mastered" if new_score >= 0.8 else "reviewing" if not signal.correct else "learning"
        state.last_seen_at = now
        state.next_review_at = _next_review_at(now, signal.correct, new_score)
        if irt_result is not None:
            state.ability = irt_result.ability
            state.predicted_success = irt_result.predicted_success
            state.state_model_version = irt_result.model_version
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
        adaptive_metadata: dict = {}
        if adaptive_context is not None and irt_result is not None:
            adaptive_metadata = await self._persist_adaptive_decision(
                signal=signal,
                state=state,
                evidence=adaptive_context[0],
                previous_score=previous_score,
                irt_result=irt_result,
                now=now,
            )
            state.next_review_at = adaptive_metadata["next_review_at"]
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
            metadata={"state_id": str(state.id), **adaptive_metadata},
        )

    async def _adaptive_evidence(
        self,
        *,
        signal: AttemptSignal,
        learner_id: uuid.UUID,
        knowledge_point_id: uuid.UUID,
    ) -> tuple[AssessmentEvidence | None, str | None] | None:
        attempt_id = _safe_uuid(signal.metadata.get("attempt_id"))
        difficulty_prior = signal.metadata.get("item_difficulty_prior")
        if (
            not settings.adaptive_learning_enabled
            or attempt_id is None
            or difficulty_prior is None
        ):
            return None
        if signal.metadata.get("interaction_type", "assessment") != "assessment":
            return None, "non_assessment"
        existing_result = await self.db.execute(
            select(AssessmentEvidence).where(AssessmentEvidence.attempt_id == attempt_id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing, "duplicate"

        evidence_input = AssessmentEvidenceInput(
            knowledge_point_id=str(knowledge_point_id),
            item_id=str(signal.metadata.get("question_id") or signal.target_id),
            evidence_mode=signal.metadata.get("evidence_mode", "recall"),
            outcome_score=_clamp(signal.score if signal.score is not None else float(signal.correct)),
            independent=signal.hint_count == 0 and signal.retry_count == 0,
            hint_count=signal.hint_count,
            retry_count=signal.retry_count,
            response_time_ms=signal.response_time_ms,
            error_tags=[signal.error_type] if signal.error_type else [],
            semantic_confidence=_clamp(signal.metadata.get("semantic_confidence", 1.0)),
            item_difficulty_prior=_clamp(difficulty_prior),
            evidence_ref=str(attempt_id),
            interaction_type=signal.metadata.get("interaction_type", "assessment"),
        )
        decision = evaluate_evidence(
            evidence_input,
            confidence_threshold=settings.adaptive_semantic_confidence_threshold,
        )
        evidence = AssessmentEvidence(
            learner_id=learner_id,
            attempt_id=attempt_id,
            knowledge_point_id=knowledge_point_id,
            item_id=evidence_input.item_id,
            evidence_mode=evidence_input.evidence_mode,
            outcome_score=evidence_input.outcome_score,
            independent=evidence_input.independent,
            hint_count=evidence_input.hint_count,
            retry_count=evidence_input.retry_count,
            response_time_ms=evidence_input.response_time_ms,
            error_tags=evidence_input.error_tags,
            semantic_confidence=evidence_input.semantic_confidence,
            item_difficulty_prior=evidence_input.item_difficulty_prior,
            interaction_type=evidence_input.interaction_type,
            accepted=decision.accepted,
            updates_learning_state=decision.updates_learning_state,
            decision_reason=decision.reason,
            evidence_ref=evidence_input.evidence_ref,
        )
        self.db.add(evidence)
        await self.db.flush()
        if not decision.updates_learning_state:
            trace = DecisionTrace(
                learner_id=learner_id,
                attempt_id=attempt_id,
                knowledge_point_id=knowledge_point_id,
                evidence_id=evidence.id,
                status="blocked",
                reason=decision.reason,
                trace_payload={"semantic_confidence": evidence.semantic_confidence},
            )
            self.db.add(trace)
            await self.db.flush()
            return evidence, None
        return evidence, "accepted"

    async def _persist_adaptive_decision(
        self,
        *,
        signal: AttemptSignal,
        state: LearnerKnowledgeState,
        evidence: AssessmentEvidence,
        previous_score: float,
        irt_result,
        now: datetime,
    ) -> dict:
        refs = [ref.model_dump(mode="json") for ref in signal.evidence_refs]
        state_update = KnowledgeStateUpdate(
            learner_id=state.learner_id,
            attempt_id=evidence.attempt_id,
            evidence_id=evidence.id,
            knowledge_point_id=state.knowledge_point_id,
            previous_mastery=previous_score,
            new_mastery=irt_result.ability,
            predicted_success=irt_result.predicted_success,
            ability=irt_result.ability,
            item_difficulty=irt_result.item_difficulty,
            evidence_refs=refs,
            model_version=irt_result.model_version,
        )
        self.db.add(state_update)

        fsrs_result = await self.db.execute(
            select(FSRSReviewState).where(
                FSRSReviewState.learner_id == state.learner_id,
                FSRSReviewState.knowledge_point_id == state.knowledge_point_id,
            )
        )
        fsrs_row = fsrs_result.scalar_one_or_none()
        previous_fsrs = FSRSState(
            difficulty=fsrs_row.difficulty if fsrs_row else 5.0,
            stability_days=fsrs_row.stability_days if fsrs_row else 1.0,
            last_review_at=fsrs_row.last_review_at if fsrs_row else None,
            next_review_at=fsrs_row.next_review_at if fsrs_row else None,
            review_count=fsrs_row.review_count if fsrs_row else 0,
        )
        rating = infer_rating(
            correct=signal.correct,
            independent=evidence.independent,
            hint_count=evidence.hint_count,
            retry_count=evidence.retry_count,
            response_time_ms=evidence.response_time_ms,
            transfer=bool(signal.metadata.get("transfer")),
        )
        schedule = schedule_review(previous_fsrs, rating, now)
        if fsrs_row is None:
            fsrs_row = FSRSReviewState(
                learner_id=state.learner_id,
                knowledge_point_id=state.knowledge_point_id,
                last_evidence_id=evidence.id,
                difficulty=schedule.difficulty,
                stability_days=schedule.stability_days,
                retrievability=schedule.retrievability,
                last_rating=rating.name,
                review_count=schedule.review_count,
                last_review_at=schedule.last_review_at,
                next_review_at=schedule.next_review_at,
                model_version=schedule.model_version,
            )
            self.db.add(fsrs_row)
        else:
            fsrs_row.last_evidence_id = evidence.id
            fsrs_row.difficulty = schedule.difficulty
            fsrs_row.stability_days = schedule.stability_days
            fsrs_row.retrievability = schedule.retrievability
            fsrs_row.last_rating = rating.name
            fsrs_row.review_count = schedule.review_count
            fsrs_row.last_review_at = schedule.last_review_at
            fsrs_row.next_review_at = schedule.next_review_at
            fsrs_row.model_version = schedule.model_version

        dkt = None
        if settings.dkt_shadow_enabled or settings.dkt_policy_enabled:
            dkt = DKTShadowPredictor().predict(
                current_mastery=irt_result.ability,
                outcome_score=evidence.outcome_score,
            )
            state.dkt_shadow_prediction = dkt.predicted_success
            dkt_row = DKTShadowPrediction(
                learner_id=state.learner_id,
                knowledge_point_id=state.knowledge_point_id,
                evidence_id=evidence.id,
                predicted_success=dkt.predicted_success,
                confidence=dkt.confidence,
                model_version=dkt.model_version,
                input_event_refs=[evidence.evidence_ref],
                shadow_mode=not settings.dkt_policy_enabled or dkt.fallback_used,
                fallback_used=dkt.fallback_used,
                error=dkt.error,
            )
            self.db.add(dkt_row)
        policy = TeachingPolicyCompiler().compile(
            knowledge_point_id=str(state.knowledge_point_id),
            mastery=irt_result.ability,
            retrievability=schedule.retrievability,
            production=float(signal.metadata.get("production_score", 0.0)),
            dkt_prediction=dkt.predicted_success if dkt else None,
            dkt_enabled=settings.dkt_policy_enabled
            and dkt is not None
            and not dkt.fallback_used,
        )
        policy_row = TeachingPolicyDecision(
            learner_id=state.learner_id,
            knowledge_point_id=state.knowledge_point_id,
            attempt_id=evidence.attempt_id,
            evidence_id=evidence.id,
            policy=policy.model_dump(mode="json"),
            input_snapshot={
                "mastery": irt_result.ability,
                "retrievability": schedule.retrievability,
                "dkt_prediction": dkt.predicted_success if dkt else None,
            },
            compiler_version=policy.compiler_version,
            dkt_applied=settings.dkt_policy_enabled
            and dkt is not None
            and not dkt.fallback_used,
        )
        self.db.add(policy_row)
        await self.db.flush()
        trace = DecisionTrace(
            learner_id=state.learner_id,
            attempt_id=evidence.attempt_id,
            knowledge_point_id=state.knowledge_point_id,
            evidence_id=evidence.id,
            state_update_id=state_update.id,
            policy_decision_id=policy_row.id,
            status="applied",
            reason="assessment_evidence_applied",
            trace_payload={
                "evidence_ref": evidence.evidence_ref,
                "irt_model": irt_result.model_version,
                "fsrs_model": schedule.model_version,
                "fsrs_rating": rating.name,
                "dkt_model": dkt.model_version if dkt else None,
                "dkt_shadow": not settings.dkt_policy_enabled
                or dkt is None
                or dkt.fallback_used,
                "policy": policy.model_dump(mode="json"),
            },
        )
        self.db.add(trace)
        return {
            "evidence_id": str(evidence.id),
            "state_update_id": str(state_update.id),
            "policy_decision_id": str(policy_row.id),
            "fsrs_rating": rating.name,
            "fsrs_stability_days": schedule.stability_days,
            "fsrs_retrievability": schedule.retrievability,
            "next_review_at": schedule.next_review_at,
            "dkt_shadow_prediction": dkt.predicted_success if dkt else None,
            "dkt_fallback_used": dkt.fallback_used if dkt else False,
            "teaching_policy": policy.model_dump(mode="json"),
        }

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
        next_review_at = _next_review_at(self.clock.now(), signal.correct, new_score)
        if item is not None:
            item.confidence = new_score
            item.review_count = (item.review_count or 0) + 1
            item.last_reviewed_at = self.clock.now()
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
            dimension = _evidence_dimension(signal)
            setattr(vector, dimension, new_score)
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
        now = self.clock.now()
        dimension = _writing_dimension(signal)
        setattr(mastery, dimension, new_score)
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


def _evidence_dimension(signal: AttemptSignal) -> str:
    requested = str(signal.metadata.get("evidence_mode") or "recall")
    allowed = {"recognition", "recall", "spelling", "listening", "context_use", "production"}
    return requested if requested in allowed else "recall"


def _writing_dimension(signal: AttemptSignal) -> str:
    requested = _evidence_dimension(signal)
    return requested if requested in {"recognition", "recall", "context_use", "production"} else "production"
