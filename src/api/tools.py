from fastapi import APIRouter, Depends

from src.api.deps import require_debug_access
from src.tools.executor import list_default_tools
from src.tools.types import ToolSpec

router = APIRouter(
    prefix="/api/tools",
    tags=["tools"],
    dependencies=[Depends(require_debug_access)],
)


@router.get("", response_model=list[ToolSpec])
async def list_tools() -> list[ToolSpec]:
    return list_default_tools()
