from src.graph.state import LearningState


async def route_skill_agent(state: LearningState) -> dict:
    """Route to the appropriate skill handler. Currently passes active_skill through."""
    return {"active_skill": state.get("active_skill", "reading")}
