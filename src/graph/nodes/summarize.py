from src.graph.llm import call_llm
from src.graph.state import LearningState


async def summarize_session(state: LearningState) -> dict:
    skill = state.get("active_skill", "reading")
    goal = state.get("today_goal", "")
    feedback = state.get("agent_feedback", {})
    review_items = state.get("review_items", [])

    context_parts = [f"学习技能: {skill}", f"今日目标: {goal}"]
    if feedback and isinstance(feedback, dict):
        context_parts.append(f"反馈摘要: {feedback.get('summary', '无')}")
    if review_items:
        context_parts.append(f"待复习项目: {len(review_items)} 项")

    user_msg = "\n".join(context_parts)

    try:
        summary = await call_llm(
            messages=[
                {
                    "role": "user",
                    "content": f"请用中文为以下英语学习session写一段简短的学习总结，鼓励学员继续加油：\n\n{user_msg}",
                }
            ],
            system_prompt="你是一位专业的英语学习AI助教。请用简洁友好的中文为学员生成学习总结。总结应该包括：1)今天学了什么 2)表现如何 3)下一步建议。控制在100字以内。",
            temperature=0.7,
            max_tokens=300,
        )
    except Exception:
        summary = f"## 学习总结\n\n今日技能: {skill}\n今日目标: {goal}\n\n继续保持！"

    return {"messages": [{"role": "assistant", "content": summary}]}
