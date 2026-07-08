import uuid

import pytest

from src.models.prompt_execution import PromptExecutionRecord
from src.prompts.executor import PromptExecutionContext, PromptExecutor
from src.providers.base import ChatResponse, ChatStreamChunk


class FakeDb:
    def __init__(self) -> None:
        self.records: list[PromptExecutionRecord] = []

    def add(self, record: PromptExecutionRecord) -> None:
        self.records.append(record)

    async def flush(self) -> None:
        return None


class FakeRouter:
    def __init__(self, content: str) -> None:
        self.content = content
        self.requests = []

    async def chat(self, request):
        self.requests.append(request)
        return ChatResponse(provider="test", model="fake", content=self.content)

    async def stream_chat(self, request):
        self.requests.append(request)
        yield ChatStreamChunk(content="hello ")
        yield ChatStreamChunk(content="world", finish_reason="stop")


@pytest.mark.asyncio
async def test_prompt_executor_success_writes_prompt_execution_record() -> None:
    db = FakeDb()
    router = FakeRouter(
        '{"candidates": [{"text": "What matters most is that...", "quality_score": 0.9}]}'
    )

    result = await PromptExecutor(db=db, model_router=router).execute(
        prompt_id="writing_phrase.import",
        version="v1",
        variables={"topic": "online learning", "task_type": "extract_phrases"},
        context=PromptExecutionContext(
            learner_id=uuid.uuid4(),
            source_module="tests.prompt_executor",
            target_type="writing_phrase",
        ),
    )

    assert result.decision == "accepted"
    assert result.schema_validation_status == "passed"
    assert result.execution_record_id == db.records[0].id
    assert len(result.prompt_hash) == 64
    assert len(result.input_hash) == 64
    assert router.requests[0].response_schema is not None
    record = db.records[0]
    assert record.prompt_id == "writing_phrase.import"
    assert record.prompt_hash == result.prompt_hash
    assert not hasattr(record, "raw_prompt")
    assert not hasattr(record, "raw_output")


@pytest.mark.asyncio
async def test_prompt_executor_fallback_record_is_review_required() -> None:
    db = FakeDb()

    result = await PromptExecutor(db=db).execute_with_raw_output(
        prompt_id="writing_phrase.import",
        version="v1",
        variables={"topic": "online learning", "task_type": "extract_phrases"},
        raw_output="英文句式：What matters most is that...\n例句：What matters most is that we keep learning.",
        context=PromptExecutionContext(source_module="tests.prompt_executor"),
        fallback_parser=lambda _raw: {
            "candidates": [
                {
                    "text": "What matters most is that...",
                    "examples": [{"sentence": "What matters most is that we keep learning."}],
                    "quality_score": 0.72,
                }
            ]
        },
    )

    assert result.fallback_used is True
    assert result.parse_mode == "regex_fallback"
    assert result.decision == "review_required"
    assert db.records[0].decision == "review_required"
    assert db.records[0].schema_validation_status == "fallback"


@pytest.mark.asyncio
async def test_prompt_executor_execute_messages_records_text_prompt() -> None:
    db = FakeDb()
    router = FakeRouter("plain response")

    result = await PromptExecutor(db=db, model_router=router).execute_messages(
        prompt_id="graph.node",
        variables={"system_prompt": "system", "messages": [{"role": "user", "content": "hi"}]},
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hi"},
        ],
        context=PromptExecutionContext(source_module="tests.prompt_executor"),
        request_overrides={"task_type": "graph_node", "temperature": 0.2, "max_tokens": 128},
    )

    assert result.raw_output == "plain response"
    assert result.schema_validation_status == "not_applicable"
    assert result.decision == "accepted"
    assert router.requests[0].task_type == "graph_node"
    assert router.requests[0].messages[0]["content"] == "system"
    assert db.records[0].prompt_id == "graph.node"
    assert db.records[0].decision == "accepted"


@pytest.mark.asyncio
async def test_prompt_executor_stream_messages_records_after_stream() -> None:
    db = FakeDb()
    router = FakeRouter("")

    chunks = []
    async for chunk in PromptExecutor(db=db, model_router=router).stream_messages(
        prompt_id="tutor.chat",
        variables={"message": "hi"},
        messages=[{"role": "user", "content": "hi"}],
        context=PromptExecutionContext(source_module="tests.prompt_executor"),
        request_overrides={"task_type": "learning_chat"},
    ):
        chunks.append(chunk.content)

    assert chunks == ["hello ", "world"]
    assert db.records[0].prompt_id == "tutor.chat"
    assert db.records[0].schema_validation_status == "not_applicable"
    assert db.records[0].decision == "accepted"
