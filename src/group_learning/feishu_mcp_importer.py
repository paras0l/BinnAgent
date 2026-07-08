import hashlib
import json
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.group_learning.service import (
    GroupLearningImportMessage,
    GroupLearningImportResult,
    import_group_messages,
    is_group_help_command,
)
from src.models.group_learning import GroupLearningSource


FEISHU_GROUP_HELP_TEXT = """BinnAgent 群聊学习指令：
#单词 nuance - 沉淀一个想学的单词
#语法 被动语态 - 记录语法学习点
#怎么说 这个观点太绝对了 - 记录表达缺口
#纠错 I am agree with you. - 记录待纠错句子
#收藏 What matters most is... - 收藏好句

发送方式：@机器人 后输入上述指令；只会在你确认后写入长期学习资产。"""


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
    help_reply_count: int = 0


@dataclass(frozen=True)
class FeishuMcpMemberSyncResult:
    source_id: uuid.UUID
    learner_id: uuid.UUID
    fetched_count: int
    upserted_count: int
    participant_count: int
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
        raw_items = _extract_message_items(payload)
        records = [self.normalize_message_record(item) for item in raw_items]
        records = [record for record in records if record is not None]
        messages = [record.message for record in records]
        help_reply_count, help_replied_ids = await self._reply_to_new_help_requests(source, client, records)
        summary = await import_group_messages(db, source_id=source.id, messages=messages)
        next_cursor = _extract_next_cursor(payload)
        source.last_cursor = next_cursor or source.last_cursor
        cumulative_help_reply_ids = _remembered_help_reply_ids(source, help_replied_ids)
        source.last_import_summary = {
            "provider": "lark-openapi-mcp",
            "tool": "im.v1.message.list",
            "synced_at": synced_at.isoformat(),
            "fetched_count": len(messages),
            "help_reply_count": help_reply_count,
            "help_replied_external_message_ids": cumulative_help_reply_ids,
            "next_cursor": next_cursor,
            "imported_count": summary.imported_count,
            "duplicate_count": summary.duplicate_count,
            "generated_signal_count": summary.generated_signal_count,
            "ignored_count": summary.ignored_count,
        }
        await db.flush()
        return _sync_result(
            source,
            summary,
            fetched_count=len(messages),
            next_cursor=next_cursor,
            help_reply_count=help_reply_count,
        )

    async def sync_members(
        self,
        db: AsyncSession,
        source: GroupLearningSource,
    ) -> FeishuMcpMemberSyncResult:
        synced_at = datetime.now(timezone.utc)
        client = await self._client_factory(source) if self._client_factory else None
        if client is None:
            source.last_import_summary = {
                **(source.last_import_summary or {}),
                "member_sync_status": "placeholder",
                "member_sync_reason": "MCP client is not configured yet",
                "member_sync_tool": "im.v1.chatMembers.get",
                "member_synced_at": synced_at.isoformat(),
            }
            await db.flush()
            return FeishuMcpMemberSyncResult(
                source_id=source.id,
                learner_id=source.learner_id,
                fetched_count=0,
                upserted_count=0,
                participant_count=0,
                last_sync_at=synced_at,
                placeholder=True,
            )

        raw_members: list[dict[str, Any]] = []
        next_cursor: str | None = None
        for _ in range(20):
            payload = await client.call_tool(
                "im.v1.chatMembers.get",
                {
                    "path": {"chat_id": source.external_group_key},
                    "params": {
                        "member_id_type": "open_id",
                        "page_size": 100,
                        **({"page_token": next_cursor} if next_cursor else {}),
                    },
                },
            )
            raw_members.extend(_extract_member_items(payload))
            next_cursor = _extract_next_cursor(payload)
            if not next_cursor:
                break

        members = [member for member in (_normalize_member(item) for item in raw_members) if member is not None]
        upserted_count = await _upsert_participants_from_members(db, source, members)
        source.last_import_summary = {
            **(source.last_import_summary or {}),
            "member_sync_status": "completed",
            "member_sync_tool": "im.v1.chatMembers.get",
            "member_synced_at": synced_at.isoformat(),
            "member_fetched_count": len(members),
            "member_upserted_count": upserted_count,
        }
        await db.flush()
        return FeishuMcpMemberSyncResult(
            source_id=source.id,
            learner_id=source.learner_id,
            fetched_count=len(members),
            upserted_count=upserted_count,
            participant_count=upserted_count,
            last_sync_at=synced_at,
        )

    def normalize_message_list(self, payload: dict[str, Any]) -> list[GroupLearningImportMessage]:
        raw_items = _extract_message_items(payload)
        records = [self.normalize_message_record(item) for item in raw_items]
        return [record.message for record in records if record is not None]

    def normalize_message(self, item: dict[str, Any]) -> GroupLearningImportMessage | None:
        record = self.normalize_message_record(item)
        return record.message if record else None

    def normalize_message_record(self, item: dict[str, Any]) -> "_FeishuNormalizedMessage | None":
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
        message = GroupLearningImportMessage(
            external_message_id=str(message_id),
            external_member_key=str(sender_id),
            display_name=str(sender_name) if sender_name else None,
            content_text=content_text,
            occurred_at=_message_time(item),
            message_type="text",
        )
        return _FeishuNormalizedMessage(
            message=message,
            help_requested=is_feishu_help_request(item, content_text),
        )

    async def _reply_to_new_help_requests(
        self,
        source: GroupLearningSource,
        client: FeishuMcpClient,
        records: list["_FeishuNormalizedMessage"],
    ) -> tuple[int, list[str]]:
        if source.status != "active":
            return 0, []
        help_records = [record for record in records if record.help_requested]
        if not help_records:
            return 0, []
        already_replied_ids = set(_remembered_help_reply_ids(source))
        replied_ids: list[str] = []
        for record in help_records:
            message_id = record.message.external_message_id
            if message_id in already_replied_ids or message_id in replied_ids:
                continue
            await send_feishu_group_help(client, source.external_group_key)
            replied_ids.append(message_id)
        return len(replied_ids), replied_ids


@dataclass(frozen=True)
class _FeishuNormalizedMessage:
    message: GroupLearningImportMessage
    help_requested: bool


async def send_feishu_group_help(client: FeishuMcpClient, chat_id: str) -> dict[str, Any]:
    return await client.call_tool(
        "im.v1.message.create",
        {
            "params": {"receive_id_type": "chat_id"},
            "data": {
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": FEISHU_GROUP_HELP_TEXT}, ensure_ascii=False),
            },
        },
    )


def is_feishu_help_request(item: dict[str, Any], content_text: str | None = None) -> bool:
    text = content_text if content_text is not None else _content_text(item.get("body", {}).get("content") or item.get("content") or "")
    if not is_group_help_command(text):
        return False
    return _mentions_bot(item, text)


@dataclass(frozen=True)
class _FeishuMember:
    external_member_key: str
    display_name: str


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
    help_reply_count: int = 0,
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
        help_reply_count=help_reply_count,
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


def _extract_member_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    items = (
        data.get("items")
        or data.get("members")
        or data.get("member_list")
        or payload.get("items")
        or []
    )
    return [item for item in items if isinstance(item, dict)]


def _extract_next_cursor(payload: dict[str, Any]) -> str | None:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    cursor = data.get("page_token") or data.get("next_page_token") or data.get("cursor")
    return str(cursor) if cursor else None


def _normalize_member(item: dict[str, Any]) -> _FeishuMember | None:
    member_id = (
        item.get("member_id")
        or item.get("open_id")
        or item.get("user_id")
        or item.get("union_id")
        or item.get("id")
    )
    if not member_id:
        return None
    display_name = (
        item.get("name")
        or item.get("nickname")
        or item.get("display_name")
        or item.get("tenant_key")
        or member_id
    )
    return _FeishuMember(external_member_key=str(member_id), display_name=str(display_name))


async def _upsert_participants_from_members(
    db: AsyncSession,
    source: GroupLearningSource,
    members: list[_FeishuMember],
) -> int:
    from sqlalchemy import select

    from src.models.group_learning import GroupLearningParticipant

    if not members:
        return 0
    result = await db.execute(
        select(GroupLearningParticipant).where(GroupLearningParticipant.source_id == source.id)
    )
    existing = {participant.external_member_key: participant for participant in result.scalars().all()}
    upserted_count = 0
    for member in members:
        participant = existing.get(member.external_member_key)
        if participant is None:
            db.add(
                GroupLearningParticipant(
                    source_id=source.id,
                    external_member_key=member.external_member_key,
                    display_name=member.display_name,
                    learner_id=None,
                    role="unknown",
                    analysis_enabled=False,
                )
            )
            upserted_count += 1
        elif participant.display_name != member.display_name:
            participant.display_name = member.display_name
            upserted_count += 1
    return upserted_count


def _remembered_help_reply_ids(
    source: GroupLearningSource,
    new_ids: list[str] | None = None,
    *,
    limit: int = 200,
) -> list[str]:
    remembered: list[str] = []
    for raw_id in (source.last_import_summary or {}).get("help_replied_external_message_ids", []):
        if not isinstance(raw_id, str) or raw_id in remembered:
            continue
        remembered.append(raw_id)
    for raw_id in new_ids or []:
        if raw_id not in remembered:
            remembered.append(raw_id)
    return remembered[-limit:]


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError:
            return content
        extracted = _extract_content_text(decoded)
        if extracted:
            return extracted
        return content
    extracted = _extract_content_text(content)
    if extracted:
        return extracted
    return ""


def _extract_content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("content"), str):
            return value["content"]
        if "content" in value:
            return _extract_content_text(value["content"])
        if value.get("tag") == "at":
            name = value.get("user_name") or value.get("name") or value.get("text")
            return f"@{name}" if name else "@"
        if isinstance(value.get("text"), (dict, list)):
            return _extract_content_text(value["text"])
        parts = [_extract_content_text(item) for item in value.values()]
        return " ".join(part for part in parts if part).strip()
    if isinstance(value, list):
        parts = [_extract_content_text(item) for item in value]
        return " ".join(part for part in parts if part).strip()
    return ""


def _mentions_bot(item: dict[str, Any], text: str) -> bool:
    mentions = item.get("mentions")
    if isinstance(mentions, list) and any(isinstance(mention, dict) for mention in mentions):
        return True
    body = item.get("body") if isinstance(item.get("body"), dict) else {}
    body_mentions = body.get("mentions")
    if isinstance(body_mentions, list) and any(isinstance(mention, dict) for mention in body_mentions):
        return True
    return bool(re.search(r"(<at\b|</at>|@_|(^|\s)@\S+)", text, flags=re.IGNORECASE))


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
