#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adaptive.dkt import DKTShadowPredictor
from src.adaptive.correction import EvidenceCorrectionService
from src.adaptive.evidence import AssessmentEvidenceInput, evaluate_evidence
from src.adaptive.fsrs import FSRSRating, FSRSState, retrievability, schedule_review
from src.adaptive.irt import predict_success, update_ability
from src.adaptive.policy import TeachingPolicyCompiler
from sqlalchemy import func, select

from src.db import async_session_factory
from src.mastery import AttemptSignal, MasteryEngine
from src.models import (
    CurriculumNode,
    ExerciseAttempt,
    ExerciseQuestion,
    KnowledgePoint,
    KnowledgeSource,
    Learner,
)
from src.models.adaptive import (
    AssessmentEvidence,
    DecisionTrace,
    DKTShadowPrediction,
    FSRSReviewState,
    KnowledgeStateUpdate,
    TeachingPolicyDecision,
)


def _evidence(**overrides) -> AssessmentEvidenceInput:
    data = {
        "knowledge_point_id": "grammar.article_usage",
        "item_id": "item-umbrella",
        "outcome_score": 1.0,
        "evidence_ref": "attempt-001",
    }
    data.update(overrides)
    return AssessmentEvidenceInput(**data)


def validations(database_checks: dict[str, bool]) -> list[tuple[str, callable]]:
    t0 = datetime(2026, 7, 14, 10, tzinfo=timezone.utc)
    compiler = TeachingPolicyCompiler()
    independent = update_ability(0.4, outcome_score=1, item_difficulty=0.5, independent=True)
    hinted = update_ability(
        0.4,
        outcome_score=1,
        item_difficulty=0.5,
        independent=False,
        hint_count=1,
    )
    state = FSRSState(stability_days=2, last_review_at=t0, review_count=1)
    again = schedule_review(state, FSRSRating.AGAIN, t0)
    hard = schedule_review(state, FSRSRating.HARD, t0)
    good = schedule_review(state, FSRSRating.GOOD, t0)
    shadow = DKTShadowPredictor().predict(current_mastery=0.5, outcome_score=1)
    low = compiler.compile(
        knowledge_point_id="grammar.article_usage", mastery=0.25, retrievability=0.41
    )
    high = compiler.compile(
        knowledge_point_id="grammar.article_usage",
        mastery=0.87,
        retrievability=0.69,
        production=0.81,
    )
    return [
        ("evidence_independent_correct", lambda: independent.ability > 0.4),
        ("evidence_hint_correct", lambda: 0.4 < hinted.ability < independent.ability),
        (
            "low_confidence_no_update",
            lambda: not evaluate_evidence(_evidence(semantic_confidence=0.3)).updates_learning_state,
        ),
        ("browsing_does_not_update", lambda: database_checks["browsing"]),
        (
            "irt_monotonicity",
            lambda: predict_success(0.8, 0.5) > predict_success(0.2, 0.5)
            and predict_success(0.5, 0.8) < predict_success(0.5, 0.2),
        ),
        (
            "fsrs_time_travel",
            lambda: again.next_review_at < hard.next_review_at < good.next_review_at
            and retrievability(state, t0 + timedelta(days=7))
            < retrievability(state, t0 + timedelta(days=1)),
        ),
        ("dkt_shadow_prediction", lambda: shadow.fallback_used and 0 <= shadow.predicted_success <= 1),
        ("prompt_policy_low_mastery", lambda: low.support_level == "guided" and low.max_new_concepts == 1),
        ("prompt_policy_high_mastery", lambda: high.practice_form == "novel_transfer" and high.support_level == "minimal"),
        ("duplicate_attempt_idempotency", lambda: database_checks["duplicate"]),
        ("model_failure_blocks_write", lambda: database_checks["blocked_write"]),
        ("evidence_trace_complete", lambda: database_checks["trace_complete"]),
    ]


async def _database_validations() -> dict[str, bool]:
    async with async_session_factory() as db:
        transaction = await db.begin()
        try:
            learner = Learner(nickname="adaptive-validation")
            source = KnowledgeSource(
                owner_learner_id=None,
                title="Adaptive validation source",
                filename="adaptive-validation.txt",
                grade="validation",
                status="published",
                visibility="private",
                sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                file_size=1,
                unit_count=1,
                knowledge_count=1,
            )
            db.add_all([learner, source])
            await db.flush()
            source.owner_learner_id = learner.id
            node = CurriculumNode(
                source_id=source.id,
                node_type="unit",
                title="Validation unit",
                ordinal=1,
                learning_objectives=[],
            )
            db.add(node)
            await db.flush()
            point = KnowledgePoint(
                source_id=source.id,
                curriculum_node_id=node.id,
                canonical_key=f"validation.article_usage.{uuid.uuid4()}",
                type="grammar",
                title="Article usage",
                summary="Choose a or an.",
                source_page="1",
                difficulty=0.5,
                status="published",
            )
            db.add(point)
            await db.flush()
            question = ExerciseQuestion(
                source_id=source.id,
                curriculum_node_id=node.id,
                knowledge_point_id=point.id,
                question_type="fill_blank",
                stem="I bought ___ umbrella yesterday.",
                options=[],
                answer="an",
                explanation="Use an before a vowel sound.",
                difficulty=0.5,
                difficulty_prior=0.5,
                difficulty_model_version="irt-prior-v1",
                status="published",
            )
            db.add(question)
            await db.flush()

            attempt = _attempt(learner.id, question, "an", True)
            db.add(attempt)
            await db.flush()
            signal = _signal(learner.id, point.id, question, attempt, confidence=1.0)
            engine = MasteryEngine(db)
            first = await engine.update_from_attempt(signal)
            await db.flush()
            first_count = await _count(db, KnowledgeStateUpdate, learner.id)
            replay = await engine.update_from_attempt(signal)
            await db.flush()
            replay_count = await _count(db, KnowledgeStateUpdate, learner.id)

            blocked_attempt = _attempt(learner.id, question, "unclear", False)
            db.add(blocked_attempt)
            await db.flush()
            before_blocked = await _count(db, KnowledgeStateUpdate, learner.id)
            blocked = await engine.update_from_attempt(
                _signal(learner.id, point.id, question, blocked_attempt, confidence=0.2)
            )
            await db.flush()
            after_blocked = await _count(db, KnowledgeStateUpdate, learner.id)

            browsing_attempt = _attempt(learner.id, question, "viewed explanation", False)
            db.add(browsing_attempt)
            await db.flush()
            evidence_before_browsing = await _count(db, AssessmentEvidence, learner.id)
            browsing_signal = _signal(
                learner.id, point.id, question, browsing_attempt, confidence=1.0
            )
            browsing_signal.metadata["interaction_type"] = "browsing"
            browsing = await engine.update_from_attempt(browsing_signal)
            await db.flush()
            evidence_after_browsing = await _count(db, AssessmentEvidence, learner.id)

            evidence_id = uuid.UUID(first.metadata["evidence_id"])
            trace_counts = [
                await _count_for_evidence(db, model, evidence_id)
                for model in (
                    KnowledgeStateUpdate,
                    DKTShadowPrediction,
                    TeachingPolicyDecision,
                    DecisionTrace,
                )
            ]
            fsrs_count = await _count(db, FSRSReviewState, learner.id)
            correction = await EvidenceCorrectionService(db).invalidate_and_recompute(
                evidence_id,
                reason="learner corrected the system grade",
                corrected_at=datetime(2026, 7, 14, 12, tzinfo=timezone.utc),
            )
            corrected_trace = (
                await db.execute(select(DecisionTrace).where(DecisionTrace.evidence_id == evidence_id))
            ).scalar_one()
            corrected_fsrs_count = await _count(db, FSRSReviewState, learner.id)
            return {
                "duplicate": first_count == replay_count == 1
                and replay.metadata.get("idempotent_replay") is True
                and replay.new_score == first.new_score,
                "blocked_write": before_blocked == after_blocked
                and blocked.metadata.get("update_blocked") is True,
                "browsing": evidence_before_browsing == evidence_after_browsing
                and browsing.metadata.get("assessment_evidence_created") is False,
                "trace_complete": trace_counts == [1, 1, 1, 1]
                and fsrs_count == 1
                and first.metadata.get("policy_decision_id") is not None
                and correction.replayed_evidence_count == 0
                and correction.mastery == 0.0
                and corrected_trace.status == "invalidated"
                and corrected_fsrs_count == 0,
            }
        finally:
            await transaction.rollback()


def _attempt(
    learner_id: uuid.UUID,
    question: ExerciseQuestion,
    answer: str,
    correct: bool,
) -> ExerciseAttempt:
    return ExerciseAttempt(
        learner_id=learner_id,
        question_id=question.id,
        submitted_answer=answer,
        correct=correct,
        response_time_ms=5000,
        exercise_id=str(question.id),
        target_type="curriculum_node",
        target_id=str(question.curriculum_node_id),
        target_label="adaptive validation",
        answer=answer,
        result="correct" if correct else "incorrect",
        metadata_={},
        source_context={},
        should_update_mastery=True,
        should_create_error_pattern=not correct,
        should_create_memory_evidence=True,
        created_at=datetime.now(timezone.utc),
    )


def _signal(
    learner_id: uuid.UUID,
    point_id: uuid.UUID,
    question: ExerciseQuestion,
    attempt: ExerciseAttempt,
    *,
    confidence: float,
) -> AttemptSignal:
    return AttemptSignal(
        learner_id=str(learner_id),
        target_type="knowledge_point",
        target_id=str(point_id),
        correct=attempt.correct,
        score=1.0 if attempt.correct else 0.0,
        response_time_ms=attempt.response_time_ms,
        source="adaptive.validation",
        metadata={
            "attempt_id": str(attempt.id),
            "question_id": str(question.id),
            "item_difficulty_prior": question.difficulty_prior,
            "semantic_confidence": confidence,
            "interaction_type": "assessment",
        },
    )


async def _count(db, model, learner_id: uuid.UUID) -> int:
    return int(
        (await db.execute(select(func.count(model.id)).where(model.learner_id == learner_id)))
        .scalar_one()
    )


async def _count_for_evidence(db, model, evidence_id: uuid.UUID) -> int:
    return int(
        (await db.execute(select(func.count(model.id)).where(model.evidence_id == evidence_id)))
        .scalar_one()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the adaptive learning core")
    parser.add_argument("--all", action="store_true", help="run every validation")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = parser.parse_args()
    failed = 0
    try:
        database_checks = asyncio.run(_database_validations())
    except Exception as exc:
        print(f"Database validation setup failed: {exc}", file=sys.stderr)
        database_checks = {
            "duplicate": False,
            "blocked_write": False,
            "browsing": False,
            "trace_complete": False,
        }
    checks = validations(database_checks)
    results = []
    for name, check in checks:
        try:
            passed = bool(check())
        except Exception:
            passed = False
        results.append({"name": name, "passed": passed})
        if not args.json:
            print(f"{'PASS' if passed else 'FAIL'} {name}")
        failed += int(not passed)
    if args.json:
        print(
            json.dumps(
                {
                    "status": "passed" if failed == 0 else "failed",
                    "passed": len(checks) - failed,
                    "failed": failed,
                    "checks": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"\n{len(checks) - failed} passed, {failed} failed")
    return int(failed > 0)


if __name__ == "__main__":
    sys.exit(main())
