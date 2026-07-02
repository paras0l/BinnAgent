from sqlalchemy.ext.asyncio import AsyncSession

from src.tools.registry import build_default_tool_registry
from src.tools.types import ToolExecutionInput, ToolExecutionResult


async def execute_tool(
    input: ToolExecutionInput,
    *,
    db: AsyncSession | None = None,
) -> ToolExecutionResult:
    return await build_default_tool_registry(db=db).execute(input)


def list_default_tools() -> list:
    return build_default_tool_registry().list_tools()
