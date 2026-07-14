import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adaptive.fsrs import FSRSState, retrievability
from src.api.deps import get_db_session, require_learner_access
from src.cache import get_redis
from src.models.adaptive import AssessmentEvidence, FSRSReviewState, KnowledgeStateUpdate
from src.models.knowledge import GrammarCanDoProfile, KnowledgePoint, LearnerKnowledgeState
from src.models.learner import Learner

router = APIRouter(prefix="/api/learners/{learner_id}/grammar", tags=["grammar"])


class GrammarHtmlCacheResponse(BaseModel):
    topic_id: str
    prompt_hash: str
    prompt_version: str
    cached: bool
    html: str | None = None
    source: str | None = None
    stored_at: datetime | None = None


class StoreGrammarHtmlCacheRequest(BaseModel):
    html: str = Field(min_length=1)
    prompt_hash: str = Field(min_length=8, max_length=128)
    prompt_version: str = Field(min_length=1, max_length=50)
    source: str | None = Field(default=None, max_length=100)

    @field_validator("html", "prompt_hash", "prompt_version", "source")
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


GrammarEvidenceMode = Literal["recognition", "recall", "production"]


class GrammarDimensionResponse(BaseModel):
    mode: GrammarEvidenceMode
    score: float
    confidence: float
    evidence_count: int


class GrammarCanDoResponse(BaseModel):
    id: uuid.UUID
    external_id: int | None
    slug: str
    canonical_key: str
    category: str
    subcategory: str
    cefr_level: str
    construct_type: str
    guideword: str | None
    can_do_statement: str
    status: str
    mastery_score: float
    predicted_success: float
    confidence: float
    next_review_at: datetime | None
    dimensions: list[GrammarDimensionResponse]


class GrammarMatrixCellResponse(BaseModel):
    category: str
    cefr_level: str
    stable: int
    forming: int
    review: int
    repeated_failure: int
    no_evidence: int
    total: int


class GrammarMapResponse(BaseModel):
    catalog_version: str
    total_count: int
    example_count: int
    source_url: str | None
    source_attribution: str | None
    points: list[GrammarCanDoResponse]
    matrix: list[GrammarMatrixCellResponse]


class GrammarEvidenceResponse(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    mode: str
    outcome_score: float
    independent: bool
    semantic_confidence: float
    decision_reason: str
    mastery_before: float | None = None
    mastery_after: float | None = None
    item_difficulty: float


class GrammarCanDoDetailResponse(GrammarCanDoResponse):
    success_criteria: list[str]
    failure_criteria: list[str]
    positive_examples: list[str]
    negative_examples: list[str]
    prerequisites: list[str]
    fsrs: dict | None
    recent_evidence: list[GrammarEvidenceResponse]


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


def _dimension_payload(evidence: list[AssessmentEvidence]) -> list[GrammarDimensionResponse]:
    payload: list[GrammarDimensionResponse] = []
    for mode in ("recognition", "recall", "production"):
        rows = [row for row in evidence if row.evidence_mode == mode and row.updates_learning_state]
        if rows:
            weights = [max(0.1, row.semantic_confidence) * (1.0 if row.independent else 0.65) for row in rows]
            score = sum(row.outcome_score * weight for row, weight in zip(rows, weights, strict=True)) / sum(weights)
            confidence = min(1.0, (len(rows) / 4) * (sum(row.semantic_confidence for row in rows) / len(rows)))
        else:
            score = confidence = 0.0
        payload.append(GrammarDimensionResponse(mode=mode, score=round(score, 3), confidence=round(confidence, 3), evidence_count=len(rows)))
    return payload


def _learning_status(
    state: LearnerKnowledgeState | None,
    evidence: list[AssessmentEvidence],
    current_retrievability: float | None,
    now: datetime,
) -> str:
    accepted = [row for row in evidence if row.updates_learning_state]
    if not state or not accepted:
        return "no_evidence"
    if len(accepted) >= 2 and all(row.outcome_score < 0.5 for row in accepted[-2:]):
        return "repeated_failure"
    if (state.next_review_at and state.next_review_at <= now) or (
        current_retrievability is not None and current_retrievability < 0.6
    ):
        return "review"
    if state.mastery_score >= 0.8 and (current_retrievability is None or current_retrievability >= 0.75):
        return "stable"
    return "forming"


def _retrievability(fsrs: FSRSReviewState | None, now: datetime) -> float | None:
    if fsrs is None:
        return None
    return retrievability(
        FSRSState(
            difficulty=fsrs.difficulty,
            stability_days=fsrs.stability_days,
            last_review_at=fsrs.last_review_at,
            next_review_at=fsrs.next_review_at,
            review_count=fsrs.review_count,
        ),
        now,
    )


def _point_payload(
    profile: GrammarCanDoProfile,
    point: KnowledgePoint,
    state: LearnerKnowledgeState | None,
    fsrs: FSRSReviewState | None,
    evidence: list[AssessmentEvidence],
    now: datetime,
) -> GrammarCanDoResponse:
    current_retrievability = _retrievability(fsrs, now)
    return GrammarCanDoResponse(
        id=point.id,
        external_id=profile.external_id,
        slug=str((point.content or {}).get("slug") or point.canonical_key.rsplit(".", 1)[-1]),
        canonical_key=point.canonical_key,
        category=profile.category,
        subcategory=profile.subcategory,
        cefr_level=profile.cefr_level,
        construct_type=profile.construct_type,
        guideword=profile.guideword,
        can_do_statement=profile.can_do_statement,
        status=_learning_status(state, evidence, current_retrievability, now),
        mastery_score=round(float(state.mastery_score if state else 0.0), 3),
        predicted_success=round(float(state.predicted_success if state and state.predicted_success is not None else state.mastery_score if state else 0.0), 3),
        confidence=round(float(state.confidence if state else 0.0), 3),
        next_review_at=fsrs.next_review_at if fsrs else state.next_review_at if state else None,
        dimensions=_dimension_payload(evidence),
    )


async def _grammar_rows(db: AsyncSession, learner_id: uuid.UUID):
    result = await db.execute(
        select(GrammarCanDoProfile, KnowledgePoint, LearnerKnowledgeState, FSRSReviewState)
        .join(KnowledgePoint, KnowledgePoint.id == GrammarCanDoProfile.knowledge_point_id)
        .outerjoin(
            LearnerKnowledgeState,
            and_(LearnerKnowledgeState.knowledge_point_id == KnowledgePoint.id, LearnerKnowledgeState.learner_id == learner_id),
        )
        .outerjoin(
            FSRSReviewState,
            and_(FSRSReviewState.knowledge_point_id == KnowledgePoint.id, FSRSReviewState.learner_id == learner_id),
        )
        .where(KnowledgePoint.status == "published")
        .order_by(GrammarCanDoProfile.cefr_level, GrammarCanDoProfile.category, GrammarCanDoProfile.subcategory)
    )
    return result.all()


@router.get("/map", response_model=GrammarMapResponse)
async def get_grammar_map(
    learner_id: uuid.UUID,
    _: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> GrammarMapResponse:
    rows = await _grammar_rows(db, learner_id)
    point_ids = [point.id for _, point, _, _ in rows]
    evidence_by_point: dict[uuid.UUID, list[AssessmentEvidence]] = {point_id: [] for point_id in point_ids}
    if point_ids:
        evidence_result = await db.execute(
            select(AssessmentEvidence)
            .where(AssessmentEvidence.learner_id == learner_id, AssessmentEvidence.knowledge_point_id.in_(point_ids), AssessmentEvidence.invalidated_at.is_(None))
            .order_by(AssessmentEvidence.created_at)
        )
        for item in evidence_result.scalars().all():
            evidence_by_point[item.knowledge_point_id].append(item)
    now = datetime.now(timezone.utc)
    points = [_point_payload(profile, point, state, fsrs, evidence_by_point[point.id], now) for profile, point, state, fsrs in rows]
    matrix_values: dict[tuple[str, str], dict[str, int]] = {}
    for point in points:
        counts = matrix_values.setdefault((point.category, point.cefr_level), {key: 0 for key in ("stable", "forming", "review", "repeated_failure", "no_evidence")})
        counts[point.status] += 1
    matrix = [GrammarMatrixCellResponse(category=category, cefr_level=cefr, total=sum(counts.values()), **counts) for (category, cefr), counts in sorted(matrix_values.items())]
    profile_rows = [profile for profile, _, _, _ in rows]
    catalog_version = profile_rows[0].catalog_version if profile_rows else "unavailable"
    source_url = profile_rows[0].source_url if profile_rows else None
    source_attribution = profile_rows[0].source_attribution if profile_rows else None
    return GrammarMapResponse(
        catalog_version=catalog_version,
        total_count=len(points),
        example_count=sum(len(profile.positive_examples or []) for profile in profile_rows),
        source_url=source_url,
        source_attribution=source_attribution,
        points=points,
        matrix=matrix,
    )


@router.get("/can-do/{point_id}", response_model=GrammarCanDoDetailResponse)
async def get_grammar_can_do_detail(
    learner_id: uuid.UUID,
    point_id: uuid.UUID,
    _: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> GrammarCanDoDetailResponse:
    row_result = await db.execute(
        select(GrammarCanDoProfile, KnowledgePoint, LearnerKnowledgeState, FSRSReviewState)
        .join(KnowledgePoint, KnowledgePoint.id == GrammarCanDoProfile.knowledge_point_id)
        .outerjoin(LearnerKnowledgeState, and_(LearnerKnowledgeState.knowledge_point_id == point_id, LearnerKnowledgeState.learner_id == learner_id))
        .outerjoin(FSRSReviewState, and_(FSRSReviewState.knowledge_point_id == point_id, FSRSReviewState.learner_id == learner_id))
        .where(KnowledgePoint.id == point_id, KnowledgePoint.status == "published")
    )
    row = row_result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Grammar can-do point not found")
    profile, point, state, fsrs = row
    evidence_result = await db.execute(
        select(AssessmentEvidence, KnowledgeStateUpdate)
        .outerjoin(KnowledgeStateUpdate, KnowledgeStateUpdate.evidence_id == AssessmentEvidence.id)
        .where(AssessmentEvidence.learner_id == learner_id, AssessmentEvidence.knowledge_point_id == point_id, AssessmentEvidence.invalidated_at.is_(None))
        .order_by(AssessmentEvidence.created_at.desc())
        .limit(20)
    )
    evidence_rows = evidence_result.all()
    evidence = [item for item, _ in reversed(evidence_rows)]
    base = _point_payload(profile, point, state, fsrs, evidence, datetime.now(timezone.utc))
    fsrs_payload = None if fsrs is None else {
        "difficulty": fsrs.difficulty,
        "stability_days": fsrs.stability_days,
        "retrievability": _retrievability(fsrs, datetime.now(timezone.utc)),
        "last_rating": fsrs.last_rating,
        "review_count": fsrs.review_count,
        "last_review_at": fsrs.last_review_at,
        "next_review_at": fsrs.next_review_at,
        "model_version": fsrs.model_version,
    }
    recent = [GrammarEvidenceResponse(id=item.id, occurred_at=item.created_at, mode=item.evidence_mode, outcome_score=item.outcome_score, independent=item.independent, semantic_confidence=item.semantic_confidence, decision_reason=item.decision_reason, mastery_before=update.previous_mastery if update else None, mastery_after=update.new_mastery if update else None, item_difficulty=item.item_difficulty_prior) for item, update in evidence_rows]
    return GrammarCanDoDetailResponse(**base.model_dump(), success_criteria=profile.success_criteria, failure_criteria=profile.failure_criteria, positive_examples=profile.positive_examples, negative_examples=profile.negative_examples, prerequisites=profile.prerequisites, fsrs=fsrs_payload, recent_evidence=recent)


def _cache_key(topic_id: str, prompt_version: str, prompt_hash: str) -> str:
    return f"grammar:html:{prompt_version}:{topic_id}:{prompt_hash}"


def _normalize_path_value(value: str, name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise HTTPException(status_code=422, detail=f"{name} must not be blank")
    if any(char in stripped for char in (" ", "\n", "\r", "\t", ":")):
        raise HTTPException(status_code=422, detail=f"{name} contains invalid characters")
    return stripped


@router.get("/topics/{topic_id}/html-cache", response_model=GrammarHtmlCacheResponse)
async def get_grammar_html_cache(
    learner_id: uuid.UUID,
    topic_id: str,
    prompt_hash: str = Query(min_length=8, max_length=128),
    prompt_version: str = Query(min_length=1, max_length=50),
    db: AsyncSession = Depends(get_db_session),
) -> GrammarHtmlCacheResponse:
    await _ensure_learner_exists(db, learner_id)
    normalized_topic_id = _normalize_path_value(topic_id, "topic_id")
    redis = await get_redis()
    raw = await redis.get(_cache_key(normalized_topic_id, prompt_version, prompt_hash))
    if raw is None:
        return GrammarHtmlCacheResponse(
            topic_id=normalized_topic_id,
            prompt_hash=prompt_hash,
            prompt_version=prompt_version,
            cached=False,
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {"html": raw}
    return GrammarHtmlCacheResponse(
        topic_id=normalized_topic_id,
        prompt_hash=prompt_hash,
        prompt_version=prompt_version,
        cached=True,
        html=payload.get("html") if isinstance(payload.get("html"), str) else raw,
        source=payload.get("source") if isinstance(payload.get("source"), str) else None,
        stored_at=datetime.fromisoformat(payload["stored_at"])
        if isinstance(payload.get("stored_at"), str)
        else None,
    )


@router.put("/topics/{topic_id}/html-cache", response_model=GrammarHtmlCacheResponse)
async def store_grammar_html_cache(
    learner_id: uuid.UUID,
    topic_id: str,
    body: StoreGrammarHtmlCacheRequest,
    db: AsyncSession = Depends(get_db_session),
) -> GrammarHtmlCacheResponse:
    await _ensure_learner_exists(db, learner_id)
    normalized_topic_id = _normalize_path_value(topic_id, "topic_id")
    stored_at = datetime.now(timezone.utc)
    payload = {
        "html": body.html,
        "source": body.source,
        "stored_at": stored_at.isoformat(),
    }
    redis = await get_redis()
    await redis.set(
        _cache_key(normalized_topic_id, body.prompt_version, body.prompt_hash),
        json.dumps(payload, ensure_ascii=False),
    )
    return GrammarHtmlCacheResponse(
        topic_id=normalized_topic_id,
        prompt_hash=body.prompt_hash,
        prompt_version=body.prompt_version,
        cached=True,
        html=body.html,
        source=body.source,
        stored_at=stored_at,
    )


@router.delete("/topics/{topic_id}/html-cache", status_code=204)
async def delete_grammar_html_cache(
    learner_id: uuid.UUID,
    topic_id: str,
    prompt_hash: str = Query(min_length=8, max_length=128),
    prompt_version: str = Query(min_length=1, max_length=50),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await _ensure_learner_exists(db, learner_id)
    normalized_topic_id = _normalize_path_value(topic_id, "topic_id")
    redis = await get_redis()
    await redis.delete(_cache_key(normalized_topic_id, prompt_version, prompt_hash))
