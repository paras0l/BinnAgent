from src.graph.state import LearningState

KEYWORD_MAP: dict[str, str] = {
    "单词": "vocabulary",
    "背词": "vocabulary",
    "词汇": "vocabulary",
    "vocabulary": "vocabulary",
    "阅读": "reading",
    "reading": "reading",
    "文章": "reading",
    "写作": "writing",
    "作文": "writing",
    "writing": "writing",
    "essay": "writing",
    "复习": "vocabulary",
    "review": "vocabulary",
}


async def detect_intent(state: LearningState) -> dict:
    """Detect learning intent from the last user message using keyword matching."""
    messages = state.get("messages", [])
    if not messages:
        return {"active_skill": "reading"}

    last_message = messages[-1]
    content = ""
    if isinstance(last_message, dict):
        content = last_message.get("content", "")
    else:
        content = getattr(last_message, "content", "")

    content_lower = content.lower()
    for keyword, skill in KEYWORD_MAP.items():
        if keyword.lower() in content_lower:
            return {"active_skill": skill}

    return {"active_skill": "reading"}
