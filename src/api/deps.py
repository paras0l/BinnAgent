from collections.abc import AsyncGenerator
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import async_session_factory
from src.models.learner import Learner
from src.providers.router import ModelRouter, router
from src.security.ownership import CurrentUser, get_learner_for_user


LOCAL_DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_model_router() -> ModelRouter:
    return router


async def get_current_user(request: Request) -> CurrentUser:
    raw_user_id = request.headers.get("x-user-id") or request.headers.get("x-dev-user-id")
    if raw_user_id:
        try:
            return CurrentUser(
                user_id=uuid.UUID(raw_user_id.strip()),
                source="dev-header",
                allow_unclaimed_learners=False,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid current user",
            ) from exc

    return CurrentUser(
        user_id=LOCAL_DEV_USER_ID,
        source="local-dev",
        allow_unclaimed_learners=True,
    )


async def require_learner_access(
    learner_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Learner:
    return await get_learner_for_user(
        db,
        current_user.user_id,
        learner_id,
        allow_unclaimed_learners=current_user.allow_unclaimed_learners,
    )


async def get_current_learner(
    learner: Learner = Depends(require_learner_access),
) -> Learner:
    return learner


def require_debug_access(request: Request) -> None:
    if not settings.debug_console_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    origin = request.headers.get("origin")
    if origin and origin not in settings.debug_console_allowed_origins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    expected_token = settings.debug_console_token
    if not expected_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    token = _debug_token_from_request(request)
    if token != expected_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _debug_token_from_request(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value:
        return value.strip()
    header_token = request.headers.get("x-debug-token")
    return header_token.strip() if header_token else None
