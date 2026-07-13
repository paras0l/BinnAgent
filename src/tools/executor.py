from sqlalchemy.ext.asyncio import AsyncSession

from src.tools.catalog import tool_catalog
from src.tools.types import ToolExecutionInput, ToolExecutionResult


async def execute_tool(
    input: ToolExecutionInput,
    *,
    db: AsyncSession | None = None,
) -> ToolExecutionResult:
    return await tool_catalog.execute(input, db=db)


def list_default_tools() -> list:
    return tool_catalog.list_tools()
