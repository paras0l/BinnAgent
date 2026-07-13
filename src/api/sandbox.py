from typing import Any

from fastapi import APIRouter

from src.expression_lab.sandbox_permissions import sandbox_permissions

router = APIRouter(tags=["sandbox"])


@router.get("/api/sandbox-policy")
async def public_sandbox_policy() -> dict[str, Any]:
    """A non-secret policy snapshot used by chat-rendered interactive widgets."""
    return {"policy": sandbox_permissions().payload()}
