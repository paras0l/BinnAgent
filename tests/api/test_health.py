from unittest.mock import AsyncMock

import pytest

from src.api import deps
from src.main import app
from src.providers.router import ModelRouter


class TestModelHealth:
    @pytest.mark.asyncio
    async def test_model_health_endpoint(self, client):
        mock_router = AsyncMock(spec=ModelRouter)
        mock_router.health_check = AsyncMock(
            return_value={"ollama": {"reachable": True, "chat_model": {"available": True}}}
        )

        app.dependency_overrides[deps.get_model_router] = lambda: mock_router
        try:
            response = await client.get("/internal/model/health")
            assert response.status_code == 200
            data = response.json()
            assert "ollama" in data
            assert data["ollama"]["reachable"] is True
        finally:
            app.dependency_overrides.clear()
