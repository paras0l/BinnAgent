import json
from typing import Any

import httpx

from src.config import settings
from src.models.group_learning import GroupLearningSource


class FeishuMcpClientError(RuntimeError):
    pass


class HttpFeishuMcpClient:
    def __init__(
        self,
        url: str,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self._transport = transport
        self._session_id: str | None = None
        self._initialized = False
        self._request_id = 0

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_initialized()
        result = await self._json_rpc(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )
        return _tool_result_payload(result)

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        await self._json_rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "BinnAgent", "version": "0.1.0"},
            },
        )
        await self._notification("notifications/initialized", {})
        self._initialized = True

    async def _json_rpc(self, method: str, params: dict[str, Any]) -> Any:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        data = await self._post(payload)
        if "error" in data:
            raise FeishuMcpClientError(_error_message(data["error"]))
        return data.get("result", {})

    async def _notification(self, method: str, params: dict[str, Any]) -> None:
        await self._post({"jsonrpc": "2.0", "method": method, "params": params}, allow_empty=True)

    async def _post(self, payload: dict[str, Any], *, allow_empty: bool = False) -> dict[str, Any]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2025-06-18",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        timeout = httpx.Timeout(self.timeout_seconds, connect=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await client.post(self.url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise FeishuMcpClientError(f"Failed to call Feishu MCP: {exc}") from exc
        if session_id := response.headers.get("Mcp-Session-Id"):
            self._session_id = session_id
        if allow_empty and response.status_code in {200, 202, 204} and not response.content:
            return {}
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise FeishuMcpClientError(
                f"Feishu MCP HTTP {response.status_code}: {response.text[:300]}"
            ) from exc
        if not response.content:
            return {}
        return _decode_response(response)


class FeishuOpenApiClient:
    def __init__(self, app_id: str, app_secret: str, *, base_url: str = "https://open.feishu.cn"):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self._tenant_access_token: str | None = None

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "im.v1.message.list":
            return await self._get("/open-apis/im/v1/messages", params=arguments.get("params") or {})
        if tool_name == "im.v1.message.create":
            params = arguments.get("params") or {}
            data = arguments.get("data") or {}
            return await self._post("/open-apis/im/v1/messages", params=params, json_body=data)
        if tool_name == "im.v1.chat.list":
            return await self._get("/open-apis/im/v1/chats", params=arguments.get("params") or {})
        if tool_name == "im.v1.chatMembers.get":
            path = arguments.get("path") or {}
            chat_id = path.get("chat_id")
            if not chat_id:
                raise FeishuMcpClientError("chat_id is required for im.v1.chatMembers.get")
            return await self._get(
                f"/open-apis/im/v1/chats/{chat_id}/members",
                params=arguments.get("params") or {},
            )
        raise FeishuMcpClientError(f"OpenAPI fallback does not support tool {tool_name}")

    async def _get(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        token = await self._tenant_token()
        timeout = httpx.Timeout(30.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params={key: value for key, value in params.items() if value is not None},
            )
        return self._response_data(response)

    async def _post(
        self,
        path: str,
        *,
        params: dict[str, Any],
        json_body: dict[str, Any],
    ) -> dict[str, Any]:
        token = await self._tenant_token()
        timeout = httpx.Timeout(30.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params={key: value for key, value in params.items() if value is not None},
                json=json_body,
            )
        return self._response_data(response)

    async def _tenant_token(self) -> str:
        if self._tenant_access_token:
            return self._tenant_access_token
        timeout = httpx.Timeout(20.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
        data = self._response_data(response)
        token = data.get("tenant_access_token")
        if not isinstance(token, str) or not token:
            raise FeishuMcpClientError("Feishu OpenAPI did not return tenant_access_token")
        self._tenant_access_token = token
        return token

    def _response_data(self, response: httpx.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise FeishuMcpClientError(
                f"Feishu OpenAPI HTTP {response.status_code}: {response.text[:300]}"
            ) from exc
        payload = response.json()
        if not isinstance(payload, dict):
            raise FeishuMcpClientError("Feishu OpenAPI response must be a JSON object")
        if payload.get("code") not in {0, None}:
            raise FeishuMcpClientError(json.dumps(payload, ensure_ascii=False))
        data = payload.get("data")
        return data if isinstance(data, dict) else payload


class FallbackFeishuClient:
    def __init__(self, primary: HttpFeishuMcpClient | None, fallback: FeishuOpenApiClient | None):
        self.primary = primary
        self.fallback = fallback

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.primary is not None:
            try:
                return await self.primary.call_tool(tool_name, arguments)
            except FeishuMcpClientError:
                if self.fallback is None:
                    raise
        if self.fallback is None:
            raise FeishuMcpClientError("No Feishu MCP or OpenAPI client is configured")
        return await self.fallback.call_tool(tool_name, arguments)


async def feishu_mcp_client_from_settings(
    source: GroupLearningSource,
) -> FallbackFeishuClient | HttpFeishuMcpClient | FeishuOpenApiClient | None:
    primary: HttpFeishuMcpClient | None = None
    fallback: FeishuOpenApiClient | None = None
    if settings.feishu_mcp_enabled:
        if settings.feishu_mcp_transport != "http":
            raise FeishuMcpClientError("Only HTTP Feishu MCP transport is supported by BinnAgent")
        if not settings.feishu_mcp_url:
            raise FeishuMcpClientError("BINN_FEISHU_MCP_URL is required when Feishu MCP is enabled")
        primary = HttpFeishuMcpClient(settings.feishu_mcp_url)
    if settings.feishu_openapi_fallback_enabled and settings.feishu_app_id and settings.feishu_app_secret:
        fallback = FeishuOpenApiClient(settings.feishu_app_id, settings.feishu_app_secret)
    if primary and fallback:
        return FallbackFeishuClient(primary, fallback)
    if primary:
        return primary
    if fallback:
        return fallback
    if not settings.feishu_mcp_enabled:
        return None
    return None


def _decode_response(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    text = response.text.strip()
    if "text/event-stream" in content_type or text.startswith("event:") or text.startswith("data:"):
        return _decode_sse(text)
    data = response.json()
    if not isinstance(data, dict):
        raise FeishuMcpClientError("MCP response must be a JSON object")
    return data


def _decode_sse(text: str) -> dict[str, Any]:
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        raw_data = line.removeprefix("data:").strip()
        if not raw_data or raw_data == "[DONE]":
            continue
        data = json.loads(raw_data)
        if isinstance(data, dict):
            return data
    raise FeishuMcpClientError("MCP SSE response did not include JSON data")


def _tool_result_payload(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise FeishuMcpClientError("MCP tool result must be a JSON object")
    is_error = bool(result.get("isError"))
    if structured := result.get("structuredContent"):
        if isinstance(structured, dict):
            if is_error:
                raise FeishuMcpClientError(f"MCP tool error: {structured}")
            return structured
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            if is_error or text.startswith("MCP error"):
                raise FeishuMcpClientError(text)
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
            if isinstance(parsed, dict):
                return parsed
            return {"data": parsed}
    return result


def _error_message(error: Any) -> str:
    if isinstance(error, dict):
        message = error.get("message")
        code = error.get("code")
        return f"MCP error {code}: {message}" if code is not None else f"MCP error: {message}"
    return f"MCP error: {error}"
