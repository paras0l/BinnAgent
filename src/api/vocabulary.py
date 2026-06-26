import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.memory.vocabulary_store import VocabularyStore
from src.models.learner import Learner
from src.models.vocabulary import (
    VocabularyItem,
    VocabularyItemSource,
    VocabularyMasteryVector,
    VocabularyMistake,
    VocabularyUserOverride,
)
from src.tools.vocabulary_detail_html import extract_vocabulary_detail_html
from src.vocabulary.learning import canonical_vocabulary_key, mastery_to_dict

router = APIRouter(prefix="/api/learners/{learner_id}/vocabulary", tags=["vocabulary"])


class AddWordRequest(BaseModel):
    word: str = Field(min_length=1, max_length=255)
    phonetic: str | None = Field(default=None, max_length=255)
    level: str | None = Field(default=None, max_length=20)
    meanings: list[str] | None = None

    @field_validator("word")
    @classmethod
    def word_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Word must not be blank")
        return stripped


class UpsertDetailHtmlRequest(BaseModel):
    term: str = Field(min_length=1, max_length=255)
    html: str = Field(min_length=1, max_length=80_000)

    @field_validator("term")
    @classmethod
    def term_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Term must not be blank")
        return stripped


class ReviewWordRequest(BaseModel):
    word_id: uuid.UUID
    correct: bool
    response_time_ms: int | None = Field(default=None, ge=0)


class WordResponse(BaseModel):
    id: uuid.UUID
    word: str
    phonetic: str | None = None
    status: str
    confidence: float
    next_review_at: str | None = None


class UpsertDetailHtmlResponse(BaseModel):
    id: uuid.UUID
    word: str
    created: bool
    phonetic: str | None = None
    meanings_count: int
    examples_count: int


class VocabularyListItemResponse(BaseModel):
    id: uuid.UUID
    word: str
    phonetic: str | None = None
    status: str
    confidence: float
    review_count: int
    meaning: str | None = None
    last_reviewed_at: str | None = None
    next_review_at: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)


class VocabularyDetailResponse(BaseModel):
    id: uuid.UUID
    word: str
    phonetic: str | None = None
    phonetic_uk: str | None = None
    phonetic_us: str | None = None
    audio_url: str | None = None
    audio_uk: str | None = None
    audio_us: str | None = None
    entry_kind: str
    meanings: list[dict[str, Any]] = Field(default_factory=list)
    dictionary_senses: list[dict[str, Any]] = Field(default_factory=list)
    word_forms: dict[str, list[str]] = Field(default_factory=dict)
    dictionary_tags: list[str] = Field(default_factory=list)
    examples: list[Any] = Field(default_factory=list)
    dictionary_provider: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    user_override: dict[str, Any] = Field(default_factory=dict)
    mastery: dict[str, float] = Field(default_factory=dict)
    mistakes: list[dict[str, Any]] = Field(default_factory=list)


class VocabularyOverrideRequest(BaseModel):
    display_form_override: str | None = Field(default=None, max_length=255)
    meaning_overrides: list[dict[str, Any]] | None = None
    hidden_meaning_ids: list[str] | None = None
    user_understanding: str | None = Field(default=None, max_length=2000)
    user_examples: list[str] | None = None
    user_collocations: list[str] | None = None
    user_notes: str | None = Field(default=None, max_length=4000)
    preferred_accent: str | None = Field(default=None, pattern="^(auto|uk|us)$")
    review_preference: str | None = Field(
        default=None, pattern="^(normal|mastered|too_easy|excluded|relearn)$"
    )
    manual_mastery: str | None = Field(default=None, pattern="^(mastered|too_easy|relearn)$")


class MistakeUpdateRequest(BaseModel):
    mistake_type: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=2000)
    correction: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


def _first_text(value: Any) -> str | None:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in (
                "definition_zh",
                "definition",
                "meaning",
                "content",
                "text",
                "zh",
                "definition_en",
                "en",
            ):
                text = first.get(key)
                if isinstance(text, str) and text.strip():
                    return text.strip()
    if isinstance(value, dict):
        for key in (
            "definition_zh",
            "definition",
            "meaning",
            "content",
            "text",
            "zh",
            "definition_en",
            "en",
        ):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else str(value) if value else None


def _meaning_id(meaning: Any, index: int) -> str:
    if isinstance(meaning, dict):
        for key in ("id", "sense_id", "key"):
            value = meaning.get(key)
            if isinstance(value, str) and value:
                return value
    return str(index)


def _is_active_override(value: Any) -> bool:
    return not isinstance(value, dict) or value.get("active", True) is not False


def _visible_meanings(item: VocabularyItem, override: VocabularyUserOverride | None) -> list[Any]:
    meanings = item.meanings if isinstance(item.meanings, list) else []
    hidden = set(override.hidden_meaning_ids if override else [])
    visible = [
        meaning
        for index, meaning in enumerate(meanings)
        if _meaning_id(meaning, index) not in hidden
    ]
    user_meanings = (
        override.meaning_overrides
        if override and isinstance(override.meaning_overrides, list)
        else []
    )
    return [meaning for meaning in user_meanings if _is_active_override(meaning)] + visible


def _effective_examples(item: VocabularyItem, override: VocabularyUserOverride | None) -> list[Any]:
    user_examples = override.user_examples if override and isinstance(override.user_examples, list) else []
    system_examples = item.examples if isinstance(item.examples, list) else []
    return user_examples + system_examples


def _override_payload(override: VocabularyUserOverride | None) -> dict[str, Any]:
    if override is None:
        return {
            "display_form_override": None,
            "meaning_overrides": [],
            "hidden_meaning_ids": [],
            "user_understanding": None,
            "user_examples": [],
            "user_collocations": [],
            "user_notes": None,
            "preferred_accent": "auto",
            "review_preference": "normal",
            "excluded_from_review": False,
            "manual_mastery": None,
        }
    return {
        "id": str(override.id),
        "display_form_override": override.display_form_override,
        "meaning_overrides": override.meaning_overrides or [],
        "hidden_meaning_ids": override.hidden_meaning_ids or [],
        "user_understanding": override.user_understanding,
        "user_examples": override.user_examples or [],
        "user_collocations": override.user_collocations or [],
        "user_notes": override.user_notes,
        "preferred_accent": override.preferred_accent,
        "review_preference": override.review_preference,
        "excluded_from_review": override.excluded_from_review,
        "manual_mastery": override.manual_mastery,
    }


async def _get_vocabulary_item(
    db: AsyncSession, learner_id: uuid.UUID, item_id: uuid.UUID
) -> VocabularyItem:
    result = await db.execute(
        select(VocabularyItem).where(
            VocabularyItem.id == item_id,
            VocabularyItem.learner_id == learner_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
    return item


async def _detail_response(
    db: AsyncSession, learner_id: uuid.UUID, item: VocabularyItem
) -> VocabularyDetailResponse:
    override_result = await db.execute(
        select(VocabularyUserOverride).where(
            VocabularyUserOverride.learner_id == learner_id,
            VocabularyUserOverride.vocabulary_item_id == item.id,
        )
    )
    override = override_result.scalar_one_or_none()
    mastery_result = await db.execute(
        select(VocabularyMasteryVector).where(
            VocabularyMasteryVector.learner_id == learner_id,
            VocabularyMasteryVector.vocabulary_item_id == item.id,
        )
    )
    mastery = mastery_result.scalar_one_or_none()
    source_result = await db.execute(
        select(VocabularyItemSource).where(
            VocabularyItemSource.learner_id == learner_id,
            VocabularyItemSource.vocabulary_item_id == item.id,
            VocabularyItemSource.active.is_(True),
        )
    )
    sources = [
        {
            "type": source.source_type,
            "label": source.display_label,
            "reason": source.reason,
            "priority": source.priority,
            "context": source.context_snapshot or {},
        }
        for source in source_result.scalars().all()
    ]
    mistake_result = await db.execute(
        select(VocabularyMistake)
        .where(
            VocabularyMistake.learner_id == learner_id,
            VocabularyMistake.vocabulary_item_id == item.id,
            VocabularyMistake.active.is_(True),
        )
        .order_by(VocabularyMistake.updated_at.desc())
        .limit(8)
    )
    mistakes = [
        {
            "id": str(mistake.id),
            "mistake_type": mistake.mistake_type,
            "note": mistake.note,
            "correction": mistake.correction,
            "active": mistake.active,
            "created_at": _iso(mistake.created_at),
            "updated_at": _iso(mistake.updated_at),
        }
        for mistake in mistake_result.scalars().all()
    ]
    return VocabularyDetailResponse(
        id=item.id,
        word=override.display_form_override if override and override.display_form_override else item.word,
        phonetic=item.phonetic,
        phonetic_uk=item.phonetic_uk,
        phonetic_us=item.phonetic_us,
        audio_url=item.audio_url,
        audio_uk=item.audio_uk,
        audio_us=item.audio_us,
        entry_kind=item.entry_kind,
        meanings=_visible_meanings(item, override),
        dictionary_senses=(
            item.dictionary_senses if isinstance(item.dictionary_senses, list) else []
        ),
        word_forms=item.word_forms if isinstance(item.word_forms, dict) else {},
        dictionary_tags=item.dictionary_tags if isinstance(item.dictionary_tags, list) else [],
        examples=_effective_examples(item, override),
        dictionary_provider=item.dictionary_provider,
        sources=sources,
        user_override=_override_payload(override),
        mastery=mastery_to_dict(mastery, item.confidence),
        mistakes=mistakes,
    )


@router.get("", response_model=list[VocabularyListItemResponse])
async def list_vocabulary(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[VocabularyListItemResponse]:
    await _ensure_learner_exists(db, learner_id)

    result = await db.execute(
        select(VocabularyItem)
        .where(VocabularyItem.learner_id == learner_id)
        .order_by(
            VocabularyItem.last_reviewed_at.desc().nullslast(),
            VocabularyItem.updated_at.desc(),
            VocabularyItem.created_at.desc(),
        )
    )
    items = list(result.scalars().all())
    item_ids = [item.id for item in items]
    source_map: dict[uuid.UUID, list[dict[str, Any]]] = {item_id: [] for item_id in item_ids}
    if item_ids:
        source_result = await db.execute(
            select(VocabularyItemSource).where(
                VocabularyItemSource.learner_id == learner_id,
                VocabularyItemSource.vocabulary_item_id.in_(item_ids),
                VocabularyItemSource.active.is_(True),
            )
        )
        for source in source_result.scalars().all():
            source_map[source.vocabulary_item_id].append(
                {
                    "type": source.source_type,
                    "label": source.display_label,
                    "reason": source.reason,
                    "priority": source.priority,
                    "context": source.context_snapshot or {},
                }
            )
    for item in items:
        if source_map[item.id] or not item.source_ref:
            continue
        source_type = item.source_ref.split(":", 1)[0]
        label = (
            "对话"
            if source_type == "conversation_message"
            else "课程"
            if source_type == "session"
            else "手动"
        )
        source_map[item.id].append({"type": source_type, "label": label, "context": {}})
    return [
        VocabularyListItemResponse(
            id=item.id,
            word=item.word,
            phonetic=item.phonetic,
            status=item.status,
            confidence=item.confidence,
            review_count=item.review_count,
            meaning=_first_text(item.meanings),
            last_reviewed_at=_iso(item.last_reviewed_at),
            next_review_at=_iso(item.next_review_at),
            sources=source_map[item.id],
        )
        for item in items
    ]


@router.get("/detail", response_model=VocabularyDetailResponse)
async def vocabulary_detail(
    learner_id: uuid.UUID,
    term: str = Query(min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyDetailResponse:
    await _ensure_learner_exists(db, learner_id)
    canonical = canonical_vocabulary_key(term)
    result = await db.execute(
        select(VocabularyItem).where(
            VocabularyItem.learner_id == learner_id,
            VocabularyItem.canonical_key == canonical,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
    return await _detail_response(db, learner_id, item)


@router.patch("/{item_id}/override", response_model=VocabularyDetailResponse)
async def update_vocabulary_override(
    learner_id: uuid.UUID,
    item_id: uuid.UUID,
    req: VocabularyOverrideRequest,
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyDetailResponse:
    await _ensure_learner_exists(db, learner_id)
    item = await _get_vocabulary_item(db, learner_id, item_id)
    result = await db.execute(
        select(VocabularyUserOverride).where(
            VocabularyUserOverride.learner_id == learner_id,
            VocabularyUserOverride.vocabulary_item_id == item_id,
        )
    )
    override = result.scalar_one_or_none()
    if override is None:
        override = VocabularyUserOverride(
            learner_id=learner_id,
            vocabulary_item_id=item_id,
            meaning_overrides=[],
            hidden_meaning_ids=[],
            user_examples=[],
            user_collocations=[],
            preferred_accent="auto",
            review_preference="normal",
            excluded_from_review=False,
        )
        db.add(override)
    data = req.model_dump(exclude_unset=True)
    for key in (
        "display_form_override",
        "meaning_overrides",
        "hidden_meaning_ids",
        "user_understanding",
        "user_examples",
        "user_collocations",
        "user_notes",
        "preferred_accent",
        "review_preference",
        "manual_mastery",
    ):
        if key in data:
            setattr(override, key, data[key])
    if "review_preference" in data:
        override.excluded_from_review = data["review_preference"] == "excluded"
        if data["review_preference"] == "mastered":
            item.status = "mastered"
            item.confidence = max(item.confidence, 0.95)
            override.manual_mastery = "mastered"
        elif data["review_preference"] == "relearn":
            item.status = "learning"
            item.confidence = min(item.confidence, 0.2)
            item.next_review_at = datetime.now(timezone.utc)
            override.manual_mastery = "relearn"
        elif data["review_preference"] == "too_easy":
            item.status = "mastered"
            item.confidence = max(item.confidence, 0.9)
            override.manual_mastery = "too_easy"
    if override.preferred_accent in {"uk", "us", "auto"}:
        item.preferred_accent = override.preferred_accent
    await db.commit()
    await db.refresh(item)
    return await _detail_response(db, learner_id, item)


@router.patch("/{item_id}/mistakes/{mistake_id}", response_model=VocabularyDetailResponse)
async def update_vocabulary_mistake(
    learner_id: uuid.UUID,
    item_id: uuid.UUID,
    mistake_id: uuid.UUID,
    req: MistakeUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyDetailResponse:
    await _ensure_learner_exists(db, learner_id)
    item = await _get_vocabulary_item(db, learner_id, item_id)
    result = await db.execute(
        select(VocabularyMistake).where(
            VocabularyMistake.id == mistake_id,
            VocabularyMistake.learner_id == learner_id,
            VocabularyMistake.vocabulary_item_id == item_id,
        )
    )
    mistake = result.scalar_one_or_none()
    if mistake is None:
        raise HTTPException(status_code=404, detail="Vocabulary mistake not found")
    for key, value in req.model_dump(exclude_unset=True).items():
        setattr(mistake, key, value)
    await db.commit()
    await db.refresh(item)
    return await _detail_response(db, learner_id, item)


@router.delete("/{item_id}/mistakes/{mistake_id}", response_model=VocabularyDetailResponse)
async def delete_vocabulary_mistake(
    learner_id: uuid.UUID,
    item_id: uuid.UUID,
    mistake_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyDetailResponse:
    await _ensure_learner_exists(db, learner_id)
    item = await _get_vocabulary_item(db, learner_id, item_id)
    result = await db.execute(
        select(VocabularyMistake).where(
            VocabularyMistake.id == mistake_id,
            VocabularyMistake.learner_id == learner_id,
            VocabularyMistake.vocabulary_item_id == item_id,
        )
    )
    mistake = result.scalar_one_or_none()
    if mistake is None:
        raise HTTPException(status_code=404, detail="Vocabulary mistake not found")
    mistake.active = False
    await db.commit()
    await db.refresh(item)
    return await _detail_response(db, learner_id, item)


@router.post("/add", response_model=WordResponse)
async def add_word(
    learner_id: uuid.UUID,
    req: AddWordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    await _ensure_learner_exists(db, learner_id)

    store = VocabularyStore(db)
    try:
        item = await store.add_word(
            learner_id=learner_id,
            word=req.word,
            phonetic=req.phonetic,
            level=req.level,
            meanings=req.meanings,
            source_ref="manual",
        )
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid vocabulary word")
    return WordResponse(
        id=item.id,
        word=item.word,
        phonetic=item.phonetic,
        status=item.status,
        confidence=item.confidence,
        next_review_at=item.next_review_at.isoformat()
        if hasattr(item.next_review_at, "isoformat")
        else str(item.next_review_at)
        if item.next_review_at
        else None,
    )


@router.post("/detail-html", response_model=UpsertDetailHtmlResponse)
async def upsert_vocabulary_detail_html(
    learner_id: uuid.UUID,
    req: UpsertDetailHtmlRequest,
    db: AsyncSession = Depends(get_db_session),
) -> UpsertDetailHtmlResponse:
    await _ensure_learner_exists(db, learner_id)
    canonical = canonical_vocabulary_key(req.term)
    if not canonical:
        raise HTTPException(status_code=422, detail="Invalid vocabulary term")
    extracted = await extract_vocabulary_detail_html(req.term, req.html)
    result = await db.execute(
        select(VocabularyItem).where(
            VocabularyItem.learner_id == learner_id,
            VocabularyItem.canonical_key == canonical,
        )
    )
    item = result.scalar_one_or_none()
    created = item is None
    if item is None:
        item = VocabularyItem(
            learner_id=learner_id,
            word=req.term.strip(),
            canonical_key=canonical,
            entry_kind="phrase" if " " in canonical else "word",
            preferred_accent="auto",
            level="custom",
            source_ref="vocabulary_detail_html",
            status="learning",
            confidence=0.0,
            review_count=0,
            next_review_at=datetime.now(timezone.utc),
        )
        db.add(item)
    item.word = req.term.strip()
    item.phonetic = extracted.phonetic
    item.meanings = extracted.meanings
    item.dictionary_senses = extracted.dictionary_senses
    item.collocations = extracted.collocations
    item.examples = extracted.examples
    item.dictionary_provider = extracted.provider
    item.dictionary_enriched_at = datetime.now(timezone.utc)
    await db.flush()

    source_result = await db.execute(
        select(VocabularyItemSource).where(
            VocabularyItemSource.learner_id == learner_id,
            VocabularyItemSource.vocabulary_item_id == item.id,
            VocabularyItemSource.source_type == "vocabulary_detail_html",
        )
    )
    source = source_result.scalar_one_or_none()
    if source is None:
        source = VocabularyItemSource(
            learner_id=learner_id,
            vocabulary_item_id=item.id,
            source_type="vocabulary_detail_html",
            source_id=canonical,
            display_label="词汇详解 HTML",
            context_snapshot={},
            active=True,
        )
        db.add(source)
    source.context_snapshot = {
        "dictionary_provider": item.dictionary_provider,
        "html_length": len(req.html),
    }
    await db.commit()
    await db.refresh(item)
    return UpsertDetailHtmlResponse(
        id=item.id,
        word=item.word,
        created=created,
        phonetic=item.phonetic,
        meanings_count=len(item.meanings or []),
        examples_count=len(item.examples or []),
    )


@router.get("/due", response_model=list[WordResponse])
async def get_due_reviews(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    await _ensure_learner_exists(db, learner_id)

    store = VocabularyStore(db)
    items = await store.get_due_reviews(learner_id)
    return [
        WordResponse(
            id=item.id,
            word=item.word,
            phonetic=item.phonetic,
            status=item.status,
            confidence=item.confidence,
            next_review_at=item.next_review_at.isoformat()
            if hasattr(item.next_review_at, "isoformat")
            else str(item.next_review_at)
            if item.next_review_at
            else None,
        )
        for item in items
    ]


@router.post("/review", response_model=WordResponse)
async def review_word(
    learner_id: uuid.UUID,
    req: ReviewWordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    await _ensure_learner_exists(db, learner_id)

    store = VocabularyStore(db)
    try:
        item = await store.update_confidence(
            learner_id=learner_id,
            item_id=req.word_id,
            correct=req.correct,
            response_time_ms=req.response_time_ms,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
    return WordResponse(
        id=item.id,
        word=item.word,
        phonetic=item.phonetic,
        status=item.status,
        confidence=item.confidence,
        next_review_at=item.next_review_at.isoformat()
        if hasattr(item.next_review_at, "isoformat")
        else str(item.next_review_at)
        if item.next_review_at
        else None,
    )


@router.get("/{item_id}", response_model=VocabularyDetailResponse)
async def vocabulary_detail_by_id(
    learner_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyDetailResponse:
    await _ensure_learner_exists(db, learner_id)
    item = await _get_vocabulary_item(db, learner_id, item_id)
    return await _detail_response(db, learner_id, item)


@router.delete("/{word_id}", status_code=204)
async def delete_word(
    learner_id: uuid.UUID,
    word_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await _ensure_learner_exists(db, learner_id)

    store = VocabularyStore(db)
    try:
        await store.delete_word(learner_id=learner_id, item_id=word_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
