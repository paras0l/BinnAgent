from contextlib import contextmanager
from typing import Any, Iterator

from src.config import settings

_langfuse_client = None


def _client():
    global _langfuse_client
    if not (
        settings.langfuse_enabled and settings.langfuse_public_key and settings.langfuse_secret_key
    ):
        return None
    if _langfuse_client is not None:
        return _langfuse_client
    try:
        from langfuse import Langfuse
    except ImportError:
        return None
    _langfuse_client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
        environment=settings.langfuse_environment,
    )
    return _langfuse_client


@contextmanager
def observe(
    name: str,
    *,
    as_type: str = "span",
    input: Any = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    client = _client()
    if client is None:
        yield None
        return
    with client.start_as_current_observation(
        name=name,
        as_type=as_type,
        input=input,
        metadata=metadata,
    ) as observation:
        yield observation


@contextmanager
def observe_langgraph_run(
    *,
    name: str,
    user_id: str,
    session_id: str,
    thread_id: str,
    input: Any,
) -> Iterator[dict[str, Any]]:
    client = _client()
    base_config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
    }
    if client is None:
        yield base_config
        return

    from langfuse import propagate_attributes
    from langfuse.langchain import CallbackHandler

    with client.start_as_current_observation(
        name=name,
        as_type="agent",
        input=input,
        metadata={"provider": "ollama", "local_model": True},
    ) as agent:
        with propagate_attributes(
            user_id=user_id,
            session_id=session_id,
            tags=["langgraph", "ollama", "local-model"],
            trace_name=name,
        ):
            config = {
                **base_config,
                "callbacks": [CallbackHandler()],
                "metadata": {
                    "langfuse_user_id": user_id,
                    "langfuse_session_id": session_id,
                    "langfuse_tags": ["langgraph", "ollama", "local-model"],
                },
            }
            try:
                yield config
            except Exception as exc:
                agent.update(level="ERROR", status_message=str(exc)[:500])
                raise


def shutdown_observability() -> None:
    global _langfuse_client
    client = _client()
    if client is not None:
        client.shutdown()
        _langfuse_client = None
