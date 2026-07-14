import pytest

from src.tools.catalog import ToolCatalogManager
from src.tools.types import ToolExecutionInput


@pytest.mark.asyncio
async def test_catalog_refresh_builds_versioned_snapshot():
    manager = ToolCatalogManager()

    view = await manager.refresh()

    assert view.tool_count == 13
    assert view.enabled_count == 13
    assert view.revision != "uninitialized"
    assert all(tool.version and tool.spec_hash for tool in view.tools)


@pytest.mark.asyncio
async def test_catalog_resolver_is_default_deny_and_honors_lifecycle():
    manager = ToolCatalogManager()
    await manager.initialize()
    manager.set_enabled("memory.write", False)

    resolution = manager.resolve(["exercise.grade", "memory.write"])
    decisions = {item.name: item for item in resolution.items}

    assert decisions["exercise.grade"].allowed is True
    assert decisions["memory.write"].allowed is False
    assert decisions["memory.write"].reason == "disabled"
    assert decisions["rag.retrieve"].reason == "not_in_task_allowlist"


@pytest.mark.asyncio
async def test_gateway_rejects_tool_outside_task_allowlist_without_calling_handler():
    manager = ToolCatalogManager()
    await manager.initialize()

    result = await manager.execute(
        ToolExecutionInput(
            tool_name="memory.write",
            payload={"event": "test"},
            allowed_tools=["exercise.grade"],
        )
    )

    assert result.status == "failed"
    assert result.error_code == "not_allowed"
    assert result.catalog_revision == manager.view().revision


@pytest.mark.asyncio
async def test_gateway_rejects_stale_catalog_revision():
    manager = ToolCatalogManager()
    await manager.initialize()

    result = await manager.execute(
        ToolExecutionInput(
            tool_name="exercise.grade",
            payload={},
            allowed_tools=["exercise.grade"],
            catalog_revision="stale",
        )
    )

    assert result.status == "failed"
    assert result.error_code == "catalog_revision_mismatch"
