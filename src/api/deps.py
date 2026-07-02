from collections.abc import AsyncGenerator

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import async_session_factory
from src.providers.router import ModelRouter, router


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
