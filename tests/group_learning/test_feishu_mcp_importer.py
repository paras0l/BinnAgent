from datetime import timezone

from src.group_learning.feishu_mcp_importer import (
    FeishuMcpMessageImporter,
    feishu_message_to_compatible_json,
)


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
