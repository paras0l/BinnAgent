import uuid
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import httpx
import pytest

import src.api.chat as chat_api
from src.api import deps
from src.main import app
from src.models.learner import Learner
from src.models.runtime import AgentThread, ConversationMessage
from src.providers.base import ChatResponse as ModelChatResponse
from src.providers.base import ChatStreamChunk
from src.providers.router import ModelRouter


@pytest.fixture
def mock_model_router():
    router = AsyncMock(spec=ModelRouter)
    app.dependency_overrides[deps.get_model_router] = lambda: router
    yield router
    app.dependency_overrides.clear()


@pytest.fixture
def mock_session():
    learner_id = uuid.uuid4()
    learner = Learner(nickname="Alice")
    learner.id = learner_id
    added_objects = []

    session = AsyncMock()
    session.add = MagicMock(side_effect=added_objects.append)

    async def _flush():
        for obj in added_objects:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def _refresh(instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()

    result = MagicMock()
    result.scalar_one_or_none.return_value = learner.id

    async def _execute(stmt):
        statement = str(stmt)
        if "max(conversation_messages.sequence)" in statement:
            max_result = MagicMock()
            max_result.scalar_one_or_none.return_value = 0
            return max_result
        if "conversation_messages" in statement:
            history_result = MagicMock()
            history_result.scalars.return_value.all.return_value = []
            return history_result
        return result

    session.execute = AsyncMock(side_effect=_execute)
    session.flush = AsyncMock(side_effect=_flush)
    session.refresh = AsyncMock(side_effect=_refresh)
    session.commit = AsyncMock()
    session.added_objects = added_objects
    session.learner_id = learner_id

    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


@pytest.fixture
def mock_stream_persist_session(monkeypatch, mock_session):
    session = AsyncMock()
    added_objects = []
    session.add = MagicMock(side_effect=added_objects.append)

    async def _execute(stmt):
        if "max(conversation_messages.sequence)" in str(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = 1
            return result
        thread = next(obj for obj in mock_session.added_objects if isinstance(obj, AgentThread))
        result = MagicMock()
        result.scalar_one_or_none.return_value = thread
        return result

    async def _refresh(instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()

    session.execute = AsyncMock(side_effect=_execute)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock(side_effect=_refresh)
    session.added_objects = added_objects

    class _FactoryContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(chat_api, "async_session_factory", lambda: _FactoryContext())
    return session


class TestChatSend:
    @pytest.mark.asyncio
    async def test_chat_send_returns_reply_and_response_alias(
        self, client, mock_model_router, mock_session
    ):
        mock_model_router.chat = AsyncMock(
            return_value=ModelChatResponse(
                provider="ollama",
                model="gemma4:e2b",
                content="你好，我可以帮你练习阅读。",
            )
        )

        response = await client.post(
            "/api/chat/send",
            json={"learner_id": str(mock_session.learner_id), "message": "我想练习阅读"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "你好，我可以帮你练习阅读。"
        assert data["response"] == "你好，我可以帮你练习阅读。"
        assert data["thread_id"]
        assert data["message_id"]
        assert data["skill_focus"] is None
        messages = [
            obj for obj in mock_session.added_objects if isinstance(obj, ConversationMessage)
        ]
        assert [message.role for message in messages] == ["user", "assistant"]
        assert messages[0].content == "我想练习阅读"
        assert messages[1].content == "你好，我可以帮你练习阅读。"
        threads = [obj for obj in mock_session.added_objects if isinstance(obj, AgentThread)]
        assert threads[0].metadata_["title"] == "我想练习阅读"
        assert "last_message_at" in threads[0].metadata_
        mock_model_router.chat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_send_uses_skill_focus_in_system_message(
        self, client, mock_model_router, mock_session
    ):
        mock_model_router.chat = AsyncMock(
            return_value=ModelChatResponse(provider="ollama", model="gemma4:e2b", content="OK")
        )

        response = await client.post(
            "/api/chat/send",
            json={
                "learner_id": str(mock_session.learner_id),
                "message": "帮我练一下",
                "skill_focus": "writing",
            },
        )

        assert response.status_code == 200
        request = mock_model_router.chat.await_args.args[0]
        assert request.task_type == "learning_chat"
        assert request.temperature == 0.7
        assert request.max_tokens == 2048
        assert "当前重点练习: writing" in request.messages[0]["content"]

    @pytest.mark.asyncio
    async def test_chat_send_blank_message_returns_422(self, client, mock_session):
        response = await client.post(
            "/api/chat/send",
            json={"learner_id": str(mock_session.learner_id), "message": "   "},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_send_model_http_error_returns_stable_503(
        self, client, mock_model_router, mock_session
    ):
        mock_model_router.chat = AsyncMock(side_effect=httpx.ConnectError("secret host detail"))

        response = await client.post(
            "/api/chat/send",
            json={"learner_id": str(mock_session.learner_id), "message": "hello"},
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Ollama service unavailable"

    @pytest.mark.asyncio
    async def test_chat_send_includes_thread_summary_and_recent_history(
        self, client, mock_model_router, mock_session
    ):
        thread_id = uuid.uuid4()
        thread = AgentThread(learner_id=mock_session.learner_id, metadata_={"summary": "讨论过长难句。"})
        thread.id = thread_id
        history_user = ConversationMessage(
            learner_id=mock_session.learner_id,
            thread_id=thread_id,
            role="user",
            content="什么是定语从句？",
            sequence=1,
        )
        history_assistant = ConversationMessage(
            learner_id=mock_session.learner_id,
            thread_id=thread_id,
            role="assistant",
            content="定语从句用来修饰名词。",
            sequence=2,
        )

        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = mock_session.learner_id
        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = thread
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = [history_assistant, history_user]
        max_result = MagicMock()
        max_result.scalar_one_or_none.return_value = 2
        mock_session.execute = AsyncMock(
            side_effect=[learner_result, thread_result, history_result, max_result]
        )
        mock_model_router.chat = AsyncMock(
            return_value=ModelChatResponse(provider="ollama", model="gemma4:e2b", content="继续讲。")
        )

        response = await client.post(
            "/api/chat/send",
            json={
                "learner_id": str(mock_session.learner_id),
                "thread_id": str(thread_id),
                "message": "继续",
            },
        )

        assert response.status_code == 200
        request = mock_model_router.chat.await_args.args[0]
        contents = [message["content"] for message in request.messages]
        assert any("此前对话摘要" in content and "讨论过长难句" in content for content in contents)
        assert "什么是定语从句？" in contents
        assert "定语从句用来修饰名词。" in contents
        assert contents[-1] == "继续"

    @pytest.mark.asyncio
    async def test_chat_send_auto_continues_length_finish_once(
        self, client, mock_model_router, mock_session
    ):
        mock_model_router.chat = AsyncMock(
            side_effect=[
                ModelChatResponse(
                    provider="ollama",
                    model="gemma4:e2b",
                    content="第一段",
                    finish_reason="length",
                ),
                ModelChatResponse(
                    provider="ollama",
                    model="gemma4:e2b",
                    content="第二段",
                    finish_reason="stop",
                ),
            ]
        )

        response = await client.post(
            "/api/chat/send",
            json={"learner_id": str(mock_session.learner_id), "message": "详细解释"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "第一段第二段"
        assert data["finish_reason"] == "stop"
        assert data["continuation_count"] == 1
        second_request = mock_model_router.chat.await_args_list[1].args[0]
        second_contents = [message["content"] for message in second_request.messages]
        assert "详细解释" in second_contents
        assert "第一段" in second_contents
        assert "不要重复已回答内容" in second_contents[-1]


class TestChatStream:
    @pytest.mark.asyncio
    async def test_chat_stream_returns_sse_and_persists_messages(
        self, client, mock_model_router, mock_session, mock_stream_persist_session
    ):
        async def stream_chat(request):
            yield "你好，"
            yield "我们开始练习。"

        mock_model_router.stream_chat = stream_chat

        response = await client.post(
            "/api/chat/stream",
            json={"learner_id": str(mock_session.learner_id), "message": "开始练习"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.text
        assert "event: meta" in body
        assert "event: delta" in body
        assert "你好，" in body
        assert "我们开始练习。" in body
        assert "event: done" in body

        request_messages = [
            obj for obj in mock_session.added_objects if isinstance(obj, ConversationMessage)
        ]
        persisted_messages = [
            obj
            for obj in mock_stream_persist_session.added_objects
            if isinstance(obj, ConversationMessage)
        ]
        assert [message.role for message in request_messages] == ["user"]
        assert [message.role for message in persisted_messages] == ["assistant"]
        assert request_messages[0].content == "开始练习"
        assert persisted_messages[0].content == "你好，我们开始练习。"

    @pytest.mark.asyncio
    async def test_chat_stream_model_http_error_returns_error_event_without_assistant_message(
        self, client, mock_model_router, mock_session
    ):
        async def stream_chat(request):
            raise httpx.ConnectError("secret host detail")
            yield ""

        mock_model_router.stream_chat = stream_chat

        response = await client.post(
            "/api/chat/stream",
            json={"learner_id": str(mock_session.learner_id), "message": "hello"},
        )

        assert response.status_code == 200
        assert "event: error" in response.text
        assert "Ollama service unavailable" in response.text
        assert "secret host detail" not in response.text

        messages = [
            obj for obj in mock_session.added_objects if isinstance(obj, ConversationMessage)
        ]
        assert [message.role for message in messages] == ["user"]

    @pytest.mark.asyncio
    async def test_chat_stream_auto_continues_length_finish(
        self, client, mock_model_router, mock_session, mock_stream_persist_session
    ):
        call_count = 0

        async def stream_chat(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield ChatStreamChunk(content="第一段")
                yield ChatStreamChunk(finish_reason="length")
            else:
                yield ChatStreamChunk(content="第二段")
                yield ChatStreamChunk(finish_reason="stop")

        mock_model_router.stream_chat = stream_chat

        response = await client.post(
            "/api/chat/stream",
            json={"learner_id": str(mock_session.learner_id), "message": "详细解释"},
        )

        assert response.status_code == 200
        assert "event: continuation" in response.text
        assert "第一段" in response.text
        assert "第二段" in response.text
        assert '"continuation_count": 1' in response.text
        messages = [
            obj
            for obj in mock_stream_persist_session.added_objects
            if isinstance(obj, ConversationMessage)
        ]
        assert messages[-1].role == "assistant"
        assert messages[-1].content == "第一段第二段"
