from src.graph.state import LearningState

SKILL_GOALS: dict[str, dict] = {
    "reading": {
        "today_goal": "练习六级阅读中的转折定位题",
        "estimated_minutes": 20,
        "success_criteria": "完成2篇阅读练习，正确率≥60%",
    },
    "writing": {
        "today_goal": "完成一篇作文练习并获得反馈",
        "estimated_minutes": 25,
        "success_criteria": "完成作文并收到评分反馈",
    },
    "vocabulary": {
        "today_goal": "复习到期词汇并学习新词",
        "estimated_minutes": 15,
        "success_criteria": "复习5个到期词汇，学习3个新词",
    },
}


async def select_learning_goal(state: LearningState) -> dict:
    """Map active_skill to a learning goal with estimated time and success criteria."""
    skill = state.get("active_skill", "reading")
    goal = SKILL_GOALS.get(skill, SKILL_GOALS["reading"])
    return dict(goal)
