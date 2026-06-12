from fastapi import APIRouter, Depends

from src.api.deps import get_model_router
from src.providers.router import ModelRouter

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/model/health")
async def model_health(
    model_router: ModelRouter = Depends(get_model_router),
) -> dict:
    return await model_router.health_check()
