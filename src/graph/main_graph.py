from langgraph.graph import END, StateGraph

from src.graph.checkpointing import build_checkpointer
from src.graph.nodes.detect_intent import detect_intent
from src.graph.nodes.generate_feedback import generate_feedback
from src.graph.nodes.grade_attempt import grade_attempt
from src.graph.nodes.load_profile import load_profile
from src.graph.nodes.recommend_learning_action import recommend_learning_action
from src.graph.nodes.route_skill import route_skill_agent
from src.graph.nodes.run_task import run_learning_task
from src.graph.nodes.schedule_review import schedule_review
from src.graph.nodes.select_goal import select_learning_goal
from src.graph.nodes.summarize import summarize_session
from src.graph.nodes.update_mastery import update_mastery
from src.graph.nodes.update_memory import update_memory
from src.graph.nodes.verify_episode import verify_episode
from src.graph.nodes.wait_for_answer import wait_for_answer
from src.graph.state import LearningGraphState

__all__ = [
    "build_checkpointer",
    "build_graph",
    "build_resume_graph",
    "daily_lesson_graph",
    "daily_lesson_resume_graph",
    "route_after_task",
]


def route_after_task(state: LearningGraphState) -> str:
    if state.get("answer_required") and not state.get("learner_answer"):
        return "interrupt"
    return "continue"


def build_graph(checkpointer=None):
    """Build the daily lesson graph with a user-input interruption point."""
    graph = StateGraph(LearningGraphState)

    graph.add_node("load_profile", load_profile)
    graph.add_node("detect_intent", detect_intent)
    graph.add_node("select_learning_goal", select_learning_goal)
    graph.add_node("route_skill_agent", route_skill_agent)
    graph.add_node("run_learning_task", run_learning_task)
    graph.add_node("wait_for_answer", wait_for_answer)
    graph.add_node("grade_attempt", grade_attempt)
    graph.add_node("update_mastery", update_mastery)
    graph.add_node("generate_feedback", generate_feedback)
    graph.add_node("update_memory", update_memory)
    graph.add_node("schedule_review", schedule_review)
    graph.add_node("recommend_learning_action", recommend_learning_action)
    graph.add_node("verify_episode", verify_episode)
    graph.add_node("summarize_session", summarize_session)

    graph.set_entry_point("load_profile")
    graph.add_edge("load_profile", "detect_intent")
    graph.add_edge("detect_intent", "select_learning_goal")
    graph.add_edge("select_learning_goal", "route_skill_agent")
    graph.add_edge("route_skill_agent", "run_learning_task")
    graph.add_edge("run_learning_task", "wait_for_answer")
    graph.add_conditional_edges(
        "wait_for_answer",
        route_after_task,
        {
            "interrupt": END,
            "continue": "grade_attempt",
        },
    )
    graph.add_edge("grade_attempt", "update_mastery")
    graph.add_edge("update_mastery", "generate_feedback")
    graph.add_edge("generate_feedback", "update_memory")
    graph.add_edge("update_memory", "schedule_review")
    graph.add_edge("schedule_review", "recommend_learning_action")
    graph.add_edge("recommend_learning_action", "verify_episode")
    graph.add_edge("verify_episode", "summarize_session")
    graph.add_edge("summarize_session", END)

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def build_resume_graph(start_node: str = "grade_attempt", checkpointer=None):
    """Build a resume graph for continuing after a persisted checkpoint."""
    allowed_start_nodes = {
        "grade_attempt",
        "update_mastery",
        "generate_feedback",
        "update_memory",
        "schedule_review",
        "recommend_learning_action",
        "verify_episode",
        "summarize_session",
    }
    if start_node not in allowed_start_nodes:
        raise ValueError(f"Unsupported resume start node: {start_node}")

    graph = StateGraph(LearningGraphState)
    graph.add_node("grade_attempt", grade_attempt)
    graph.add_node("update_mastery", update_mastery)
    graph.add_node("generate_feedback", generate_feedback)
    graph.add_node("update_memory", update_memory)
    graph.add_node("schedule_review", schedule_review)
    graph.add_node("recommend_learning_action", recommend_learning_action)
    graph.add_node("verify_episode", verify_episode)
    graph.add_node("summarize_session", summarize_session)

    graph.set_entry_point(start_node)
    if start_node == "grade_attempt":
        graph.add_edge("grade_attempt", "update_mastery")
    if start_node in {"grade_attempt", "update_mastery"}:
        graph.add_edge("update_mastery", "generate_feedback")
    if start_node in {"grade_attempt", "update_mastery", "generate_feedback"}:
        graph.add_edge("generate_feedback", "update_memory")
    if start_node in {"grade_attempt", "update_mastery", "generate_feedback", "update_memory"}:
        graph.add_edge("update_memory", "schedule_review")
    if start_node in {
        "grade_attempt",
        "update_mastery",
        "generate_feedback",
        "update_memory",
        "schedule_review",
    }:
        graph.add_edge("schedule_review", "recommend_learning_action")
    if start_node in {
        "grade_attempt",
        "update_mastery",
        "generate_feedback",
        "update_memory",
        "schedule_review",
        "recommend_learning_action",
    }:
        graph.add_edge("recommend_learning_action", "verify_episode")
    if start_node in {
        "grade_attempt",
        "update_mastery",
        "generate_feedback",
        "update_memory",
        "schedule_review",
        "recommend_learning_action",
        "verify_episode",
    }:
        graph.add_edge("verify_episode", "summarize_session")
    graph.add_edge("summarize_session", END)

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


daily_lesson_graph = build_graph()
daily_lesson_resume_graph = build_resume_graph()
