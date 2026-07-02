import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.recommendation.engine import RecommendationEngine
from src.recommendation.types import RecommendationInput, RecommendationPlan

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/daily-plan", response_model=RecommendationPlan)
async def get_daily_recommendation_plan(
    learner_id: uuid.UUID,
    current_curriculum_node_id: uuid.UUID | None = None,
    time_budget_minutes: int | None = Query(default=None, ge=1, le=240),
    mode_hint: str | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> RecommendationPlan:
    return await RecommendationEngine(db).build_daily_plan(
        RecommendationInput(
            learner_id=str(learner_id),
            current_curriculum_node_id=(
                str(current_curriculum_node_id) if current_curriculum_node_id else None
            ),
            time_budget_minutes=time_budget_minutes,
            mode_hint=mode_hint,
        )
    )
