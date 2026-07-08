import json
import uuid
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import src.group_learning.feishu_mcp_importer as feishu_importer
from src.group_learning.feishu_mcp_importer import (
    FEISHU_GROUP_HELP_TEXT,
    FeishuMcpMessageImporter,
    feishu_message_to_compatible_json,
    is_feishu_help_request,
)
from src.group_learning.service import GroupLearningImportResult


def test_feishu_importer_normalizes_text_messages_from_mcp_payload():
    importer = FeishuMcpMessageImporter()

    messages = importer.normalize_message_list(
        {
            "data": {
                "items": [
                    {
                        "message_id": "om_123",
                        "msg_type": "text",
                        "create_time": "1783487400000",
                        "sender": {"id": "ou_alex", "name": "Alex"},
                        "body": {"content": '{"text":"#纠错 I am agree with you."}'},
                    },
                    {
                        "message_id": "om_image",
                        "msg_type": "image",
                        "create_time": "1783487400000",
                    },
                ]
            }
        }
    )

    assert len(messages) == 1
    assert messages[0].external_message_id == "om_123"
    assert messages[0].external_member_key == "ou_alex"
    assert messages[0].display_name == "Alex"
    assert messages[0].content_text == "#纠错 I am agree with you."
    assert messages[0].occurred_at.tzinfo == timezone.utc


def test_feishu_message_can_map_to_legacy_compatible_json_shape():
    mapped = feishu_message_to_compatible_json(
        {
            "message_id": "om_456",
            "msg_type": "text",
            "create_time": "1783487400000",
            "sender": {"id": "ou_mia", "name": "Mia"},
            "body": {"content": '{"text":"#单词 nuance"}'},
        },
        chat_id="oc_group",
        chat_name="英语学习搭子群",
    )

    assert mapped["source"] == "feishu"
    assert mapped["talker"] == "oc_group"
    assert mapped["talker_name"] == "英语学习搭子群"
    assert mapped["sender"] == "ou_mia"
    assert mapped["sender_name"] == "Mia"
    assert mapped["msg_id"] == "om_456"
    assert mapped["type"] == "text"
    assert mapped["content"] == "#单词 nuance"
    assert mapped["raw"]["provider"] == "lark-openapi-mcp"


def test_feishu_help_request_requires_help_command_and_bot_mention():
    assert is_feishu_help_request(
        {
            "body": {"content": '{"text":"@_user_1 --help"}'},
            "mentions": [{"key": "@_user_1", "name": "BinnAgent"}],
        }
    )
    assert not is_feishu_help_request({"body": {"content": '{"text":"--help"}'}})
    assert not is_feishu_help_request(
        {
            "body": {"content": '{"text":"@_user_1 #单词 nuance"}'},
            "mentions": [{"key": "@_user_1", "name": "BinnAgent"}],
        }
    )
    assert is_feishu_help_request(
        {
            "body": {
                "content": json.dumps(
                    {
                        "content": [
                            [
                                {"tag": "at", "user_id": "ou_bot", "user_name": "BinnAgent2.0"},
                                {"tag": "text", "text": "  --help"},
                            ]
                        ]
                    },
                    ensure_ascii=False,
                )
            }
        }
    )


@pytest.mark.asyncio
async def test_feishu_sync_replies_to_new_help_request(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.calls = []

        async def call_tool(self, tool_name, arguments):
            self.calls.append((tool_name, arguments))
            if tool_name == "im.v1.message.list":
                return {
                    "data": {
                        "items": [
                            {
                                "message_id": "om_help",
                                "msg_type": "text",
                                "create_time": "1783487400000",
                                "sender": {"id": "ou_alex", "name": "Alex"},
                                "mentions": [{"key": "@_user_1", "name": "BinnAgent"}],
                                "body": {"content": '{"text":"@_user_1 --help"}'},
                            }
                        ]
                    }
                }
            if tool_name == "im.v1.message.create":
                return {"data": {"message_id": "om_reply"}}
            raise AssertionError(tool_name)

    client = FakeClient()
    source = SimpleNamespace(
        id=uuid.uuid4(),
        learner_id=uuid.uuid4(),
        external_group_key="oc_group",
        last_cursor=None,
        last_import_summary={},
        import_mode="silent",
        status="active",
    )
    db = SimpleNamespace(flush=AsyncMock())
    monkeypatch.setattr(
        feishu_importer,
        "import_group_messages",
        AsyncMock(return_value=GroupLearningImportResult(1, 0, 0, 0, 1)),
    )

    result = await FeishuMcpMessageImporter(client_factory=lambda _: _async_value(client)).sync_source(db, source)

    assert result.help_reply_count == 1
    assert source.last_import_summary["help_replied_external_message_ids"] == ["om_help"]
    assert client.calls[1][0] == "im.v1.message.create"
    assert client.calls[1][1]["params"] == {"receive_id_type": "chat_id"}
    assert client.calls[1][1]["data"]["receive_id"] == "oc_group"
    reply_content = json.loads(client.calls[1][1]["data"]["content"])
    assert "#单词 nuance" in reply_content["text"]
    assert FEISHU_GROUP_HELP_TEXT == reply_content["text"]


@pytest.mark.asyncio
async def test_feishu_sync_does_not_repeat_remembered_help_reply(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.calls = []

        async def call_tool(self, tool_name, arguments):
            self.calls.append((tool_name, arguments))
            if tool_name == "im.v1.message.list":
                return {
                    "data": {
                        "items": [
                            {
                                "message_id": "om_help",
                                "msg_type": "text",
                                "create_time": "1783487400000",
                                "sender": {"id": "ou_alex", "name": "Alex"},
                                "mentions": [{"key": "@_user_1", "name": "BinnAgent"}],
                                "body": {"content": '{"text":"@_user_1 --help"}'},
                            }
                        ]
                    }
                }
            if tool_name == "im.v1.message.create":
                return {"data": {"message_id": "om_reply"}}
            raise AssertionError(tool_name)

    client = FakeClient()
    source = SimpleNamespace(
        id=uuid.uuid4(),
        learner_id=uuid.uuid4(),
        external_group_key="oc_group",
        last_cursor=None,
        last_import_summary={"help_replied_external_message_ids": ["om_help"]},
        import_mode="silent",
        status="active",
    )
    db = SimpleNamespace(flush=AsyncMock())
    monkeypatch.setattr(
        feishu_importer,
        "import_group_messages",
        AsyncMock(return_value=GroupLearningImportResult(0, 1, 0, 0, 1)),
    )

    result = await FeishuMcpMessageImporter(client_factory=lambda _: _async_value(client)).sync_source(db, source)

    assert result.help_reply_count == 0
    assert [call[0] for call in client.calls] == ["im.v1.message.list"]
    assert source.last_import_summary["help_replied_external_message_ids"] == ["om_help"]


@pytest.mark.asyncio
async def test_feishu_sync_members_fetches_chat_members(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.calls = []

        async def call_tool(self, tool_name, arguments):
            self.calls.append((tool_name, arguments))
            if tool_name == "im.v1.chatMembers.get":
                return {
                    "data": {
                        "items": [
                            {"member_id": "ou_alex", "name": "Alex"},
                            {"open_id": "ou_mia", "nickname": "Mia"},
                        ]
                    }
                }
            raise AssertionError(tool_name)

    client = FakeClient()
    source = SimpleNamespace(
        id=uuid.uuid4(),
        learner_id=uuid.uuid4(),
        external_group_key="oc_group",
        last_import_summary={},
    )
    db = SimpleNamespace(flush=AsyncMock())
    upsert = AsyncMock(return_value=2)
    monkeypatch.setattr(feishu_importer, "_upsert_participants_from_members", upsert)

    result = await FeishuMcpMessageImporter(client_factory=lambda _: _async_value(client)).sync_members(db, source)

    assert result.fetched_count == 2
    assert result.upserted_count == 2
    assert client.calls[0] == (
        "im.v1.chatMembers.get",
        {
            "path": {"chat_id": "oc_group"},
            "params": {"member_id_type": "open_id", "page_size": 100},
        },
    )
    members = upsert.call_args.args[2]
    assert [member.external_member_key for member in members] == ["ou_alex", "ou_mia"]


async def _async_value(value):
    return value
