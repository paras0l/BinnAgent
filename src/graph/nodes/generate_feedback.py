from src.graph.state import LearningGraphState as LearningState
from src.prompts import PromptExecutionContext, PromptExecutor
from src.providers.router import router


async def generate_feedback(state: LearningState) -> dict:
    learner_answer = state.get("learner_answer")
    input_materials = state.get("input_materials", [])
    active_skill = state.get("active_skill", "reading")
    grade_result = state.get("grade_result") or {}
    wrong_reason = state.get("wrong_reason")
    if grade_result.get("feedback"):
        return {
            "agent_feedback": {
                "summary": str(grade_result["feedback"]),
                "key_issues": [wrong_reason] if wrong_reason else [],
                "strengths": ["回答正确"] if grade_result.get("correct") else [],
                "drill": None if grade_result.get("correct") else "根据提示再完成一次同类题。",
            }
        }

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
    grade_context = ""
    if grade_result:
        grade_context = (
            f"\n评分: {'正确' if grade_result.get('correct') else '需要改进'}"
            f"\n得分: {grade_result.get('score', 0)}"
            f"\n错误原因: {wrong_reason or grade_result.get('error_type') or '无'}"
        )

    user_msg = f"技能类型: {active_skill}\n练习内容:\n{material_context}{answer_context}{grade_context}"

    try:
        result = await PromptExecutor(model_router=router).execute(
            prompt_id="graph.feedback",
            variables={"user_msg": user_msg},
            context=PromptExecutionContext(
                source_module="graph.generate_feedback",
                task_id="graph_feedback",
                target_type=str(active_skill),
            ),
            request_overrides={"task_type": "graph_feedback"},
        )
        if result.decision != "accepted" or result.validated_output is None:
            raise ValueError("graph feedback output was not accepted")
        feedback_data = result.validated_output
        feedback = {
            "summary": feedback_data.get("summary", "练习已完成"),
            "key_issues": feedback_data.get("improvements", []),
            "strengths": feedback_data.get("strengths", []),
            "drill": feedback_data.get("drill"),
        }
    except Exception:
        if grade_result.get("feedback"):
            summary = str(grade_result["feedback"])
        else:
            summary = f"已完成{active_skill}练习"
        feedback = {
            "summary": summary,
            "key_issues": [wrong_reason] if wrong_reason else [],
            "drill": None,
        }

    return {"agent_feedback": feedback}
