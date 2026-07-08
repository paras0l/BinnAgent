import pytest

from src.config import settings
from src.providers.router import router as model_router


@pytest.fixture(autouse=True)
def debug_model_provider_settings_guard():
    original_debug_settings = (
        settings.debug_console_enabled,
        settings.debug_console_token,
        list(settings.debug_console_allowed_origins),
    )
    original_provider = model_router.default_provider
    try:
        yield
    finally:
        (
            settings.debug_console_enabled,
            settings.debug_console_token,
            settings.debug_console_allowed_origins,
        ) = original_debug_settings
        model_router.set_default_provider(original_provider)


@pytest.mark.asyncio
async def test_model_provider_debug_requires_debug_access(client) -> None:
    settings.debug_console_enabled = False

    response = await client.get("/api/debug/model/provider")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_model_provider_debug_switches_runtime_provider(client) -> None:
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"

    response = await client.patch(
        "/api/debug/model/provider",
        headers={"X-Debug-Token": "dev"},
        json={"provider": "longcat"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["active_provider"] == "longcat"
    assert data["rag_provider"] == "ollama"
    assert {provider["id"] for provider in data["providers"]} == {
        "ollama",
        "deepseek",
        "longcat",
    }


@pytest.mark.asyncio
async def test_model_provider_debug_rejects_unknown_provider(client) -> None:
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"

    response = await client.patch(
        "/api/debug/model/provider",
        headers={"X-Debug-Token": "dev"},
        json={"provider": "unknown"},
    )

    assert response.status_code == 400
