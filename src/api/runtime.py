import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.runtime.episode import EpisodeRuntime
from src.runtime.schemas import EpisodeTraceView
from src.verification.report import VerificationService
from src.verification.types import VerificationReport

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.get("/episodes/{episode_id}", response_model=EpisodeTraceView)
async def get_runtime_episode(
    episode_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> EpisodeTraceView:
    try:
        return await EpisodeRuntime(db).get_episode_trace(episode_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="AgentEpisode not found") from exc


@router.get("/episodes/{episode_id}/verification", response_model=VerificationReport)
async def get_runtime_episode_verification(
    episode_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> VerificationReport:
    try:
        return await VerificationService(db).verify_episode(str(episode_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="AgentEpisode not found") from exc
