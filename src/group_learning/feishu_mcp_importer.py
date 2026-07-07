import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.group_learning.service import GroupLearningImportMessage, GroupLearningImportResult, import_group_messages
from src.models.group_learning import GroupLearningSource


class FeishuMcpClient(Protocol):
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a larksuite/lark-openapi-mcp tool."""


@dataclass(frozen=True)
class FeishuMcpSyncResult:
    source_id: uuid.UUID
    learner_id: uuid.UUID
    imported_count: int
    duplicate_count: int
    generated_signal_count: int
    ignored_count: int
    participant_count: int
    fetched_count: int
    next_cursor: str | None
    last_sync_at: datetime
    placeholder: bool = False


McpClientFactory = Callable[[GroupLearningSource], Awaitable[FeishuMcpClient | None]]


class FeishuMcpMessageImporter:
    """Adapter from Feishu MCP message.list output to neutral group-learning messages."""

    def __init__(self, client_factory: McpClientFactory | None = None):
        self._client_factory = client_factory

    async def sync_source(
        self,
        db: AsyncSession,
        source: GroupLearningSource,
    ) -> FeishuMcpSyncResult:
        synced_at = datetime.now(timezone.utc)
        client = await self._client_factory(source) if self._client_factory else None
        if client is None:
            summary = {
                "provider": "lark-openapi-mcp",
                "status": "placeholder",
                "reason": "MCP client is not configured yet",
                "tool": "im.v1.message.list",
                "synced_at": synced_at.isoformat(),
            }
            source.last_import_summary = summary
            await db.flush()
            return FeishuMcpSyncResult(
                source_id=source.id,
                learner_id=source.learner_id,
                imported_count=0,
                duplicate_count=0,
                generated_signal_count=0,
                ignored_count=0,
                participant_count=0,
                fetched_count=0,
                next_cursor=source.last_cursor,
                last_sync_at=synced_at,
                placeholder=True,
            )

        payload = await client.call_tool(
            "im.v1.message.list",
            {
                "params": {
                    "container_id_type": "chat",
                    "container_id": source.external_group_key,
                    "sort_type": "ByCreateTimeAsc",
                    "page_size": 50,
                    **({"page_token": source.last_cursor} if source.last_cursor else {}),
                },
            },
        )
        messages = self.normalize_message_list(payload)
        summary = await import_group_messages(db, source_id=source.id, messages=messages)
        next_cursor = _extract_next_cursor(payload)
        source.last_cursor = next_cursor or source.last_cursor
        source.last_import_summary = {
            "provider": "lark-openapi-mcp",
            "tool": "im.v1.message.list",
            "synced_at": synced_at.isoformat(),
            "fetched_count": len(messages),
            "next_cursor": next_cursor,
            "imported_count": summary.imported_count,
            "duplicate_count": summary.duplicate_count,
            "generated_signal_count": summary.generated_signal_count,
            "ignored_count": summary.ignored_count,
        }
        await db.flush()
        return _sync_result(source, summary, fetched_count=len(messages), next_cursor=next_cursor)

    def normalize_message_list(self, payload: dict[str, Any]) -> list[GroupLearningImportMessage]:
        raw_items = _extract_message_items(payload)
        messages = [self.normalize_message(item) for item in raw_items]
        return [message for message in messages if message is not None]

    def normalize_message(self, item: dict[str, Any]) -> GroupLearningImportMessage | None:
        message_type = str(item.get("msg_type") or item.get("message_type") or "text")
        if message_type != "text":
            return None
        content_text = _content_text(item.get("body", {}).get("content") or item.get("content") or "")
        if not content_text.strip():
            return None
        sender = item.get("sender") if isinstance(item.get("sender"), dict) else {}
        sender_id = (
            sender.get("id")
            or sender.get("sender_id")
            or item.get("sender_id")
            or item.get("external_member_key")
            or "unknown-feishu-sender"
        )
        sender_name = (
            sender.get("name")
            or sender.get("sender_name")
            or item.get("sender_name")
            or item.get("display_name")
        )
        message_id = item.get("message_id") or item.get("msg_id") or item.get("id")
        if not message_id:
            digest = hashlib.sha256(content_text.encode("utf-8")).hexdigest()[:16]
            message_id = f"feishu-{sender_id}-{_message_time(item).isoformat()}-{digest}"
        return GroupLearningImportMessage(
            external_message_id=str(message_id),
            external_member_key=str(sender_id),
            display_name=str(sender_name) if sender_name else None,
            content_text=content_text,
            occurred_at=_message_time(item),
            message_type="text",
        )


def feishu_message_to_compatible_json(item: dict[str, Any], *, chat_id: str, chat_name: str) -> dict[str, Any]:
    """Map a Feishu message to the legacy WeChat-compatible import shape."""
    importer = FeishuMcpMessageImporter()
    normalized = importer.normalize_message(item)
    if normalized is None:
        return {}
    return {
        "source": "feishu",
        "platform": "feishu",
        "talker": chat_id,
        "talker_name": chat_name,
        "sender": normalized.external_member_key,
        "sender_name": normalized.display_name,
        "msg_id": normalized.external_message_id,
        "type": normalized.message_type,
        "content": normalized.content_text,
        "create_time": normalized.occurred_at.isoformat(),
        "raw": {"provider": "lark-openapi-mcp"},
    }


def _sync_result(
    source: GroupLearningSource,
    summary: GroupLearningImportResult,
    *,
    fetched_count: int,
    next_cursor: str | None,
) -> FeishuMcpSyncResult:
    return FeishuMcpSyncResult(
        source_id=source.id,
        learner_id=source.learner_id,
        imported_count=summary.imported_count,
        duplicate_count=summary.duplicate_count,
        generated_signal_count=summary.generated_signal_count,
        ignored_count=summary.ignored_count,
        participant_count=summary.participant_count,
        fetched_count=fetched_count,
        next_cursor=next_cursor,
        last_sync_at=_last_sync_at(source),
    )


def _last_sync_at(source: GroupLearningSource) -> datetime:
    synced_at = (source.last_import_summary or {}).get("synced_at")
    if isinstance(synced_at, str) and synced_at.strip():
        return datetime.fromisoformat(synced_at.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


def _extract_message_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    items = data.get("items") or data.get("messages") or payload.get("items") or []
    return [item for item in items if isinstance(item, dict)]


def _extract_next_cursor(payload: dict[str, Any]) -> str | None:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    cursor = data.get("page_token") or data.get("next_page_token") or data.get("cursor")
    return str(cursor) if cursor else None


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError:
            return content
        if isinstance(decoded, dict):
            return str(decoded.get("text") or decoded.get("content") or "")
        return content
    if isinstance(content, dict):
        return str(content.get("text") or content.get("content") or "")
    return ""


def _message_time(item: dict[str, Any]) -> datetime:
    value = item.get("create_time") or item.get("created_at") or item.get("occurred_at")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(_timestamp_seconds(value), tz=timezone.utc)
    if isinstance(value, str) and value.strip():
        if value.isdigit():
            return datetime.fromtimestamp(_timestamp_seconds(float(value)), tz=timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


def _timestamp_seconds(value: float) -> float:
    return value / 1000 if value > 10_000_000_000 else value
