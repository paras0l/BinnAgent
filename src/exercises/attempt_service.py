import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge import ExerciseAttempt, ExerciseQuestion

ExerciseTargetType = Literal[
    "curriculum_node",
    "grammar_topic",
    "vocabulary_item",
    "vocabulary",
    "word_part",
    "reading_passage",
    "writing_phrase",
    "pronunciation_item",
]
ExerciseAttemptResult = Literal["correct", "incorrect"]
ExerciseLearningStatus = Literal["mastered", "needs_review", "unstable", "not_started"]


@dataclass(frozen=True)
class ExerciseTarget:
    type: ExerciseTargetType
    id: str
    label: str


@dataclass(frozen=True)
class ExerciseAttemptCreate:
    exercise_id: str
    target: ExerciseTarget
    answer: str
    result: ExerciseAttemptResult
    attempt_id: uuid.UUID | None = None
    client_attempt_id: str | None = None
    question_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    response_time_ms: int | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_context: dict[str, Any] = field(default_factory=dict)
    should_update_mastery: bool = True
    should_create_error_pattern: bool = False
    should_create_memory_evidence: bool = True


@dataclass(frozen=True)
class ExerciseAttemptSummary:
    total: int
    correct: int
    incorrect: int
    accuracy: int
    last_attempt_at: datetime | None
    last_result: ExerciseAttemptResult | None
    needs_review: bool
    learning_status: ExerciseLearningStatus


class ExerciseAttemptService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_attempt(
        self,
        learner_id: uuid.UUID,
        payload: ExerciseAttemptCreate,
    ) -> ExerciseAttempt:
        metadata = dict(payload.metadata)
        if payload.client_attempt_id:
            metadata.setdefault("client_attempt_id", payload.client_attempt_id)

        attempt = ExerciseAttempt(
            learner_id=learner_id,
            question_id=payload.question_id,
            session_id=payload.session_id,
            submitted_answer=payload.answer.strip(),
            correct=payload.result == "correct",
            response_time_ms=payload.response_time_ms,
            exercise_id=payload.exercise_id.strip(),
            target_type=payload.target.type,
            target_id=payload.target.id.strip(),
            target_label=payload.target.label.strip(),
            answer=payload.answer.strip(),
            result=payload.result,
            metadata_=metadata,
            source_context=dict(payload.source_context),
            should_update_mastery=payload.should_update_mastery,
            should_create_error_pattern=payload.should_create_error_pattern,
            should_create_memory_evidence=payload.should_create_memory_evidence,
            created_at=payload.created_at or datetime.now(timezone.utc),
        )
        if payload.attempt_id is not None:
            attempt.id = payload.attempt_id
        self.db.add(attempt)
        await self.db.flush()
        if getattr(attempt, "id", None) is None:
            attempt.id = uuid.uuid4()
        if getattr(attempt, "created_at", None) is None:
            attempt.created_at = payload.created_at or datetime.now(timezone.utc)
        return attempt

    async def save_knowledge_question_attempt(
        self,
        learner_id: uuid.UUID,
        question: ExerciseQuestion,
        answer: str,
        correct: bool,
        session_id: uuid.UUID | None = None,
        response_time_ms: int | None = None,
        target_label: str | None = None,
        metadata: dict[str, Any] | None = None,
        source_context: dict[str, Any] | None = None,
    ) -> ExerciseAttempt:
        payload = ExerciseAttemptCreate(
            exercise_id=str(question.id),
            target=ExerciseTarget(
                type="curriculum_node",
                id=str(question.curriculum_node_id),
                label=target_label or "课程知识库练习",
            ),
            answer=answer,
            result="correct" if correct else "incorrect",
            question_id=question.id,
            session_id=session_id,
            response_time_ms=response_time_ms,
            metadata={
                "question_id": str(question.id),
                "question_type": question.question_type,
                "knowledge_point_id": (
                    str(question.knowledge_point_id) if question.knowledge_point_id else None
                ),
                **(metadata or {}),
            },
            source_context={
                "source": "knowledge_base",
                "question_id": str(question.id),
                "curriculum_node_id": str(question.curriculum_node_id),
                **(source_context or {}),
            },
            should_update_mastery=True,
            should_create_error_pattern=not correct,
            should_create_memory_evidence=True,
        )
        return await self.save_attempt(learner_id, payload)

    async def list_attempts(
        self,
        learner_id: uuid.UUID,
        target_type: ExerciseTargetType | None = None,
        target_id: str | None = None,
    ) -> list[ExerciseAttempt]:
        query = select(ExerciseAttempt).where(ExerciseAttempt.learner_id == learner_id)
        if target_type is not None:
            query = query.where(ExerciseAttempt.target_type == target_type)
        if target_id is not None:
            query = query.where(ExerciseAttempt.target_id == target_id.strip())
        query = query.order_by(ExerciseAttempt.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_summary(
        self,
        learner_id: uuid.UUID,
        target_type: ExerciseTargetType | None = None,
        target_id: str | None = None,
    ) -> ExerciseAttemptSummary:
        attempts = await self.list_attempts(learner_id, target_type, target_id)
        return build_exercise_attempt_summary(attempts)

def build_exercise_attempt_summary(attempts: list[ExerciseAttempt]) -> ExerciseAttemptSummary:
    ordered_attempts = sorted(attempts, key=_attempt_created_at, reverse=True)
    total = len(ordered_attempts)
    correct = sum(1 for attempt in ordered_attempts if _attempt_result(attempt) == "correct")
    incorrect = total - correct
    accuracy = round((correct / total) * 100) if total > 0 else 0
    last_attempt = ordered_attempts[0] if ordered_attempts else None
    last_result = _attempt_result(last_attempt) if last_attempt is not None else None

    return ExerciseAttemptSummary(
        total=total,
        correct=correct,
        incorrect=incorrect,
        accuracy=accuracy,
        last_attempt_at=last_attempt.created_at if last_attempt is not None else None,
        last_result=last_result,
        needs_review=total > 0 and (last_result == "incorrect" or accuracy < 70),
        learning_status=_learning_status(total, accuracy, last_result),
    )


def _learning_status(
    total: int,
    accuracy: int,
    last_result: ExerciseAttemptResult | None,
) -> ExerciseLearningStatus:
    if total == 0:
        return "not_started"
    if last_result == "incorrect":
        return "needs_review"
    if accuracy >= 80 and last_result == "correct":
        return "mastered"
    return "unstable"


def _attempt_result(attempt: ExerciseAttempt) -> ExerciseAttemptResult:
    if attempt.result in ("correct", "incorrect"):
        return attempt.result
    return "correct" if attempt.correct else "incorrect"


def _attempt_created_at(attempt: ExerciseAttempt) -> datetime:
    return attempt.created_at or datetime.min.replace(tzinfo=timezone.utc)
