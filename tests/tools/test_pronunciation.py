from unittest.mock import AsyncMock

import pytest

from src.tools import pronunciation


class _Response:
    status_code = 200

    def json(self):
        return [
            {
                "phonetic": "/həˈləʊ/",
                "phonetics": [
                    {
                        "text": "/həˈləʊ/",
                        "audio": "//ssl.gstatic.com/dictionary/static/sounds/hello--_gb_1.mp3",
                    },
                    {"text": "/həˈloʊ/", "audio": "http://unsafe.example/hello.mp3"},
                ],
            }
        ]


class _Client:
    def __init__(self, **kwargs):
        self.get = AsyncMock(return_value=_Response())

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


@pytest.mark.asyncio
async def test_lookup_keeps_only_allowlisted_https_audio(monkeypatch) -> None:
    pronunciation._CACHE.clear()
    monkeypatch.setattr(pronunciation.httpx, "AsyncClient", _Client)

    assets = await pronunciation.lookup_pronunciations("hello", "uk")

    assert len(assets) == 1
    assert assets[0].accent == "uk"
    assert assets[0].audio_url.startswith("https://ssl.gstatic.com/")
    assert assets[0].kind == "recording"


@pytest.mark.asyncio
async def test_lookup_falls_back_to_browser_speech(monkeypatch) -> None:
    pronunciation._CACHE.clear()

    class _FailingClient(_Client):
        async def __aenter__(self):
            raise pronunciation.httpx.ConnectError("offline")

    monkeypatch.setattr(pronunciation.httpx, "AsyncClient", _FailingClient)

    [asset] = await pronunciation.lookup_pronunciations("offline", "us")

    assert asset.kind == "tts_fallback"
    assert asset.accent == "us"
    assert asset.audio_url is None
