from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.config import settings
from src.main import app
from src.models.base_dictionary import BaseDictionaryBuild


@pytest.fixture(autouse=True)
def debug_settings_guard():
    original = (settings.debug_console_enabled, settings.debug_console_token)
    yield
    settings.debug_console_enabled, settings.debug_console_token = original
    app.dependency_overrides.clear()


@pytest.fixture
def mock_session():
    session = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    return session


def _build_result(build):
    result = MagicMock()
    result.scalars.return_value.first.return_value = build
    return result


def _one(values):
    result = MagicMock()
    result.one.return_value = values
    return result


def _rows(values):
    result = MagicMock()
    result.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_base_dictionary_metadata_reports_build_and_coverage(client, mock_session):
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    completed_at = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
    build = BaseDictionaryBuild(
        version="2026-07-12.1",
        status="published",
        source_manifest={"kaikki_wiktionary": {"version": "2026-07-09"}},
        selection_config={"word_limit": 10000, "phrase_limit": 2000},
        statistics={"entries": 11800},
        started_at=completed_at,
        completed_at=completed_at,
    )
    mock_session.execute.side_effect = [
        _build_result(build),
        _one((11800, 26500, 9000, 11200)),
        _rows([("phrase", 1200), ("phrasal_verb", 600), ("word", 10000)]),
        _one((11700, 26000)),
    ]

    response = await client.get(
        "/api/debug/base-dictionary/metadata",
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["build"]["version"] == "2026-07-12.1"
    assert payload["entries"]["total"] == 11800
    assert payload["entries"]["by_kind"]["word"] == 10000
    assert payload["entries"]["example_coverage"] == pytest.approx(0.7627)
    assert payload["translations"]["sense_coverage"] == pytest.approx(0.9811)


@pytest.mark.asyncio
async def test_base_dictionary_metadata_requires_debug_access(client, mock_session):
    settings.debug_console_enabled = False

    response = await client.get("/api/debug/base-dictionary/metadata")

    assert response.status_code == 404
    mock_session.execute.assert_not_called()
