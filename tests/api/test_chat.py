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


def _empty_many():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    return result


def _count_result(value: int):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _rows_result(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


def _scalars_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


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
            result.scalar_one_or_none.return_value = 0
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
    async def test_persist_chat_messages_locks_existing_thread_before_sequence(self):
        learner_id = uuid.uuid4()
        thread_id = uuid.uuid4()
        thread = AgentThread(learner_id=learner_id)
        thread.id = thread_id
        db = AsyncMock()
        added_objects = []
        db.add = MagicMock(side_effect=added_objects.append)
        db.flush = AsyncMock()
        lock_result = MagicMock()
        lock_result.scalar_one_or_none.return_value = thread
        max_result = MagicMock()
        max_result.scalar_one_or_none.return_value = 4
        db.execute = AsyncMock(side_effect=[lock_result, max_result])
        req = chat_api.ChatRequest(
            learner_id=learner_id,
            thread_id=thread_id,
            message="继续讲",
        )

        _, user_message, assistant_message = await chat_api._persist_chat_messages(
            db=db,
            req=req,
            thread=thread,
            assistant_reply="好的",
            skill=None,
            user_metadata={},
            assistant_metadata={},
        )

        statements = [str(call.args[0]) for call in db.execute.await_args_list]
        assert "FOR UPDATE" in statements[0]
        assert "max(conversation_messages.sequence)" in statements[1]
        assert [obj.role for obj in added_objects if isinstance(obj, ConversationMessage)] == [
            "user",
            "assistant",
        ]
        assert user_message.sequence == 5
        assert assistant_message.sequence == 6

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
        messages = [
            obj for obj in mock_session.added_objects if isinstance(obj, ConversationMessage)
        ]
        assert messages == []
        mock_session.rollback.assert_awaited()

    @pytest.mark.asyncio
    async def test_chat_send_includes_thread_summary_and_recent_history(
        self, client, mock_model_router, mock_session, monkeypatch
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
        lock_result = MagicMock()
        lock_result.scalar_one_or_none.return_value = thread
        max_result = MagicMock()
        max_result.scalar_one_or_none.return_value = 2
        mock_session.execute = AsyncMock(
            side_effect=[
                learner_result,
                thread_result,
                history_result,
                *[_empty_many() for _ in range(11)],
                lock_result,
                max_result,
            ]
        )
        monkeypatch.setattr(chat_api, "_learning_snapshot_item", AsyncMock(return_value=None))
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
        assert any("FOR UPDATE" in str(call.args[0]) for call in mock_session.execute.await_args_list)

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

    @pytest.mark.asyncio
    async def test_chat_send_vocabulary_skill_returns_started_event(
        self, client, mock_model_router, mock_session, monkeypatch
    ):
        async def fake_background(**kwargs):
            return None

        monkeypatch.setattr(chat_api, "_run_vocabulary_agent_background", fake_background)
        mock_model_router.chat = AsyncMock(
            return_value=ModelChatResponse(
                provider="ollama",
                model="gemma4:e2b",
                content="significant: 重要的。",
            )
        )

        response = await client.post(
            "/api/chat/send",
            json={
                "learner_id": str(mock_session.learner_id),
                "message": "讲解 significant",
                "skill_focus": "vocabulary",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["skill_id"] == "vocabulary_deposit"
        assert data["skill_name"] == "词汇 Skill"
        assert data["skill_events"][0]["name"] == "vocabulary_agent"
        assert data["skill_events"][0]["skill_id"] == "vocabulary_deposit"
        assert data["skill_events"][0]["status"] == "started"
        threads = [obj for obj in mock_session.added_objects if isinstance(obj, AgentThread)]
        assert threads[0].metadata_["skill_id"] == "vocabulary_deposit"

    @pytest.mark.asyncio
    async def test_chat_send_restores_thread_skill_without_request_skill(
        self, client, mock_model_router, mock_session, monkeypatch
    ):
        thread_id = uuid.uuid4()
        thread = AgentThread(
            learner_id=mock_session.learner_id,
            metadata_={"skill_id": "vocabulary_deposit", "skill_name": "词汇 Skill"},
        )
        thread.id = thread_id

        async def fake_background(**kwargs):
            return None

        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = mock_session.learner_id
        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = thread
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []
        lock_result = MagicMock()
        lock_result.scalar_one_or_none.return_value = thread
        max_result = MagicMock()
        max_result.scalar_one_or_none.return_value = 0
        empty_result = MagicMock()
        empty_result.scalar_one_or_none.return_value = None
        empty_result.scalars.return_value.all.return_value = []
        empty_result.all.return_value = []

        async def _execute(stmt):
            statement = str(stmt)
            if "max(conversation_messages.sequence)" in statement:
                return max_result
            if "agent_threads" in statement and "FOR UPDATE" in statement:
                return lock_result
            if "agent_threads" in statement:
                return thread_result
            if "conversation_messages" in statement:
                return history_result
            if "learners" in statement:
                return learner_result
            return empty_result

        mock_session.execute = AsyncMock(side_effect=_execute)
        monkeypatch.setattr(chat_api, "_learning_snapshot_item", AsyncMock(return_value=None))
        monkeypatch.setattr(chat_api, "_run_vocabulary_agent_background", fake_background)
        mock_model_router.chat = AsyncMock(
            return_value=ModelChatResponse(provider="ollama", model="gemma4:e2b", content="OK")
        )

        response = await client.post(
            "/api/chat/send",
            json={
                "learner_id": str(mock_session.learner_id),
                "thread_id": str(thread_id),
                "message": "那再讲一个例句",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["skill_id"] == "vocabulary_deposit"
        assert data["skill_events"][0]["status"] == "started"
        request = mock_model_router.chat.await_args.args[0]
        assert "当前 Agent Skill: 词汇 Skill" in request.messages[0]["content"]
        messages = [
            obj for obj in mock_session.added_objects if isinstance(obj, ConversationMessage)
        ]
        assert {message.skill_focus for message in messages} == {"vocabulary_deposit"}


class TestChatLearningSnapshot:
    @pytest.mark.asyncio
    async def test_learning_snapshot_summarizes_structured_progress(self):
        db = AsyncMock()
        grammar_item = MagicMock()
        grammar_item.title = "一般现在时"
        db.execute = AsyncMock(
            side_effect=[
                _count_result(24),
                _count_result(6),
                _rows_result([(MagicMock(), "weather"), (MagicMock(), "usually"), (MagicMock(), "weather")]),
                _count_result(3),
                _scalars_result([grammar_item]),
            ]
        )

        item = await chat_api._learning_snapshot_item(db, learner_id=uuid.uuid4())

        assert item is not None
        assert item.type == "learning_snapshot"
        assert item.payload["total_vocab"] == 24
        assert item.payload["mastered_vocab"] == 6
        assert item.payload["recent_vocabulary_attempt_count"] == 3
        assert item.payload["recent_words"] == ["weather", "usually"]
        assert item.payload["grammar_learned"] == 3
        assert item.payload["recent_grammar_titles"] == ["一般现在时"]
        assert "词汇库共 24 个词" in item.summary
        assert "已学语法 3 个" in item.summary

    @pytest.mark.asyncio
    async def test_chat_memory_context_prepends_learning_snapshot(self, monkeypatch):
        learner_id = uuid.uuid4()
        snapshot = chat_api.RetrievedMemoryItem(
            id="learning_snapshot:current",
            type="learning_snapshot",
            skill="general",
            summary="学习快照：词汇库共 2 个词。已学语法 1 个：一般现在时。",
            confidence=1.0,
            layer="context",
        )
        older_item = chat_api.RetrievedMemoryItem(
            id="learning_memory_event:old",
            type="learning_event",
            skill="general",
            summary="旧记忆",
            confidence=0.8,
            layer="evidence",
        )

        class FakeRetriever:
            def __init__(self, db):
                self.db = db

            async def for_chat(self, **kwargs):
                return chat_api.MemoryContext(
                    loaded_items=[older_item],
                    retrieval_reason="chat",
                )

        monkeypatch.setattr(chat_api, "MemoryRetriever", FakeRetriever)
        monkeypatch.setattr(chat_api, "_learning_snapshot_item", AsyncMock(return_value=snapshot))

        context = await chat_api._retrieve_memory_context_safely(
            AsyncMock(),
            learner_id=learner_id,
            reason="chat",
            skill_focus=None,
            thread_id=uuid.uuid4(),
        )

        assert [item.id for item in context.loaded_items] == [
            "learning_snapshot:current",
            "learning_memory_event:old",
        ]


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
        assert request_messages == []
        assert [message.role for message in persisted_messages] == ["user", "assistant"]
        assert [message.sequence for message in persisted_messages] == [1, 2]
        assert persisted_messages[0].content == "开始练习"
        assert persisted_messages[1].content == "你好，我们开始练习。"

    @pytest.mark.asyncio
    async def test_chat_stream_model_http_error_returns_error_event_without_assistant_message(
        self, client, mock_model_router, mock_session, mock_stream_persist_session
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
        persisted_messages = [
            obj
            for obj in mock_stream_persist_session.added_objects
            if isinstance(obj, ConversationMessage)
        ]
        assert messages == []
        assert persisted_messages == []

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

    @pytest.mark.asyncio
    async def test_chat_stream_emits_vocabulary_skill_events_after_done(
        self, client, mock_model_router, mock_session, mock_stream_persist_session, monkeypatch
    ):
        async def stream_chat(request):
            yield ChatStreamChunk(content="significant means important.")
            yield ChatStreamChunk(finish_reason="stop")

        async def fake_vocabulary_agent(**kwargs):
            return chat_api.VocabularyAgentResult(saved_count=2)

        mock_model_router.stream_chat = stream_chat
        monkeypatch.setattr(chat_api, "_run_vocabulary_agent_background", fake_vocabulary_agent)

        response = await client.post(
            "/api/chat/stream",
            json={
                "learner_id": str(mock_session.learner_id),
                "message": "讲解 significant",
                "skill_focus": "vocabulary",
            },
        )

        assert response.status_code == 200
        body = response.text
        assert "event: done" in body
        assert "event: skill" in body
        assert '"skill_id": "vocabulary_deposit"' in body
        assert '"status": "started"' in body
        assert '"status": "completed"' in body
        assert '"saved_count": 2' in body
