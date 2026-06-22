import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from src.config import settings

TOKEN_ENDPOINT = "https://aip.baidubce.com/oauth/2.0/token"
DICTIONARY_ENDPOINT = "https://aip.baidubce.com/rpc/2.0/mt/texttrans-with-dict/v1"
_TOKEN_LOCK = asyncio.Lock()
_TOKEN: tuple[str, float] | None = None
_RATE_LOCK = asyncio.Lock()
_NEXT_REQUEST_AT = 0.0


class BaiduDictionaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class BaiduDictionaryEntry:
    word: str
    phonetic_uk: str | None
    phonetic_us: str | None
    senses: list[dict[str, Any]]
    word_forms: dict[str, list[str]]
    tags: list[str]
    english_definitions: list[dict[str, Any]]
    provider: str = "baidu_dictionary_api"


def is_configured() -> bool:
    return bool(settings.baidu_dictionary_api_key and settings.baidu_dictionary_secret_key)


async def _access_token(client: httpx.AsyncClient) -> str:
    global _TOKEN
    now = time.monotonic()
    if _TOKEN and _TOKEN[1] > now:
        return _TOKEN[0]
    async with _TOKEN_LOCK:
        now = time.monotonic()
        if _TOKEN and _TOKEN[1] > now:
            return _TOKEN[0]
        response = await client.post(
            TOKEN_ENDPOINT,
            params={
                "grant_type": "client_credentials",
                "client_id": settings.baidu_dictionary_api_key,
                "client_secret": settings.baidu_dictionary_secret_key,
            },
        )
        payload = response.json()
        token = payload.get("access_token")
        if response.status_code != 200 or not token:
            message = payload.get("error_description") or payload.get("error") or "token error"
            raise BaiduDictionaryError(f"Baidu dictionary authentication failed: {message}")
        expires_in = max(300, int(payload.get("expires_in") or 2_592_000))
        _TOKEN = (str(token), now + expires_in - 120)
        return str(token)


async def _wait_for_rate_limit() -> None:
    global _NEXT_REQUEST_AT
    async with _RATE_LOCK:
        interval = 1.0 / max(settings.baidu_dictionary_qps, 0.1)
        now = time.monotonic()
        if now < _NEXT_REQUEST_AT:
            await asyncio.sleep(_NEXT_REQUEST_AT - now)
        _NEXT_REQUEST_AT = time.monotonic() + interval


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _parse_entry(word: str, payload: dict[str, Any]) -> BaiduDictionaryEntry:
    result = payload.get("result") or {}
    rows = result.get("trans_result") or payload.get("trans_result") or []
    row = rows[0] if rows else {}
    dictionary = _as_dict(row.get("dict"))
    word_result = dictionary.get("word_result") or {}
    simple = word_result.get("simple_means") or {}
    symbols = simple.get("symbols") or []
    symbol = symbols[0] if symbols else {}
    senses = [
        {
            "part_of_speech": str(part.get("part") or "word"),
            "meanings_zh": [str(value) for value in part.get("means") or [] if value],
        }
        for part in symbol.get("parts") or []
        if part.get("means")
    ]
    exchange = {
        str(key): [str(value) for value in values if value]
        for key, values in (simple.get("exchange") or {}).items()
        if isinstance(values, list) and values
    }
    tag_groups = simple.get("tags") or {}
    tags = [
        str(value)
        for values in tag_groups.values()
        if isinstance(values, list)
        for value in values
        if value
    ]
    english_definitions: list[dict[str, Any]] = []
    for item in ((word_result.get("edict") or {}).get("item") or []):
        part_of_speech = str(item.get("pos") or "word")
        for group in item.get("tr_group") or []:
            definitions = [str(value) for value in group.get("tr") or [] if value]
            examples = [str(value) for value in group.get("example") or [] if value]
            for definition in definitions:
                english_definitions.append(
                    {
                        "part_of_speech": part_of_speech,
                        "definition": definition,
                        "examples": examples,
                    }
                )
    return BaiduDictionaryEntry(
        word=str(simple.get("word_name") or word),
        phonetic_uk=str(symbol.get("ph_en") or "").strip() or None,
        phonetic_us=str(symbol.get("ph_am") or "").strip() or None,
        senses=senses,
        word_forms=exchange,
        tags=list(dict.fromkeys(tags)),
        english_definitions=english_definitions,
    )


async def lookup_baidu_dictionary(word: str) -> BaiduDictionaryEntry:
    if not is_configured():
        raise BaiduDictionaryError("Baidu dictionary API credentials are not configured")
    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        token = await _access_token(client)
        attempts = max(1, settings.baidu_dictionary_max_retries + 1)
        for attempt in range(attempts):
            await _wait_for_rate_limit()
            response = await client.post(
                DICTIONARY_ENDPOINT,
                params={"access_token": token},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json={"q": word, "from": "en", "to": "zh"},
            )
            payload = response.json()
            message = str(payload.get("error_msg") or f"HTTP {response.status_code}")
            is_rate_limited = response.status_code == 429 or any(
                marker in message.casefold()
                for marker in ("qps", "rate limit", "request limit", "too many requests")
            )
            if response.status_code == 200 and not payload.get("error_code"):
                return _parse_entry(word, payload)
            if not is_rate_limited or attempt == attempts - 1:
                raise BaiduDictionaryError(f"Baidu dictionary lookup failed: {message}")
            await asyncio.sleep(max(1.0, 2.0**attempt))
    raise BaiduDictionaryError("Baidu dictionary lookup failed after retries")


async def lookup_baidu_dictionary_batch(
    words: list[str], *, concurrency: int = 3
) -> dict[str, BaiduDictionaryEntry | None]:
    semaphore = asyncio.Semaphore(concurrency)

    async def lookup(word: str) -> tuple[str, BaiduDictionaryEntry | None]:
        async with semaphore:
            try:
                return word, await lookup_baidu_dictionary(word)
            except BaiduDictionaryError:
                return word, None

    return dict(await asyncio.gather(*(lookup(word) for word in words)))
