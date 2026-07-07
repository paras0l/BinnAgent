import json

import httpx
import pytest

from src.group_learning.feishu_mcp_client import (
    FallbackFeishuClient,
    FeishuMcpClientError,
    HttpFeishuMcpClient,
)


@pytest.mark.asyncio
async def test_http_feishu_mcp_client_initializes_and_calls_tool():
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        if payload["method"] == "initialize":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": payload["id"], "result": {"protocolVersion": "2025-06-18"}},
                headers={"Mcp-Session-Id": "session-1"},
            )
        if payload["method"] == "notifications/initialized":
            assert request.headers["Mcp-Session-Id"] == "session-1"
            return httpx.Response(202)
        if payload["method"] == "tools/call":
            assert request.headers["Mcp-Session-Id"] == "session-1"
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({"data": {"items": [{"message_id": "om_1"}]}}),
                            }
                        ]
                    },
                },
            )
        return httpx.Response(404)

    client = HttpFeishuMcpClient(
        "http://mcp.test/mcp",
        transport=httpx.MockTransport(handler),
    )

    result = await client.call_tool("im.v1.message.list", {"container_id": "oc_1"})

    assert result["data"]["items"][0]["message_id"] == "om_1"
    assert [call["method"] for call in calls] == [
        "initialize",
        "notifications/initialized",
        "tools/call",
    ]


@pytest.mark.asyncio
async def test_http_feishu_mcp_client_decodes_sse_tool_result():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": {}})
        if payload["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            content=(
                'event: message\n'
                'data: {"jsonrpc":"2.0","id":2,"result":{"structuredContent":{"data":{"items":[]}}}}\n\n'
            ),
            headers={"content-type": "text/event-stream"},
        )

    client = HttpFeishuMcpClient(
        "http://mcp.test/mcp",
        transport=httpx.MockTransport(handler),
    )

    result = await client.call_tool("im.v1.message.list", {})

    assert result == {"data": {"items": []}}


@pytest.mark.asyncio
async def test_fallback_client_uses_openapi_when_mcp_fails():
    class FailingClient:
        async def call_tool(self, tool_name, arguments):
            raise FeishuMcpClientError("mcp failed")

    class WorkingClient:
        async def call_tool(self, tool_name, arguments):
            return {"items": [{"message_id": "om_fallback"}]}

    client = FallbackFeishuClient(FailingClient(), WorkingClient())

    result = await client.call_tool("im.v1.message.list", {"params": {}})

    assert result["items"][0]["message_id"] == "om_fallback"
