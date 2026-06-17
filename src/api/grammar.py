import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.cache import get_redis
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


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


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
