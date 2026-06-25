from contextlib import contextmanager
from unittest.mock import patch

from src.observability import observe_langgraph_run


class _Observation:
    def update(self, **kwargs) -> None:
        return None


class _Client:
    @contextmanager
    def start_as_current_observation(self, **kwargs):
        yield _Observation()


def test_langgraph_observation_adds_callback_and_trace_attributes() -> None:
    with patch("src.observability._client", return_value=_Client()):
        with observe_langgraph_run(
            name="daily-lesson-graph",
            user_id="learner-1",
            session_id="session-1",
            thread_id="thread-1",
            input={"message": "practice"},
        ) as config:
            assert config["configurable"]["thread_id"] == "thread-1"
            assert len(config["callbacks"]) == 1
            assert config["metadata"]["langfuse_user_id"] == "learner-1"
            assert config["metadata"]["langfuse_session_id"] == "session-1"


def test_langgraph_observation_is_noop_when_disabled() -> None:
    with patch("src.observability._client", return_value=None):
        with observe_langgraph_run(
            name="daily-lesson-graph",
            user_id="learner-1",
            session_id="session-1",
            thread_id="thread-1",
            input={},
        ) as config:
            assert config == {"configurable": {"thread_id": "thread-1"}}
