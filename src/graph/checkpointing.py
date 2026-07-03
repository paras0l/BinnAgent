from typing import Any


def build_checkpointer(settings: Any | None = None, *, kind: str | None = None) -> Any | None:
    """Build a LangGraph checkpointer for development/test runs.

    This is distinct from ``LearningGraphCheckpoint`` records, which are
    business checkpoints exposed to the frontend for daily lesson recovery.
    """
    mode = (
        kind
        or _setting(settings, "langgraph_checkpointer")
        or _setting(settings, "LANGGRAPH_CHECKPOINTER")
        or _setting(settings, "checkpointer")
    )
    if mode is None:
        return None
    normalized = str(mode).strip().lower()
    if normalized in {"", "none", "false", "disabled", "off"}:
        return None
    if normalized in {"memory", "inmemory", "in_memory", "test"}:
        try:
            from langgraph.checkpoint.memory import InMemorySaver
        except ImportError:
            return None

        return InMemorySaver()
    return None


def _setting(settings: Any | None, name: str) -> Any | None:
    if settings is None:
        return None
    if isinstance(settings, dict):
        return settings.get(name)
    return getattr(settings, name, None)
