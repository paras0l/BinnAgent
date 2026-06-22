import asyncio
import time
from dataclasses import dataclass, field, replace
from urllib.parse import quote

import httpx

from src.tools.baidu_dictionary import is_configured as baidu_dictionary_is_configured
from src.tools.baidu_dictionary import lookup_baidu_dictionary_batch
from src.tools.baidu_translate import BaiduTranslateError, translate_english_to_chinese

DICTIONARY_ENDPOINT = "https://api.dictionaryapi.dev/api/v2/entries/en"
_CACHE_TTL_SECONDS = 86_400
_CACHE: dict[str, tuple[float, "FreeDictionaryEntry"]] = {}
_CACHE_LOCK = asyncio.Lock()


@dataclass(frozen=True)
class FreeDictionaryEntry:
    word: str
    phonetic: str | None
    meanings: list[dict[str, str]]
    examples: list[str]
    provider: str
    phonetic_uk: str | None = None
    phonetic_us: str | None = None
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


async def lookup_free_dictionary(word: str) -> FreeDictionaryEntry:
    key = " ".join(word.casefold().strip().split())
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]

    result = FreeDictionaryEntry(key, None, [], [], "free_dictionary_not_found")
    timeout = httpx.Timeout(6.0, connect=3.0)
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
                    selected: list[tuple[str, str]] = []
                    examples: list[str] = []
                    for meaning in entry.get("meanings") or []:
                        definitions = meaning.get("definitions") or []
                        if not definitions:
                            continue
                        definition = definitions[0]
                        text = str(definition.get("definition") or "").strip()
                        if text:
                            selected.append((str(meaning.get("partOfSpeech") or "word"), text))
                        example = str(definition.get("example") or "").strip()
                        if example and example not in examples:
                            examples.append(example)
                        if len(selected) >= 3:
                            break
                    try:
                        translations = await translate_english_to_chinese(
                            [definition for _, definition in selected]
                        )
                    except BaiduTranslateError:
                        translations = [""] * len(selected)
                        translation_provider = "baidu_translate_error"
                    else:
                        translation_provider = "baidu_translate"
                    meanings = [
                        {
                            "part_of_speech": part_of_speech,
                            "definition": definition,
                            "definition_zh": translated or "",
                        }
                        for (part_of_speech, definition), translated in zip(
                            selected, translations, strict=True
                        )
                    ]
                    result = FreeDictionaryEntry(
                        word=str(entry.get("word") or word),
                        phonetic=_phonetic(entry),
                        meanings=meanings,
                        examples=examples[:3],
                        provider=f"free_dictionary_api+{translation_provider}",
                    )
    except (httpx.HTTPError, TypeError, ValueError):
        result = FreeDictionaryEntry(key, None, [], [], "free_dictionary_error")

    if result.provider in {"free_dictionary_not_found", "free_dictionary_error"}:
        try:
            translated_word = (await translate_english_to_chinese([word]))[0]
        except (BaiduTranslateError, IndexError):
            pass
        else:
            result = FreeDictionaryEntry(
                word=word,
                phonetic=None,
                meanings=[
                    {
                        "part_of_speech": "word",
                        "definition": "",
                        "definition_zh": translated_word,
                    }
                ],
                examples=[],
                provider="baidu_translate_fallback",
            )

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

    entries = dict(await asyncio.gather(*(lookup(word) for word in words)))
    if not baidu_dictionary_is_configured():
        return entries
    rich_entries = await lookup_baidu_dictionary_batch(words, concurrency=min(concurrency, 3))
    for word, rich in rich_entries.items():
        if rich is None:
            continue
        base = entries[word]
        entries[word] = replace(
            base,
            phonetic=rich.phonetic_uk or rich.phonetic_us or base.phonetic,
            phonetic_uk=rich.phonetic_uk,
            phonetic_us=rich.phonetic_us,
            dictionary_senses=rich.senses,
            word_forms=rich.word_forms,
            dictionary_tags=rich.tags,
            provider=f"{rich.provider}+{base.provider}",
        )
    return entries
