import json as _json

from src.graph.llm import call_llm
from src.graph.state import LearningGraphState as LearningState


async def generate_feedback(state: LearningState) -> dict:
    learner_answer = state.get("learner_answer")
    input_materials = state.get("input_materials", [])
    active_skill = state.get("active_skill", "reading")

    material_context = ""
    if input_materials:
        first = input_materials[0] if input_materials else {}
        if isinstance(first, dict):
            if first.get("type") == "reading_question":
                material_context = f"阅读题目: {first.get('stem', '')}\n选项: {', '.join(first.get('options', []))}"
            elif first.get("type") == "writing_prompt":
                material_context = f"写作题目: {first.get('content', '')}"
            elif first.get("type") == "vocabulary_list":
                words = [w.get("word", "") for w in first.get("words", [])]
                material_context = f"词汇列表: {', '.join(words)}"

    answer_context = ""
    if learner_answer:
        answer_context = f"\n学员作答: {learner_answer.get('answer', '未提供')}"

    user_msg = f"技能类型: {active_skill}\n练习内容:\n{material_context}{answer_context}"

    try:
        response_text = await call_llm(
            messages=[
                {"role": "user", "content": f"请用中文为以下英语学习练习提供反馈：\n\n{user_msg}"}
            ],
            system_prompt=(
                "你是一位专业的英语学习AI助教。请为学员的练习提供具体的、有建设性的反馈。"
                "包括：1)做得好的地方 2)需要改进的地方 3)具体建议。控制在150字以内。"
                '用JSON格式回复：{"summary": "总结", "strengths": ["优点"], "improvements": ["改进建议"], "drill": "建议的练习"}'
            ),
            temperature=0.7,
            max_tokens=500,
        )

        try:
            feedback_data = _json.loads(response_text)
            feedback = {
                "summary": feedback_data.get("summary", "练习已完成"),
                "key_issues": feedback_data.get("improvements", []),
                "strengths": feedback_data.get("strengths", []),
                "drill": feedback_data.get("drill"),
            }
        except (_json.JSONDecodeError, TypeError):
            feedback = {
                "summary": response_text[:200],
                "key_issues": [],
                "drill": None,
            }
    except Exception:
        feedback = {
            "summary": f"已完成{active_skill}练习",
            "key_issues": [],
            "drill": None,
        }

    return {"agent_feedback": feedback}
