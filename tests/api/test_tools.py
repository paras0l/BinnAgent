import pytest

from src.config import settings
from src.main import app
from src.tools.catalog import tool_catalog


@pytest.fixture(autouse=True)
def tool_debug_settings():
    original = (settings.debug_console_enabled, settings.debug_console_token)
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    yield
    settings.debug_console_enabled, settings.debug_console_token = original
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_tool_catalog_lifecycle_and_resolution_api(client):
    await tool_catalog.refresh()
    headers = {"X-Debug-Token": "dev"}

    catalog_response = await client.get("/api/tools/catalog", headers=headers)
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()
    assert catalog["tool_count"] == 8
    assert catalog["revision"]

    disabled = await client.post("/api/tools/memory.write/disable", headers=headers)
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    resolved = await client.post(
        "/api/tools/resolve",
        headers=headers,
        json={"allowed_tools": ["memory.write", "exercise.grade"]},
    )
    assert resolved.status_code == 200
    decisions = {item["name"]: item for item in resolved.json()["items"]}
    assert decisions["memory.write"]["reason"] == "disabled"
    assert decisions["exercise.grade"]["allowed"] is True

    refreshed = await client.post("/api/tools/refresh", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["disabled_count"] == 1

    enabled = await client.post("/api/tools/memory.write/enable", headers=headers)
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True


@pytest.mark.asyncio
async def test_tool_catalog_requires_debug_access(client):
    settings.debug_console_enabled = False

    response = await client.get("/api/tools/catalog")

    assert response.status_code == 404
