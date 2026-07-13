from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import require_debug_access
from src.tools.catalog import tool_catalog
from src.tools.types import (
    ToolCatalogView,
    ToolResolutionRequest,
    ToolResolutionView,
    ToolSpec,
)

router = APIRouter(
    prefix="/api/tools",
    tags=["tools"],
    dependencies=[Depends(require_debug_access)],
)


@router.get("", response_model=list[ToolSpec])
async def list_tools() -> list[ToolSpec]:
    await tool_catalog.initialize()
    return tool_catalog.list_tools()


@router.get("/catalog", response_model=ToolCatalogView)
async def get_tool_catalog() -> ToolCatalogView:
    await tool_catalog.initialize()
    return tool_catalog.view()


@router.post("/refresh", response_model=ToolCatalogView)
async def refresh_tool_catalog() -> ToolCatalogView:
    return await tool_catalog.refresh()


@router.post("/{tool_name}/enable", response_model=ToolSpec)
async def enable_tool(tool_name: str) -> ToolSpec:
    return _set_enabled(tool_name, True)


@router.post("/{tool_name}/disable", response_model=ToolSpec)
async def disable_tool(tool_name: str) -> ToolSpec:
    return _set_enabled(tool_name, False)


@router.post("/resolve", response_model=ToolResolutionView)
async def resolve_tools(request: ToolResolutionRequest) -> ToolResolutionView:
    await tool_catalog.initialize()
    return tool_catalog.resolve(request.allowed_tools)


def _set_enabled(tool_name: str, enabled: bool) -> ToolSpec:
    try:
        return tool_catalog.set_enabled(tool_name, enabled)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        ) from exc
