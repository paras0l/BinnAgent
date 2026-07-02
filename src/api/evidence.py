from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, require_debug_access
from src.evidence.resolver import EvidenceResolver
from src.evidence.types import EvidenceRef, EvidenceResolution

router = APIRouter(
    prefix="/api/evidence",
    tags=["evidence"],
    dependencies=[Depends(require_debug_access)],
)


class ResolveEvidenceRequest(BaseModel):
    refs: list[EvidenceRef]


class ResolveEvidenceResponse(BaseModel):
    resolutions: list[EvidenceResolution]


@router.post("/resolve", response_model=ResolveEvidenceResponse)
async def resolve_evidence(
    body: ResolveEvidenceRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ResolveEvidenceResponse:
    resolver = EvidenceResolver(db)
    return ResolveEvidenceResponse(
        resolutions=[await resolver.resolve_ref(ref) for ref in body.refs]
    )
