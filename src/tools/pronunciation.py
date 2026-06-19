import asyncio
import time
from dataclasses import dataclass
from urllib.parse import quote, urlparse

import httpx


@dataclass(frozen=True)
class PronunciationAsset:
    accent: str
    phonetic: str | None
    audio_url: str | None
    provider: str
    kind: str


_CACHE: dict[tuple[str, str], tuple[float, list[PronunciationAsset]]] = {}
_CACHE_LOCK = asyncio.Lock()
_ALLOWED_AUDIO_HOSTS = {
    "api.dictionaryapi.dev",
    "ssl.gstatic.com",
    "dictionaryapi.dev",
}


def _accent_from_url(url: str, fallback: str) -> str:
    lowered = url.casefold()
    if "-uk" in lowered or "_gb_" in lowered:
        return "uk"
    if "-us" in lowered or "_us_" in lowered:
        return "us"
    return fallback


def _safe_audio_url(value: str) -> str | None:
    if not value:
        return None
    url = f"https:{value}" if value.startswith("//") else value
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_AUDIO_HOSTS:
        return None
    return url


async def lookup_pronunciations(word: str, accent: str = "uk") -> list[PronunciationAsset]:
    key = (word.casefold().strip(), accent)
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]
    endpoint = f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(key[0], safe='')}"
    assets: list[PronunciationAsset] = []
    try:
        timeout = httpx.Timeout(3.0, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.get(endpoint, headers={"Accept": "application/json"})
            if response.status_code == 200:
                payload = response.json()
                for entry in payload[:2]:
                    for phonetic in entry.get("phonetics", []):
                        audio_url = _safe_audio_url(phonetic.get("audio", ""))
                        if not audio_url:
                            continue
                        detected_accent = _accent_from_url(audio_url, accent)
                        assets.append(
                            PronunciationAsset(
                                accent=detected_accent,
                                phonetic=phonetic.get("text") or entry.get("phonetic"),
                                audio_url=audio_url,
                                provider="free_dictionary_api",
                                kind="recording",
                            )
                        )
    except (httpx.HTTPError, ValueError, TypeError):
        assets = []
    deduplicated = list({asset.audio_url: asset for asset in assets}.values())
    deduplicated.sort(key=lambda item: item.accent != accent)
    if not deduplicated:
        deduplicated = [
            PronunciationAsset(
                accent=accent,
                phonetic=None,
                audio_url=None,
                provider="browser_speech_synthesis",
                kind="tts_fallback",
            )
        ]
    async with _CACHE_LOCK:
        _CACHE[key] = (now + (86_400 if assets else 600), deduplicated)
    return deduplicated
