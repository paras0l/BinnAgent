import asyncio
import time
from dataclasses import dataclass, field
from urllib.parse import quote, urlparse

import httpx

DICTIONARY_ENDPOINT = "https://api.dictionaryapi.dev/api/v2/entries/en"
_CACHE_TTL_SECONDS = 86_400
_MAX_RETRIES = 2
_CACHE: dict[str, tuple[float, "FreeDictionaryEntry"]] = {}
_CACHE_LOCK = asyncio.Lock()
_ALLOWED_AUDIO_HOSTS = {
    "api.dictionaryapi.dev",
    "ssl.gstatic.com",
    "dictionaryapi.dev",
}


@dataclass(frozen=True)
class FreeDictionaryEntry:
    word: str
    phonetic: str | None
    meanings: list[dict[str, str]]
    examples: list[str]
    provider: str
    phonetic_uk: str | None = None
    phonetic_us: str | None = None
    audio_url: str | None = None
    audio_uk: str | None = None
    audio_us: str | None = None
    dictionary_senses: list[dict] = field(default_factory=list)
    word_forms: dict[str, list[str]] = field(default_factory=dict)
    dictionary_tags: list[str] = field(default_factory=list)


def _phonetic(payload: dict) -> str | None:
    if payload.get("phonetic"):
        return str(payload["phonetic"])
    for item in payload.get("phonetics") or []:
        if item.get("text"):
            return str(item["text"])
    return None


def _safe_audio_url(value: str) -> str | None:
    if not value:
        return None
    url = f"https:{value}" if value.startswith("//") else value
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_AUDIO_HOSTS:
        return None
    return url


def _accent_from_audio_url(url: str) -> str | None:
    lowered = url.casefold()
    if "-uk" in lowered or "_gb_" in lowered:
        return "uk"
    if "-us" in lowered or "_us_" in lowered:
        return "us"
    return None


def _pronunciation_fields(payload: dict) -> dict[str, str | None]:
    phonetic = _phonetic(payload)
    phonetic_uk: str | None = None
    phonetic_us: str | None = None
    audio_url: str | None = None
    audio_uk: str | None = None
    audio_us: str | None = None

    for item in payload.get("phonetics") or []:
        text = str(item.get("text") or "").strip() or None
        audio = _safe_audio_url(str(item.get("audio") or "").strip())
        accent = _accent_from_audio_url(audio or "")
        if text and accent == "uk" and phonetic_uk is None:
            phonetic_uk = text
        elif text and accent == "us" and phonetic_us is None:
            phonetic_us = text
        if audio and audio_url is None:
            audio_url = audio
        if audio and accent == "uk" and audio_uk is None:
            audio_uk = audio
        elif audio and accent == "us" and audio_us is None:
            audio_us = audio

    return {
        "phonetic": phonetic,
        "phonetic_uk": phonetic_uk,
        "phonetic_us": phonetic_us,
        "audio_url": audio_url,
        "audio_uk": audio_uk,
        "audio_us": audio_us,
    }


async def lookup_free_dictionary(word: str) -> FreeDictionaryEntry:
    key = " ".join(word.casefold().strip().split())
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]

    result = FreeDictionaryEntry(key, None, [], [], "free_dictionary_not_found")
    timeout = httpx.Timeout(6.0, connect=3.0)
    for attempt in range(_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                response = await client.get(
                    f"{DICTIONARY_ENDPOINT}/{quote(key, safe='')}",
                    headers={"Accept": "application/json"},
                )
                if response.status_code == 200:
                    entries = response.json()
                    if entries:
                        entry = entries[0]
                        pronunciation = _pronunciation_fields(entry)
                        selected: list[tuple[str, str]] = []
                        examples: list[str] = []
                        for meaning in entry.get("meanings") or []:
                            definitions = meaning.get("definitions") or []
                            if not definitions:
                                continue
                            definition = definitions[0]
                            text = str(definition.get("definition") or "").strip()
                            if text:
                                selected.append(
                                    (str(meaning.get("partOfSpeech") or "word"), text)
                                )
                            example = str(definition.get("example") or "").strip()
                            if example and example not in examples:
                                examples.append(example)
                            if len(selected) >= 3:
                                break
                        result = FreeDictionaryEntry(
                            word=str(entry.get("word") or word),
                            phonetic=pronunciation["phonetic"],
                            meanings=[
                                {
                                    "part_of_speech": part_of_speech,
                                    "definition": definition,
                                    "definition_zh": "",
                                }
                                for part_of_speech, definition in selected
                            ],
                            examples=examples[:3],
                            provider="free_dictionary_api",
                            phonetic_uk=pronunciation["phonetic_uk"],
                            phonetic_us=pronunciation["phonetic_us"],
                            audio_url=pronunciation["audio_url"],
                            audio_uk=pronunciation["audio_uk"],
                            audio_us=pronunciation["audio_us"],
                        )
                    break
                if response.status_code == 404:
                    break
        except (httpx.HTTPError, TypeError, ValueError):
            if attempt >= _MAX_RETRIES:
                result = FreeDictionaryEntry(key, None, [], [], "free_dictionary_error")
            else:
                await asyncio.sleep(0.5 * (attempt + 1))

    async with _CACHE_LOCK:
        _CACHE[key] = (now + _CACHE_TTL_SECONDS, result)
    return result


async def lookup_free_dictionary_batch(
    words: list[str], *, concurrency: int = 6
) -> dict[str, FreeDictionaryEntry]:
    semaphore = asyncio.Semaphore(concurrency)

    async def lookup(word: str) -> tuple[str, FreeDictionaryEntry]:
        async with semaphore:
            return word, await lookup_free_dictionary(word)

    return dict(await asyncio.gather(*(lookup(word) for word in words)))
