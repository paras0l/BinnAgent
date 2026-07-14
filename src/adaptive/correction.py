import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adaptive.fsrs import FSRSSchedule, FSRSRating, FSRSState, infer_rating, schedule_review
from src.adaptive.irt import update_ability
from src.adaptive.policy import TeachingPolicyCompiler
from src.models.adaptive import (
    AssessmentEvidence,
    DecisionTrace,
    FSRSReviewState,
    KnowledgeStateUpdate,
    TeachingPolicyDecision,
)
from src.models.knowledge import LearnerKnowledgeState


@dataclass(frozen=True)
class CorrectionResult:
    evidence_id: uuid.UUID
    invalidated: bool
    replayed_evidence_count: int
    mastery: float
    next_review_at: datetime | None


class EvidenceCorrectionService:
    """Invalidate a disputed assessment and deterministically rebuild derived state."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def invalidate_and_recompute(
        self,
        evidence_id: uuid.UUID,
        *,
        reason: str,
        corrected_at: datetime | None = None,
    ) -> CorrectionResult:
        now = corrected_at or datetime.now(timezone.utc)
        result = await self.db.execute(
            select(AssessmentEvidence)
            .where(AssessmentEvidence.id == evidence_id)
            .with_for_update()
        )
        evidence = result.scalar_one_or_none()
        if evidence is None:
            raise ValueError("assessment evidence not found")
        if evidence.invalidated_at is None:
            evidence.invalidated_at = now
            evidence.invalidation_reason = reason.strip()[:500]

        state_result = await self.db.execute(
            select(LearnerKnowledgeState)
            .where(
                LearnerKnowledgeState.learner_id == evidence.learner_id,
                LearnerKnowledgeState.knowledge_point_id == evidence.knowledge_point_id,
            )
            .with_for_update()
        )
        state = state_result.scalar_one_or_none()
        valid_result = await self.db.execute(
            select(AssessmentEvidence)
            .where(
                AssessmentEvidence.learner_id == evidence.learner_id,
                AssessmentEvidence.knowledge_point_id == evidence.knowledge_point_id,
                AssessmentEvidence.updates_learning_state.is_(True),
                AssessmentEvidence.invalidated_at.is_(None),
            )
            .order_by(AssessmentEvidence.created_at.asc(), AssessmentEvidence.id.asc())
        )
        valid = list(valid_result.scalars().all())
        mastery, predicted, fsrs = replay_evidence(valid)

        if state is not None:
            state.mastery_score = mastery
            state.ability = mastery
            state.predicted_success = predicted
            state.exposure_count = len(valid)
            state.correct_count = sum(item.outcome_score >= 0.6 for item in valid)
            state.status = "mastered" if mastery >= 0.8 else "learning" if valid else "not_started"
            state.last_seen_at = valid[-1].created_at if valid else None
            state.next_review_at = fsrs.next_review_at if fsrs else None
            state.evidence_summary = {
                "recomputed_after_correction": True,
                "invalidated_evidence_id": str(evidence.id),
                "invalidation_reason": evidence.invalidation_reason,
                "active_evidence_refs": [item.evidence_ref for item in valid],
            }

        update_result = await self.db.execute(
            select(KnowledgeStateUpdate).where(KnowledgeStateUpdate.evidence_id == evidence.id)
        )
        invalid_update = update_result.scalar_one_or_none()
        if invalid_update is not None:
            invalid_update.evidence_refs = [
                *list(invalid_update.evidence_refs or []),
                {
                    "evidence_type": "assessment_correction",
                    "evidence_id": str(evidence.id),
                    "reason": evidence.invalidation_reason,
                },
            ]

        trace_result = await self.db.execute(
            select(DecisionTrace).where(DecisionTrace.evidence_id == evidence.id)
        )
        trace = trace_result.scalar_one_or_none()
        if trace is not None:
            trace.status = "invalidated"
            trace.reason = "learner_correction"
            trace.trace_payload = {
                **dict(trace.trace_payload or {}),
                "invalidated_at": now.isoformat(),
                "invalidation_reason": evidence.invalidation_reason,
                "replayed_evidence_count": len(valid),
            }

        fsrs_result = await self.db.execute(
            select(FSRSReviewState).where(
                FSRSReviewState.learner_id == evidence.learner_id,
                FSRSReviewState.knowledge_point_id == evidence.knowledge_point_id,
            )
        )
        fsrs_row = fsrs_result.scalar_one_or_none()
        if fsrs_row is not None and fsrs is None:
            await self.db.delete(fsrs_row)
        elif fsrs_row is not None and fsrs is not None:
            last = valid[-1]
            fsrs_row.last_evidence_id = last.id
            fsrs_row.difficulty = fsrs.difficulty
            fsrs_row.stability_days = fsrs.stability_days
            fsrs_row.retrievability = 1.0
            fsrs_row.last_rating = _rating_for(last).name
            fsrs_row.review_count = fsrs.review_count
            fsrs_row.last_review_at = fsrs.last_review_at
            fsrs_row.next_review_at = fsrs.next_review_at

        if valid:
            policy_result = await self.db.execute(
                select(TeachingPolicyDecision)
                .where(
                    TeachingPolicyDecision.learner_id == evidence.learner_id,
                    TeachingPolicyDecision.knowledge_point_id == evidence.knowledge_point_id,
                )
                .order_by(TeachingPolicyDecision.created_at.desc())
                .limit(1)
            )
            policy_row = policy_result.scalar_one_or_none()
            if policy_row is not None:
                policy = TeachingPolicyCompiler().compile(
                    knowledge_point_id=str(evidence.knowledge_point_id),
                    mastery=mastery,
                    retrievability=1.0 if fsrs else 0.0,
                )
                policy_row.policy = policy.model_dump(mode="json")
                policy_row.input_snapshot = {
                    "mastery": mastery,
                    "retrievability": 1.0 if fsrs else 0.0,
                    "recomputed_after_correction": True,
                }

        await self.db.flush()
        return CorrectionResult(
            evidence_id=evidence.id,
            invalidated=True,
            replayed_evidence_count=len(valid),
            mastery=mastery,
            next_review_at=fsrs.next_review_at if fsrs else None,
        )


def replay_evidence(
    evidence: list[AssessmentEvidence],
) -> tuple[float, float | None, FSRSSchedule | None]:
    mastery = 0.0
    predicted: float | None = None
    fsrs_state = FSRSState()
    schedule = None
    for item in evidence:
        irt = update_ability(
            mastery,
            outcome_score=item.outcome_score,
            item_difficulty=item.item_difficulty_prior,
            independent=item.independent,
            hint_count=item.hint_count,
            retry_count=item.retry_count,
        )
        mastery = irt.ability
        predicted = irt.predicted_success
        reviewed_at = item.created_at or datetime.now(timezone.utc)
        schedule = schedule_review(fsrs_state, _rating_for(item), reviewed_at)
        fsrs_state = FSRSState(
            difficulty=schedule.difficulty,
            stability_days=schedule.stability_days,
            last_review_at=schedule.last_review_at,
            next_review_at=schedule.next_review_at,
            review_count=schedule.review_count,
        )
    return mastery, predicted, schedule


def _rating_for(evidence: AssessmentEvidence) -> FSRSRating:
    return infer_rating(
        correct=evidence.outcome_score >= 0.6,
        independent=evidence.independent,
        hint_count=evidence.hint_count,
        retry_count=evidence.retry_count,
        response_time_ms=evidence.response_time_ms,
    )
