import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, get_model_router
from src.base_dictionary.enrichment import reading_translation
from src.base_dictionary.service import get_entry as get_base_dictionary_entry
from src.exercises import ExerciseAttemptCreate, ExerciseAttemptService, ExerciseTarget
from src.models.knowledge import CurriculumNode, KnowledgePoint, KnowledgeSource
from src.models.learner import Learner, LearnerProfile
from src.models.reading import ReadingMaterialHistory
from src.prompts import PromptExecutionContext, PromptExecutor
from src.providers.router import ModelRouter

router = APIRouter(tags=["reading-workshop"])

ReadingLevel = Literal["junior", "cet4", "cet6", "general"]
ReadingGoal = Literal["intensive", "extensive", "mixed"]
ReadingMaterialType = Literal["dialogue", "passage"]
ReadingMaterialLength = Literal["short", "long"]


class ReadingTitleSuggestionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)


class ReadingTitleSuggestionResponse(BaseModel):
    is_complete: bool
    suggested_title: str | None = None
    reason: str
    word_count: int
    sentence_count: int


class ReadingSelectionTranslationRequest(BaseModel):
    selection: str = Field(min_length=1, max_length=200)
    sentence: str = Field(min_length=1, max_length=1500)
    learner_level: str | None = Field(default=None, max_length=30)


class ReadingSelectionTranslationResponse(BaseModel):
    selection: str
    translation: str
    context_note: str
    confidence: float
    source: Literal["base_dictionary", "model"] = "model"
    build_version: str | None = None


class ReadingMaterialHistoryRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    text: str = Field(min_length=1, max_length=12000)
    level: ReadingLevel = "general"
    goal: ReadingGoal = "mixed"
    material_type: ReadingMaterialType = "passage"
    curriculum_node_id: uuid.UUID | None = None
    generation_context: dict[str, Any] = Field(default_factory=dict)


class ReadingMaterialGenerationRequest(BaseModel):
    curriculum_node_id: uuid.UUID | None = None
    material_type: ReadingMaterialType = "passage"
    length: ReadingMaterialLength = "short"
    goal: ReadingGoal = "mixed"
    level: ReadingLevel | None = None
    topic: str | None = Field(default=None, max_length=120)


class ReadingMaterialCompleteRequest(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=0, le=24 * 60 * 60)
    comprehension_score: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=2000)
    selected_sentence_count: int = Field(default=0, ge=0, le=500)
    grammar_topic_count: int = Field(default=0, ge=0, le=100)
    unknown_vocabulary: list[str] = Field(default_factory=list, max_length=50)
    grammar_blind_spots: list[str] = Field(default_factory=list, max_length=30)
    correction_notes: list[str] = Field(default_factory=list, max_length=30)
    perceived_difficulty: Literal["too_easy", "right", "challenging", "too_hard"] | None = None


class ReadingMaterialHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    learner_id: uuid.UUID
    title: str | None = None
    text: str
    level: ReadingLevel
    goal: ReadingGoal
    material_type: ReadingMaterialType
    word_count: int
    sentence_count: int
    source: str
    curriculum_node_id: uuid.UUID | None = None
    generation_context: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ReadingMaterialGenerationResponse(BaseModel):
    material: ReadingMaterialHistoryResponse
    generation_context: dict[str, Any]


class ReadingMaterialCompleteResponse(BaseModel):
    material_id: uuid.UUID
    attempt_id: uuid.UUID
    reading_value: int
    message: str


_SENTENCE_PATTERN = re.compile(r"[^.!?]+(?:[.!?]+[\"')\]]*)?|[^.!?]+$")
_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)?")
_DIALOGUE_TURN_PATTERN = re.compile(
    r"^\s*(?:[A-Z][A-Za-z]{0,24}(?:\s+[A-Z][A-Za-z]{0,24})?|[AB])\s*[:：]\s+\S",
    re.MULTILINE,
)
_STOP_WORDS = {
    "about",
    "after",
    "also",
    "because",
    "between",
    "could",
    "every",
    "from",
    "have",
    "into",
    "more",
    "most",
    "other",
    "should",
    "some",
    "such",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "through",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}


@router.post(
    "/api/learners/{learner_id}/reading-workshop/selection-translation",
    response_model=ReadingSelectionTranslationResponse,
)
async def translate_reading_selection(
    learner_id: uuid.UUID,
    body: ReadingSelectionTranslationRequest,
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> ReadingSelectionTranslationResponse:
    await _ensure_learner_exists(db, learner_id)
    selection = " ".join(body.selection.split())
    sentence = " ".join(body.sentence.split())
    if selection.lower() not in sentence.lower():
        raise HTTPException(status_code=422, detail="Selection must appear in the sentence")
    shared_translation = reading_translation(
        await get_base_dictionary_entry(db, selection)
    )
    if shared_translation is not None:
        return ReadingSelectionTranslationResponse(
            selection=selection,
            **shared_translation,
        )
    result = await PromptExecutor(db=db, model_router=model_router).execute(
        prompt_id="reading.selection_translation",
        variables={
            "selection": selection,
            "sentence": sentence,
            "learner_level": body.learner_level or "unknown",
        },
        context=PromptExecutionContext(
            learner_id=learner_id,
            source_module="api.reading",
            task_id="selection_translation",
            target_type="reading_selection",
            target_id=hashlib.sha256(f"{sentence}:{selection}".encode()).hexdigest()[:24],
        ),
    )
    if result.decision != "accepted" or not result.validated_output:
        raise HTTPException(status_code=502, detail="Selection translation failed schema validation")
    payload = result.validated_output
    return ReadingSelectionTranslationResponse(
        selection=selection,
        translation=str(payload["translation"]),
        context_note=str(payload["context_note"]),
        confidence=float(payload["confidence"]),
        source="model",
    )


@router.post("/api/reading-workshop/title-suggestion", response_model=ReadingTitleSuggestionResponse)
async def suggest_reading_title(
    body: ReadingTitleSuggestionRequest,
) -> ReadingTitleSuggestionResponse:
    raw_text = body.text.strip()
    text = _normalize_text(raw_text)
    sentences = _split_sentences(text)
    words = _words(text)
    is_complete, reason = _assess_complete_material(text, sentences, words)

    return ReadingTitleSuggestionResponse(
        is_complete=is_complete,
        suggested_title=_suggest_title(raw_text, sentences, words) if is_complete else None,
        reason=reason,
        word_count=len(words),
        sentence_count=len(sentences),
    )


@router.get(
    "/api/learners/{learner_id}/reading-workshop/materials",
    response_model=list[ReadingMaterialHistoryResponse],
)
async def list_reading_materials(
    learner_id: uuid.UUID,
    curriculum_node_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> list[ReadingMaterialHistory]:
    await _ensure_learner_exists(db, learner_id)
    query = select(ReadingMaterialHistory).where(ReadingMaterialHistory.learner_id == learner_id)
    if curriculum_node_id is not None:
        await _get_accessible_curriculum_node(db, learner_id, curriculum_node_id)
        query = query.where(ReadingMaterialHistory.curriculum_node_id == curriculum_node_id)
    result = await db.execute(
        query
        .order_by(ReadingMaterialHistory.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.post(
    "/api/learners/{learner_id}/reading-workshop/materials",
    response_model=ReadingMaterialHistoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_reading_material(
    learner_id: uuid.UUID,
    body: ReadingMaterialHistoryRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ReadingMaterialHistory:
    await _ensure_learner_exists(db, learner_id)
    if body.curriculum_node_id is not None:
        await _get_accessible_curriculum_node(db, learner_id, body.curriculum_node_id)
    stored_text = body.text.strip()
    normalized_text = _normalize_text(stored_text)
    words = _words(normalized_text)
    sentences = _split_sentences(normalized_text)
    text_hash = _text_hash(normalized_text)
    normalized_title = body.title.strip() if body.title and body.title.strip() else None

    result = await db.execute(
        select(ReadingMaterialHistory).where(
            ReadingMaterialHistory.learner_id == learner_id,
            ReadingMaterialHistory.text_hash == text_hash,
        )
    )
    material = result.scalar_one_or_none()
    if material is None:
        material = ReadingMaterialHistory(
            learner_id=learner_id,
            text=stored_text,
            text_hash=text_hash,
            source="reading_workshop",
        )
        db.add(material)

    material.title = normalized_title
    material.text = stored_text
    material.level = body.level
    material.goal = body.goal
    material.material_type = body.material_type
    material.curriculum_node_id = body.curriculum_node_id
    material.generation_context = body.generation_context or {}
    material.word_count = len(words)
    material.sentence_count = len(sentences)
    material.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(material)
    return material


@router.post(
    "/api/learners/{learner_id}/reading-workshop/generated-materials",
    response_model=ReadingMaterialGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_reading_material(
    learner_id: uuid.UUID,
    body: ReadingMaterialGenerationRequest,
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> ReadingMaterialGenerationResponse:
    await _ensure_learner_exists(db, learner_id)
    node: CurriculumNode | None = None
    source: KnowledgeSource | None = None
    if body.curriculum_node_id is not None:
        node, source = await _get_accessible_curriculum_node(db, learner_id, body.curriculum_node_id)
        points = await _unit_points(db, node)
        profile = await _learner_profile(db, learner_id)
        level = body.level or _reading_level_from_profile(profile)
        variables = _generation_prompt_variables(
            learner_id=learner_id, profile=profile, source=source, node=node, points=points,
            material_type=body.material_type, length=body.length, level=level,
        )
    else:
        profile = await _learner_profile(db, learner_id)
        level = body.level or _reading_level_from_profile(profile)
        variables = _personalized_generation_prompt_variables(
            learner_id=learner_id,
            profile=profile,
            material_type=body.material_type,
            length=body.length,
            level=level,
            topic=body.topic,
        )
    result = await PromptExecutor(db=db, model_router=model_router).execute(
        prompt_id="reading.material_generation",
        variables=variables,
        context=PromptExecutionContext(
            learner_id=learner_id,
            source_module="api.reading",
            target_type="curriculum_node" if node else "learner_reading_track",
            target_id=node.id if node else learner_id,
            metadata={
                "material_type": body.material_type,
                "length": body.length,
                "level": level,
            },
        ),
    )
    if result.decision != "accepted" or not result.validated_output:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Reading material generation failed schema validation",
        )

    payload = result.validated_output
    stored_text = str(payload["text"]).strip()
    normalized_text = _normalize_text(stored_text)
    _validate_generated_material_shape(
        requested_type=body.material_type,
        payload_type=str(payload.get("material_type") or ""),
        text=stored_text,
    )
    words = _words(normalized_text)
    sentences = _split_sentences(normalized_text)
    if len(words) < 20 or len(sentences) < 2:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Generated reading material is too short",
        )

    generation_context = {
        "prompt_id": result.prompt_id,
        "prompt_version": result.prompt_version,
        "prompt_execution_record_id": str(result.execution_record_id) if result.execution_record_id else None,
        "schema_validation_status": result.schema_validation_status,
        "repair_used": result.repair_used,
        "source_id": str(source.id) if source else None,
        "source_title": source.title if source else "个性化阅读主线",
        "unit_title": node.title if node else None,
        "unit_subtitle": node.subtitle if node else None,
        "learning_track": "school" if node else "reading",
        "requested_topic": body.topic,
        "length": body.length,
        "theme": payload.get("theme"),
        "grammar_focus": payload.get("grammar_focus") or [],
        "vocabulary_used": payload.get("vocabulary_used") or [],
        "level_rationale": payload.get("level_rationale"),
        "comprehension_checks": payload.get("comprehension_checks") or [],
        "confidence": payload.get("confidence"),
    }
    material = ReadingMaterialHistory(
        learner_id=learner_id,
        curriculum_node_id=node.id if node else None,
        title=str(payload["title"]).strip()[:200],
        text=stored_text,
        text_hash=_text_hash(normalized_text),
        level=level,
        goal=body.goal,
        material_type=body.material_type,
        word_count=len(words),
        sentence_count=len(sentences),
        source="unit_llm_generation",
        generation_context=generation_context,
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)

    return ReadingMaterialGenerationResponse(
        material=ReadingMaterialHistoryResponse.model_validate(material),
        generation_context=generation_context,
    )


@router.post(
    "/api/learners/{learner_id}/reading-workshop/materials/{material_id}/complete",
    response_model=ReadingMaterialCompleteResponse,
)
async def complete_reading_material(
    learner_id: uuid.UUID,
    material_id: uuid.UUID,
    body: ReadingMaterialCompleteRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ReadingMaterialCompleteResponse:
    await _ensure_learner_exists(db, learner_id)
    result = await db.execute(
        select(ReadingMaterialHistory).where(
            ReadingMaterialHistory.id == material_id,
            ReadingMaterialHistory.learner_id == learner_id,
        )
    )
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(status_code=404, detail="Reading material not found")

    reading_value = _reading_value(material, body)
    attempt = await ExerciseAttemptService(db).save_attempt(
        learner_id,
        ExerciseAttemptCreate(
            exercise_id=f"reading-material-{material.id}",
            target=ExerciseTarget(
                type="reading_passage",
                id=str(material.id),
                label=material.title or "Reading material",
            ),
            answer="completed",
            result="correct",
            metadata={
                "source": "reading_workshop_completion",
                "reading_value": reading_value,
                "comprehension_score": body.comprehension_score,
                "duration_seconds": body.duration_seconds,
                "selected_sentence_count": body.selected_sentence_count,
                "grammar_topic_count": body.grammar_topic_count,
                "material_type": material.material_type,
                "curriculum_node_id": str(material.curriculum_node_id) if material.curriculum_node_id else None,
                "notes": body.notes,
                "unknown_vocabulary": body.unknown_vocabulary,
                "grammar_blind_spots": body.grammar_blind_spots,
                "correction_notes": body.correction_notes,
                "perceived_difficulty": body.perceived_difficulty,
            },
            source_context={
                "source": material.source,
                "material_id": str(material.id),
                "title": material.title,
                "word_count": material.word_count,
                "sentence_count": material.sentence_count,
                "generation_context": material.generation_context or {},
            },
            should_update_mastery=False,
            should_create_error_pattern=False,
            should_create_memory_evidence=True,
        ),
    )
    return ReadingMaterialCompleteResponse(
        material_id=material.id,
        attempt_id=attempt.id,
        reading_value=reading_value,
        message="阅读训练已记录，学习画像的阅读值会随练习记录更新。",
    )


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


async def _get_accessible_curriculum_node(
    db: AsyncSession,
    learner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> tuple[CurriculumNode, KnowledgeSource]:
    result = await db.execute(
        select(CurriculumNode, KnowledgeSource)
        .join(KnowledgeSource, KnowledgeSource.id == CurriculumNode.source_id)
        .where(
            CurriculumNode.id == node_id,
            CurriculumNode.node_type == "unit",
            or_(
                KnowledgeSource.owner_learner_id.is_(None),
                KnowledgeSource.owner_learner_id == learner_id,
            ),
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Curriculum unit not found")
    return row[0], row[1]


async def _unit_points(db: AsyncSession, node: CurriculumNode) -> list[KnowledgePoint]:
    result = await db.execute(
        select(KnowledgePoint)
        .where(KnowledgePoint.curriculum_node_id == node.id, KnowledgePoint.status == "published")
        .order_by(
            KnowledgePoint.content["unit_order"].as_integer().asc().nullslast(),
            KnowledgePoint.created_at.asc(),
        )
    )
    return list(result.scalars().all())


async def _learner_profile(db: AsyncSession, learner_id: uuid.UUID) -> LearnerProfile | None:
    result = await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
    return result.scalar_one_or_none()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_sentences(text: str) -> list[str]:
    return [match.group(0).strip() for match in _SENTENCE_PATTERN.finditer(text) if match.group(0).strip()]


def _words(text: str) -> list[str]:
    return _WORD_PATTERN.findall(text)


def _assess_complete_material(text: str, sentences: list[str], words: list[str]) -> tuple[bool, str]:
    if len(words) < 30:
        return False, "material_too_short"
    if len(sentences) < 2:
        return False, "needs_more_sentences"
    if not re.search(r'[.!?]["\')\]]*$', text):
        return False, "missing_terminal_punctuation"
    return True, "complete_enough_for_title"


def _suggest_title(text: str, sentences: list[str], words: list[str]) -> str:
    explicit_title = _explicit_title(text)
    if explicit_title:
        return explicit_title

    candidates = _keyword_candidates(words)
    if candidates:
        return _title_case(" ".join(candidates[:4]))

    first_sentence = sentences[0] if sentences else text
    first_words = _words(first_sentence)[:7]
    return _title_case(" ".join(first_words)) or "Reading Material"


def _explicit_title(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    first_line_words = _words(lines[0])
    if 2 <= len(first_line_words) <= 10 and not re.search(r"[.!?]$", lines[0]):
        return _title_case(" ".join(first_line_words))
    return None


def _keyword_candidates(words: list[str]) -> list[str]:
    counts: dict[str, tuple[int, int]] = {}
    for index, raw_word in enumerate(words):
        word = raw_word.lower()
        if len(word) < 4 or word in _STOP_WORDS:
            continue
        count, first_index = counts.get(word, (0, index))
        counts[word] = (count + 1, first_index)

    return [
        word
        for word, _ in sorted(
            counts.items(),
            key=lambda item: (-item[1][0], item[1][1], item[0]),
        )
    ]


def _title_case(text: str) -> str:
    small_words = {"and", "as", "for", "in", "of", "on", "or", "the", "to", "with"}
    words = _words(text)
    if not words:
        return ""

    titled: list[str] = []
    for index, word in enumerate(words):
        lowered = word.lower()
        if 0 < index < len(words) - 1 and lowered in small_words:
            titled.append(lowered)
        else:
            titled.append(lowered.capitalize())
    return " ".join(titled)[:80]


def _generation_prompt_variables(
    *,
    learner_id: uuid.UUID,
    profile: LearnerProfile | None,
    source: KnowledgeSource,
    node: CurriculumNode,
    points: list[KnowledgePoint],
    material_type: ReadingMaterialType,
    length: ReadingMaterialLength,
    level: ReadingLevel,
) -> dict[str, Any]:
    grammar_points = [point for point in points if point.type in {"grammar", "sentence_pattern"}]
    vocabulary_points = [point for point in points if point.type == "vocabulary"]
    text_notes = [point for point in points if point.type in {"text_note", "phrase"}]
    return {
        "material_type": material_type,
        "length_label": "120-180 words" if length == "short" else "260-420 words",
        "learner_profile": {
            "learner_id": str(learner_id),
            "current_level": profile.current_level if profile else None,
            "target_exam": profile.target_exam if profile else None,
            "weak_skills": profile.weak_skills if profile else [],
            "reading_level": level,
        },
        "unit_context": {
            "source_title": source.title,
            "grade": source.grade,
            "volume": source.volume,
            "unit_title": node.title,
            "unit_subtitle": node.subtitle,
            "objectives": node.learning_objectives or [],
        },
        "grammar_focus": [_point_focus_payload(point) for point in grammar_points[:8]],
        "vocabulary_focus": [_point_focus_payload(point) for point in vocabulary_points[:16]],
        "theme_focus": [_point_focus_payload(point) for point in text_notes[:8]],
    }


def _personalized_generation_prompt_variables(
    *,
    learner_id: uuid.UUID,
    profile: LearnerProfile | None,
    material_type: ReadingMaterialType,
    length: ReadingMaterialLength,
    level: ReadingLevel,
    topic: str | None,
) -> dict[str, Any]:
    interests = profile.interest_topics if profile and isinstance(profile.interest_topics, list) else []
    weak_skills = profile.weak_skills if profile and isinstance(profile.weak_skills, list) else []
    selected_topic = topic.strip() if topic and topic.strip() else (interests[0] if interests else "everyday discovery")
    return {
        "material_type": material_type,
        "length_label": "120-180 words" if length == "short" else "260-420 words",
        "learner_profile": {
            "learner_id": str(learner_id),
            "current_level": profile.current_level if profile else None,
            "target_exam": profile.target_exam if profile else None,
            "learning_track": "reading",
            "interest_topics": interests,
            "weak_skills": weak_skills,
            "daily_time_budget_minutes": profile.daily_time_budget_minutes if profile else None,
            "reading_level": level,
        },
        "unit_context": {
            "source_title": "BinnAgent personalized reading track",
            "unit_title": selected_topic,
            "objectives": [
                "expand useful vocabulary through context",
                "notice one or two reusable grammar patterns",
                "check comprehension and expose blind spots",
            ],
        },
        "grammar_focus": weak_skills[:4],
        "vocabulary_focus": [],
        "theme_focus": [selected_topic, *interests[:4]],
    }


def _point_focus_payload(point: KnowledgePoint) -> dict[str, Any]:
    content = point.content or {}
    return {
        "title": point.title,
        "type": point.type,
        "summary": point.summary,
        "theme": content.get("theme"),
        "unit_order": content.get("unit_order"),
    }


def _reading_level_from_profile(profile: LearnerProfile | None) -> ReadingLevel:
    current_level = (profile.current_level if profile else None) or ""
    normalized = current_level.strip().lower()
    if normalized in {"a1", "a2", "junior", "初中"}:
        return "junior"
    if normalized in {"b2", "c1", "c2", "cet6", "六级"}:
        return "cet6"
    if normalized in {"b1", "cet4", "四级"}:
        return "cet4"
    return "general"


def _validate_generated_material_shape(
    *,
    requested_type: ReadingMaterialType,
    payload_type: str,
    text: str,
) -> None:
    if payload_type.strip() != requested_type:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Generated reading material type does not match the request",
        )

    looks_like_dialogue = _looks_like_dialogue(text)
    if requested_type == "passage" and looks_like_dialogue:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Generated passage used dialogue format",
        )
    if requested_type == "dialogue" and not looks_like_dialogue:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Generated dialogue did not use dialogue format",
        )


def _looks_like_dialogue(text: str) -> bool:
    nonempty_lines = [line for line in text.splitlines() if line.strip()]
    if not nonempty_lines:
        return False

    turn_count = len(_DIALOGUE_TURN_PATTERN.findall(text))
    if turn_count < 2:
        return False
    return turn_count / len(nonempty_lines) >= 0.3


def _reading_value(material: ReadingMaterialHistory, body: ReadingMaterialCompleteRequest) -> int:
    base = min(80, max(10, round(material.word_count / 3)))
    if material.material_type == "dialogue":
        base += 5
    if material.goal == "mixed":
        base += 10
    if body.selected_sentence_count:
        base += min(15, body.selected_sentence_count * 2)
    if body.grammar_topic_count:
        base += min(10, body.grammar_topic_count * 2)
    if body.comprehension_score is not None:
        base += round((body.comprehension_score - 60) / 5)
    return max(10, min(100, base))


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
