import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.extraction import extract_writing_phrase_candidates
from src.memory.curator import MemoryCurator
from src.memory.explainer import MemoryExplainer
from src.memory.retriever import MemoryRetriever
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter
from src.models.learner import Learner
from src.models.writing_phrase import (
    WritingPhrase,
    WritingPhraseAttempt,
    WritingPhraseExercise,
)

router = APIRouter(
    prefix="/api/learners/{learner_id}/writing-phrases",
    tags=["writing-phrases"],
)

ExerciseType = Literal["recognition", "blank", "replacement"]


class PhraseExample(BaseModel):
    sentence: str
    translation: str | None = None


class WritingPhraseBase(BaseModel):
    text: str = Field(min_length=1)
    chinese_meaning: str | None = None
    explanation: str | None = None
    usage_scene: str | None = None
    usage_position: str | None = None
    tags: list[str] = Field(default_factory=list)
    examples: list[PhraseExample | dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    source_type: str = "manual"
    source_ref: str | None = None
    source_raw_text: str | None = None
    register_level: str | None = None
    difficulty: int = Field(default=2, ge=1, le=5)
    is_favorite: bool = False
    is_archived: bool = False
    review_enabled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be blank")
        return stripped

    @field_validator("tags", "notes", "mistakes")
    @classmethod
    def clean_string_list(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned


class CreateWritingPhraseRequest(WritingPhraseBase):
    pass


class UpdateWritingPhraseRequest(BaseModel):
    text: str | None = None
    chinese_meaning: str | None = None
    explanation: str | None = None
    usage_scene: str | None = None
    usage_position: str | None = None
    tags: list[str] | None = None
    examples: list[PhraseExample | dict[str, Any]] | None = None
    notes: list[str] | None = None
    mistakes: list[str] | None = None
    source_type: str | None = None
    source_ref: str | None = None
    source_raw_text: str | None = None
    register_level: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    is_favorite: bool | None = None
    is_archived: bool | None = None
    review_enabled: bool | None = None
    metadata: dict[str, Any] | None = None


class WritingPhraseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    learner_id: uuid.UUID
    text: str
    normalized_text: str
    chinese_meaning: str | None = None
    explanation: str | None = None
    usage_scene: str | None = None
    usage_position: str | None = None
    tags: list[str]
    examples: list[dict[str, Any]]
    notes: list[str]
    mistakes: list[str]
    source_type: str
    source_ref: str | None = None
    source_raw_text: str | None = None
    register_level: str | None = None
    difficulty: int
    is_favorite: bool
    is_archived: bool
    review_enabled: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ImportWritingPhrasesRequest(BaseModel):
    source: str = "external_model"
    raw_text: str = Field(min_length=1)
    topic: str | None = None
    import_mode: Literal["extract_phrases"] = "extract_phrases"


class WritingPhraseCandidate(BaseModel):
    text: str
    chinese_meaning: str | None = None
    usage_scene: str | None = None
    usage_position: str | None = None
    tags: list[str] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    usage_notes: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    quality_score: float = Field(default=0.7, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    parse_mode: str = "regex_fallback"
    confidence: float = Field(default=0.7, ge=0, le=1)


class ImportWritingPhrasesResponse(BaseModel):
    candidates: list[WritingPhraseCandidate]
    parse_mode: str = "regex_fallback"
    warnings: list[str] = Field(default_factory=list)
    repair_used: bool = False
    confidence: float = Field(default=0.7, ge=0, le=1)


class ExerciseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phrase_id: uuid.UUID
    exercise_type: str
    prompt: str
    answer: str
    options: list[str]
    explanation: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class GenerateExercisesRequest(BaseModel):
    exercise_types: list[ExerciseType] = Field(
        default_factory=lambda: ["recognition", "blank", "replacement"]
    )


class AttemptRequest(BaseModel):
    exercise_id: uuid.UUID | None = None
    exercise_type: str = Field(min_length=1, max_length=30)
    answer: str | None = None
    expected_answer: str | None = None
    is_correct: bool | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    feedback: str | None = None
    response_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class AttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phrase_id: uuid.UUID
    exercise_id: uuid.UUID | None = None
    exercise_type: str
    answer: str | None = None
    expected_answer: str | None = None
    is_correct: bool
    score: float
    feedback: str | None = None
    response_time_ms: int | None = None
    occurred_at: datetime


class PhraseRecommendationResponse(BaseModel):
    recommendation_reason: str
    memory_items: list[dict[str, Any]]


async def _ensure_learner(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


def _examples_for_storage(examples: list[PhraseExample | dict[str, Any]]) -> list[dict[str, Any]]:
    stored: list[dict[str, Any]] = []
    for example in examples:
        if isinstance(example, PhraseExample):
            data = example.model_dump(exclude_none=True)
        else:
            data = {
                key: value
                for key, value in example.items()
                if key in {"sentence", "translation"} and value
            }
        if data.get("sentence"):
            stored.append(data)
    return stored


def _phrase_response(phrase: WritingPhrase) -> WritingPhraseResponse:
    return WritingPhraseResponse(
        id=phrase.id,
        learner_id=phrase.learner_id,
        text=phrase.text,
        normalized_text=phrase.normalized_text,
        chinese_meaning=phrase.chinese_meaning,
        explanation=phrase.explanation,
        usage_scene=phrase.usage_scene,
        usage_position=phrase.usage_position,
        tags=phrase.tags or [],
        examples=phrase.examples or [],
        notes=phrase.notes or [],
        mistakes=phrase.mistakes or [],
        source_type=phrase.source_type,
        source_ref=phrase.source_ref,
        source_raw_text=phrase.source_raw_text,
        register_level=phrase.register_level,
        difficulty=phrase.difficulty,
        is_favorite=phrase.is_favorite,
        is_archived=phrase.is_archived,
        review_enabled=phrase.review_enabled,
        metadata=phrase.metadata_ or {},
        created_at=phrase.created_at,
        updated_at=phrase.updated_at,
    )


async def _get_phrase(
    db: AsyncSession, learner_id: uuid.UUID, phrase_id: uuid.UUID
) -> WritingPhrase:
    result = await db.execute(
        select(WritingPhrase).where(
            WritingPhrase.id == phrase_id,
            WritingPhrase.learner_id == learner_id,
        )
    )
    phrase = result.scalar_one_or_none()
    if phrase is None:
        raise HTTPException(status_code=404, detail="Writing phrase not found")
    return phrase


def _field(block: str, names: tuple[str, ...]) -> str | None:
    joined = "|".join(re.escape(name) for name in names)
    prefix = r"(?:[-*]\s*|\d+[.)、]\s*)?"
    pattern = rf"(?:^|\n)\s*{prefix}(?:{joined})\s*[:：]\s*(.+?)(?=\n\s*{prefix}(?:[\u4e00-\u9fa5A-Za-z ]{{2,18}})\s*[:：]|\Z)"
    match = re.search(pattern, block, flags=re.S)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip(" -*\n")


def _split_import_blocks(raw_text: str) -> list[str]:
    normalized = raw_text.replace("\r\n", "\n").strip()
    blocks = re.split(r"\n(?=\s*(?:\d+[.)、]|[-*]\s*(?:英文句式|原句|句式|表达)))", normalized)
    if len(blocks) <= 1:
        blocks = re.split(r"\n{2,}", normalized)
    return [block.strip() for block in blocks if block.strip()]


def _infer_tags(block: str, topic: str | None) -> list[str]:
    tags: list[str] = []
    tag_text = _field(block, ("标签", "句式功能", "功能"))
    if tag_text:
        tags.extend(re.split(r"[/,，、\s]+", tag_text))
    if topic:
        tags.append(topic)
    cleaned: list[str] = []
    for tag in tags:
        value = tag.strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned[:6]


def _parse_candidates(raw_text: str, topic: str | None) -> ImportWritingPhrasesResponse:
    result = extract_writing_phrase_candidates(raw_text, topic)
    return ImportWritingPhrasesResponse(
        candidates=[
            WritingPhraseCandidate(
                text=candidate.text,
                chinese_meaning=candidate.chinese_meaning,
                usage_scene=candidate.usage_scene,
                usage_position=candidate.usage_position,
                tags=candidate.tags,
                examples=candidate.examples,
                usage_notes=candidate.usage_notes,
                mistakes=candidate.mistakes,
                quality_score=candidate.quality_score,
                warnings=candidate.warnings,
                parse_mode=candidate.parse_mode,
                confidence=candidate.confidence,
            )
            for candidate in result.candidates
        ],
        parse_mode=result.parse_mode,
        warnings=result.warnings,
        repair_used=result.repair_used,
        confidence=result.confidence,
    )


def _blank_answer(text: str) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    return " ".join(words[: min(4, len(words))]) if words else text


def _build_exercise(phrase: WritingPhrase, exercise_type: str) -> dict[str, Any]:
    first_example = phrase.examples[0]["sentence"] if phrase.examples else phrase.text
    if exercise_type == "recognition":
        answer = phrase.usage_scene or phrase.chinese_meaning or "用于对应写作场景中自然表达观点。"
        return {
            "prompt": f"{phrase.text}\n最适合用于什么写作场景？",
            "answer": answer,
            "options": [
                answer,
                "总结全文",
                "描述图表数据",
                "举例说明一个具体案例",
            ],
            "explanation": phrase.explanation or phrase.usage_scene,
        }
    if exercise_type == "blank":
        answer = _blank_answer(phrase.text)
        prompt = re.sub(re.escape(answer), "_____", first_example, count=1, flags=re.IGNORECASE)
        if prompt == first_example:
            prompt = f"请补全句式开头：_____ {first_example}"
        return {
            "prompt": prompt,
            "answer": answer,
            "options": [],
            "explanation": phrase.chinese_meaning,
        }
    return {
        "prompt": f"把低级表达 Also/First 替换成更自然表达，并围绕这个句式造句：\n{phrase.text}",
        "answer": phrase.text,
        "options": [],
        "explanation": phrase.usage_scene or phrase.chinese_meaning,
    }


@router.get("", response_model=list[WritingPhraseResponse])
async def list_writing_phrases(
    learner_id: uuid.UUID,
    q: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    db: AsyncSession = Depends(get_db_session),
) -> list[WritingPhraseResponse]:
    await _ensure_learner(db, learner_id)
    query = select(WritingPhrase).where(WritingPhrase.learner_id == learner_id)
    if not include_archived:
        query = query.where(WritingPhrase.is_archived.is_(False))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                WritingPhrase.text.ilike(pattern),
                WritingPhrase.chinese_meaning.ilike(pattern),
                WritingPhrase.usage_scene.ilike(pattern),
            )
        )
    if tag:
        query = query.where(WritingPhrase.tags.contains([tag.strip()]))
    query = query.order_by(
        WritingPhrase.is_favorite.desc(),
        WritingPhrase.review_enabled.desc(),
        WritingPhrase.updated_at.desc(),
    )
    result = await db.execute(query)
    return [_phrase_response(phrase) for phrase in result.scalars().all()]


@router.get("/recommendations", response_model=PhraseRecommendationResponse)
async def writing_phrase_recommendations(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> PhraseRecommendationResponse:
    await _ensure_learner(db, learner_id)
    try:
        context = await MemoryRetriever(db).for_writing_phrasebook(
            learner_id=learner_id,
            limit=5,
        )
        memory_items = context.loaded_items
    except Exception:
        memory_items = []
    return PhraseRecommendationResponse(
        recommendation_reason=MemoryExplainer().recommendation_reason(
            memory_items,
            "根据收藏句式、最近句式练习和写作弱点推荐下一组表达。",
        ),
        memory_items=[
            {
                "id": item.id,
                "type": item.type,
                "summary": item.summary,
                "confidence": item.confidence,
                "evidence": item.evidence_refs,
            }
            for item in memory_items
        ],
    )


@router.post("", response_model=WritingPhraseResponse, status_code=status.HTTP_201_CREATED)
async def create_writing_phrase(
    learner_id: uuid.UUID,
    body: CreateWritingPhraseRequest,
    db: AsyncSession = Depends(get_db_session),
) -> WritingPhraseResponse:
    await _ensure_learner(db, learner_id)
    phrase = WritingPhrase(
        learner_id=learner_id,
        text=body.text,
        normalized_text=_normalize_text(body.text),
        chinese_meaning=body.chinese_meaning,
        explanation=body.explanation,
        usage_scene=body.usage_scene,
        usage_position=body.usage_position,
        tags=body.tags,
        examples=_examples_for_storage(body.examples),
        notes=body.notes,
        mistakes=body.mistakes,
        source_type=body.source_type,
        source_ref=body.source_ref,
        source_raw_text=body.source_raw_text,
        register_level=body.register_level,
        difficulty=body.difficulty,
        is_favorite=body.is_favorite,
        is_archived=body.is_archived,
        review_enabled=body.review_enabled,
        metadata_=body.metadata,
    )
    db.add(phrase)
    await db.flush()
    await MemoryWriter(db).record_event(
        MemoryEventInput(
            learner_id=learner_id,
            event_type="writing_phrase_saved",
            skill="writing",
            subskill=body.tags[0] if body.tags else body.usage_position,
            source_type="writing_phrase",
            source_id=str(phrase.id),
            payload={
                "phrase_id": str(phrase.id),
                "text": phrase.text,
                "tags": phrase.tags,
                "usage_scene": phrase.usage_scene,
                "review_enabled": phrase.review_enabled,
            },
            confidence=1.0,
            created_by="user",
        )
    )
    await db.refresh(phrase)
    return _phrase_response(phrase)


@router.post("/import", response_model=ImportWritingPhrasesResponse)
async def import_writing_phrases(
    learner_id: uuid.UUID,
    body: ImportWritingPhrasesRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ImportWritingPhrasesResponse:
    await _ensure_learner(db, learner_id)
    return _parse_candidates(body.raw_text, body.topic)


@router.get("/{phrase_id}", response_model=WritingPhraseResponse)
async def get_writing_phrase(
    learner_id: uuid.UUID,
    phrase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> WritingPhraseResponse:
    await _ensure_learner(db, learner_id)
    return _phrase_response(await _get_phrase(db, learner_id, phrase_id))


@router.patch("/{phrase_id}", response_model=WritingPhraseResponse)
async def update_writing_phrase(
    learner_id: uuid.UUID,
    phrase_id: uuid.UUID,
    body: UpdateWritingPhraseRequest,
    db: AsyncSession = Depends(get_db_session),
) -> WritingPhraseResponse:
    await _ensure_learner(db, learner_id)
    phrase = await _get_phrase(db, learner_id, phrase_id)
    updates = body.model_dump(exclude_unset=True)
    if "text" in updates and updates["text"] is not None:
        phrase.text = updates["text"].strip()
        phrase.normalized_text = _normalize_text(phrase.text)
        updates.pop("text")
    if "examples" in updates and updates["examples"] is not None:
        phrase.examples = _examples_for_storage(updates.pop("examples"))
    if "metadata" in updates:
        phrase.metadata_ = updates.pop("metadata") or {}
    for key, value in updates.items():
        setattr(phrase, key, value)
    await db.flush()
    await MemoryWriter(db).record_user_control_event(
        learner_id=learner_id,
        operation_type="edit",
        target_type="writing_phrase",
        target_id=phrase.id,
        before={},
        after={
            "skill": "writing",
            "phrase_id": str(phrase.id),
            "updated_fields": sorted(updates.keys()),
        },
    )
    await MemoryWriter(db).record_event(
        MemoryEventInput(
            learner_id=learner_id,
            event_type="writing_phrase_updated",
            skill="writing",
            subskill=phrase.tags[0] if phrase.tags else phrase.usage_position,
            source_type="writing_phrase",
            source_id=str(phrase.id),
            payload={"phrase_id": str(phrase.id), "updated_fields": sorted(updates.keys())},
            confidence=1.0,
            created_by="user",
        )
    )
    await db.refresh(phrase)
    return _phrase_response(phrase)


@router.delete("/{phrase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_writing_phrase(
    learner_id: uuid.UUID,
    phrase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await _ensure_learner(db, learner_id)
    phrase = await _get_phrase(db, learner_id, phrase_id)
    await MemoryWriter(db).record_user_control_event(
        learner_id=learner_id,
        operation_type="delete",
        target_type="writing_phrase",
        target_id=phrase.id,
        before={"skill": "writing", "phrase_id": str(phrase.id), "text": phrase.text},
        reason="User deleted writing phrase",
    )
    await MemoryWriter(db).record_event(
        MemoryEventInput(
            learner_id=learner_id,
            event_type="writing_phrase_deleted",
            skill="writing",
            source_type="writing_phrase",
            source_id=str(phrase.id),
            payload={"phrase_id": str(phrase.id), "text": phrase.text},
            confidence=1.0,
            created_by="user",
        )
    )
    await db.delete(phrase)
    await db.flush()


@router.post("/{phrase_id}/exercises", response_model=list[ExerciseResponse])
async def generate_phrase_exercises(
    learner_id: uuid.UUID,
    phrase_id: uuid.UUID,
    body: GenerateExercisesRequest,
    db: AsyncSession = Depends(get_db_session),
) -> list[ExerciseResponse]:
    await _ensure_learner(db, learner_id)
    phrase = await _get_phrase(db, learner_id, phrase_id)
    exercises: list[WritingPhraseExercise] = []
    for exercise_type in body.exercise_types:
        payload = _build_exercise(phrase, exercise_type)
        exercise = WritingPhraseExercise(
            learner_id=learner_id,
            phrase_id=phrase.id,
            exercise_type=exercise_type,
            prompt=payload["prompt"],
            answer=payload["answer"],
            options=payload["options"],
            explanation=payload["explanation"],
            metadata_={},
        )
        db.add(exercise)
        exercises.append(exercise)
    await db.flush()
    for exercise in exercises:
        await db.refresh(exercise)
    return [
        ExerciseResponse(
            id=exercise.id,
            phrase_id=exercise.phrase_id,
            exercise_type=exercise.exercise_type,
            prompt=exercise.prompt,
            answer=exercise.answer,
            options=exercise.options or [],
            explanation=exercise.explanation,
            metadata=exercise.metadata_ or {},
            created_at=exercise.created_at,
        )
        for exercise in exercises
    ]


@router.post("/{phrase_id}/attempts", response_model=AttemptResponse, status_code=201)
async def record_phrase_attempt(
    learner_id: uuid.UUID,
    phrase_id: uuid.UUID,
    body: AttemptRequest,
    db: AsyncSession = Depends(get_db_session),
) -> AttemptResponse:
    await _ensure_learner(db, learner_id)
    phrase = await _get_phrase(db, learner_id, phrase_id)
    expected = body.expected_answer
    if body.exercise_id:
        result = await db.execute(
            select(WritingPhraseExercise).where(
                WritingPhraseExercise.id == body.exercise_id,
                WritingPhraseExercise.learner_id == learner_id,
                WritingPhraseExercise.phrase_id == phrase.id,
            )
        )
        exercise = result.scalar_one_or_none()
        if exercise is None:
            raise HTTPException(status_code=404, detail="Writing phrase exercise not found")
        expected = expected or exercise.answer
    answer = (body.answer or "").strip()
    expected_text = (expected or "").strip()
    auto_correct = bool(expected_text) and answer.casefold() == expected_text.casefold()
    is_correct = body.is_correct if body.is_correct is not None else auto_correct
    score = body.score if body.score is not None else (1.0 if is_correct else 0.0)
    attempt = WritingPhraseAttempt(
        learner_id=learner_id,
        phrase_id=phrase.id,
        exercise_id=body.exercise_id,
        exercise_type=body.exercise_type,
        answer=body.answer,
        expected_answer=expected,
        is_correct=is_correct,
        score=score,
        feedback=body.feedback,
        response_time_ms=body.response_time_ms,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    await db.flush()
    await MemoryWriter(db).record_event(
        MemoryEventInput(
            learner_id=learner_id,
            event_type="writing_phrase_attempted",
            skill="writing",
            subskill=phrase.tags[0] if phrase.tags else phrase.usage_position,
            source_type="writing_phrase_attempt",
            source_id=str(attempt.id),
            payload={
                "phrase_id": str(phrase.id),
                "exercise_id": str(attempt.exercise_id) if attempt.exercise_id else None,
                "exercise_type": attempt.exercise_type,
                "correct": attempt.is_correct,
                "score": attempt.score,
                "feedback": attempt.feedback,
                "tags": phrase.tags,
                "error_type": None if attempt.is_correct else "needs_practice",
                "response_time_ms": attempt.response_time_ms,
            },
            confidence=0.95,
            occurred_at=attempt.occurred_at,
        )
    )
    try:
        await MemoryCurator(db).curate_learner(learner_id)
    except Exception:
        pass
    await db.refresh(attempt)
    return AttemptResponse(
        id=attempt.id,
        phrase_id=attempt.phrase_id,
        exercise_id=attempt.exercise_id,
        exercise_type=attempt.exercise_type,
        answer=attempt.answer,
        expected_answer=attempt.expected_answer,
        is_correct=attempt.is_correct,
        score=attempt.score,
        feedback=attempt.feedback,
        response_time_ms=attempt.response_time_ms,
        occurred_at=attempt.occurred_at,
    )
