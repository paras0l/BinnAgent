from datetime import datetime

import pytest

from src.graph.nodes.update_memory import update_memory


@pytest.mark.asyncio
async def test_update_memory_uses_runtime_timestamp() -> None:
    result = await update_memory(
        {
            "active_skill": "writing",
            "learner_answer": {"answer": "My essay"},
            "agent_feedback": {"summary": "Good structure"},
        }
    )

    [candidate] = result["memory_candidates"]
    timestamp = candidate["timestamp"]

    assert timestamp != "2026-01-01T00:00:00"
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.tzinfo is not None
    assert candidate["metadata"]["active_skill"] == "writing"
    assert candidate["metadata"]["feedback_summary"] == "Good structure"
