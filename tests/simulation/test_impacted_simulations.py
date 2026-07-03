from scripts.list_impacted_simulations import impacted_payload


def test_impacted_simulations_match_graph_changes() -> None:
    payload = impacted_payload(["src/graph/main_graph.py"])

    ids = {item["id"] for item in payload["scenarios"]}
    assert "smoke_learning_journey" in ids
    assert "daily_lesson_checkpoint_resume" in ids
    assert "langgraph" in payload["module_tags"]


def test_impacted_simulations_prompt_changes_include_prompt_regression() -> None:
    payload = impacted_payload(["src/prompts/registry.py"])

    ids = {item["id"] for item in payload["scenarios"]}
    assert "llm_json_missing_field_triggers_repair" in ids
    assert "prompt_schema" in payload["module_tags"]


def test_impacted_simulations_knowledge_changes_include_runtime_knowledge_practice() -> None:
    payload = impacted_payload(["src/knowledge/processor.py"])

    ids = {item["id"] for item in payload["scenarios"]}
    assert "episode_runtime_knowledge_practice" in ids
    assert "knowledge" in payload["module_tags"]
