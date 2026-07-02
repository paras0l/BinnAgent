from fastapi import APIRouter

from src.tools.executor import list_default_tools
from src.tools.types import ToolSpec

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("", response_model=list[ToolSpec])
async def list_tools() -> list[ToolSpec]:
    return list_default_tools()
