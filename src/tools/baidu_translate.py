import asyncio
import hashlib
import random
import secrets
import time

import httpx

from src.config import settings

ENDPOINT = "https://fanyi-api.baidu.com/ait/api/aiTextTranslate"
GENERAL_ENDPOINT = "https://fanyi-api.baidu.com/api/trans/vip/translate"
_RETRYABLE_CODES = {"52001", "52002", "54003", "54005", "59004"}


class BaiduTranslateError(RuntimeError):
    pass


class _RateLimiter:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def wait(self) -> None:
        async with self._lock:
            interval = 1.0 / max(settings.baidu_translate_qps, 0.1)
            now = time.monotonic()
            if now < self._next_request_at:
                await asyncio.sleep(self._next_request_at - now)
            self._next_request_at = time.monotonic() + interval


_RATE_LIMITER = _RateLimiter()
_AI_ENDPOINT_AVAILABLE: bool | None = None


def is_configured() -> bool:
    return bool(
        settings.baidu_translate_app_id
        and (settings.baidu_translate_api_key or settings.baidu_translate_app_key)
    )


def _translations(payload: dict, expected: int) -> list[str]:
    rows = payload.get("trans_result") or []
    translated = [str(row.get("dst") or "").strip() for row in rows]
    translated = [value for value in translated if value]
    if len(translated) == expected:
        return translated
    if len(translated) == 1:
        lines = [line.strip() for line in translated[0].splitlines() if line.strip()]
        if len(lines) == expected:
            return lines
    raise BaiduTranslateError("Baidu translation result count did not match the request")


async def translate_english_to_chinese(texts: list[str]) -> list[str]:
    global _AI_ENDPOINT_AVAILABLE

    if not texts:
        return []
    if not is_configured():
        raise BaiduTranslateError("Baidu translation APPID/API key are not configured")

    if settings.baidu_translate_api_key and _AI_ENDPOINT_AVAILABLE is not False:
        try:
            translated = await _translate_with_api_key(texts)
        except BaiduTranslateError as exc:
            if not settings.baidu_translate_app_key or "服务未开通" not in str(exc):
                raise
            _AI_ENDPOINT_AVAILABLE = False
        else:
            _AI_ENDPOINT_AVAILABLE = True
            return translated
    return await _translate_with_sign(texts)


async def _translate_with_api_key(texts: list[str]) -> list[str]:
    body = {
        "appid": settings.baidu_translate_app_id,
        "from": "en",
        "to": "zh",
        "q": "\n".join(texts),
        "model_type": "nmt",
    }
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.baidu_translate_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for attempt in range(settings.baidu_translate_max_retries + 1):
            await _RATE_LIMITER.wait()
            try:
                response = await client.post(ENDPOINT, headers=headers, json=body)
                payload = response.json()
            except (httpx.HTTPError, TypeError, ValueError) as exc:
                if attempt >= settings.baidu_translate_max_retries:
                    raise BaiduTranslateError("Baidu translation request failed") from exc
                await asyncio.sleep((2**attempt) + random.random())
                continue

            error_code = str(payload.get("error_code") or "")
            retryable = response.status_code == 429 or response.status_code >= 500
            retryable = retryable or error_code in _RETRYABLE_CODES
            if retryable and attempt < settings.baidu_translate_max_retries:
                await asyncio.sleep((2**attempt) + random.random())
                continue
            if response.status_code != 200 or error_code:
                message = str(payload.get("error_msg") or f"HTTP {response.status_code}")
                raise BaiduTranslateError(f"Baidu translation rejected the request: {message}")
            return _translations(payload, len(texts))

    raise BaiduTranslateError("Baidu translation retries exhausted")


async def _translate_with_sign(texts: list[str]) -> list[str]:
    query = "\n".join(texts)
    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for attempt in range(settings.baidu_translate_max_retries + 1):
            salt = secrets.token_hex(8)
            raw_sign = (
                f"{settings.baidu_translate_app_id}{query}{salt}"
                f"{settings.baidu_translate_app_key}"
            )
            form = {
                "appid": settings.baidu_translate_app_id,
                "q": query,
                "from": "en",
                "to": "zh",
                "salt": salt,
                "sign": hashlib.md5(raw_sign.encode("utf-8")).hexdigest(),  # noqa: S324
            }
            await _RATE_LIMITER.wait()
            try:
                response = await client.post(
                    GENERAL_ENDPOINT,
                    headers={"Accept": "application/json"},
                    data=form,
                )
                payload = response.json()
            except (httpx.HTTPError, TypeError, ValueError) as exc:
                if attempt >= settings.baidu_translate_max_retries:
                    raise BaiduTranslateError("Baidu general translation request failed") from exc
                await asyncio.sleep((2**attempt) + random.random())
                continue

            error_code = str(payload.get("error_code") or "")
            retryable = response.status_code == 429 or response.status_code >= 500
            retryable = retryable or error_code in _RETRYABLE_CODES
            if retryable and attempt < settings.baidu_translate_max_retries:
                await asyncio.sleep((2**attempt) + random.random())
                continue
            if response.status_code != 200 or error_code:
                message = str(payload.get("error_msg") or f"HTTP {response.status_code}")
                raise BaiduTranslateError(
                    f"Baidu general translation rejected the request: {message}"
                )
            return _translations(payload, len(texts))

    raise BaiduTranslateError("Baidu general translation retries exhausted")
