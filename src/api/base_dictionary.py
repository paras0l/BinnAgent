from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.base_dictionary.pipeline import canonical_key
from src.base_dictionary.service import get_entry
from src.models.base_dictionary import BaseDictionaryEntry

router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])


class DictionarySearchItem(BaseModel):
    canonical_key: str
    lemma: str
    entry_kind: str
    frequency_rank: int
    parts_of_speech: list[str] = Field(default_factory=list)
    short_definition_en: str | None = None


class DictionaryEntryResponse(BaseModel):
    id: str
    canonical_key: str
    lemma: str
    entry_kind: str
    frequency_zipf: float
    frequency_rank: int
    parts_of_speech: list[str]
    pronunciations: list[dict[str, Any]]
    forms: list[str]
    senses: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    examples: list[dict[str, Any]]
    source_attribution: dict[str, Any]
    build_version: str


@router.get("/search", response_model=list[DictionarySearchItem])
async def search_dictionary(
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> list[DictionarySearchItem]:
    key = canonical_key(q)
    result = await db.execute(
        select(BaseDictionaryEntry)
        .where(
            BaseDictionaryEntry.active.is_(True),
            or_(
                BaseDictionaryEntry.canonical_key == key,
                BaseDictionaryEntry.canonical_key.startswith(key),
            ),
        )
        .order_by(
            (BaseDictionaryEntry.canonical_key == key).desc(),
            BaseDictionaryEntry.frequency_rank,
        )
        .limit(limit)
    )
    return [
        DictionarySearchItem(
            canonical_key=entry.canonical_key,
            lemma=entry.lemma,
            entry_kind=entry.entry_kind,
            frequency_rank=entry.frequency_rank,
            parts_of_speech=entry.parts_of_speech,
            short_definition_en=(entry.senses[0].get("definition_en") if entry.senses else None),
        )
        for entry in result.scalars().all()
    ]


@router.get("/entries/{term:path}", response_model=DictionaryEntryResponse)
async def dictionary_entry(
    term: str,
    db: AsyncSession = Depends(get_db_session),
) -> DictionaryEntryResponse:
    payload = await get_entry(db, term)
    if payload is None:
        raise HTTPException(status_code=404, detail="Dictionary entry not found")
    return DictionaryEntryResponse(**payload)
