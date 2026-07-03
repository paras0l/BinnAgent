from scripts.list_impacted_simulations import impacted_payload


def test_impacted_simulations_match_graph_changes() -> None:
    payload = impacted_payload(["src/graph/main_graph.py"])

    ids = {item["id"] for item in payload["scenarios"]}
    assert "smoke_learning_journey" in ids
    assert "daily_lesson_checkpoint_resume" in ids
    assert "langgraph" in payload["module_tags"]


def test_impacted_simulations_prompt_changes_can_be_empty() -> None:
    payload = impacted_payload(["src/prompts/registry.py"])

    assert payload["scenarios"] == []
    assert payload["module_tags"] == []


def test_impacted_simulations_parser_changes_can_be_empty() -> None:
    payload = impacted_payload(["src/knowledge/processor.py"])

    assert payload["scenarios"] == []
    assert payload["module_tags"] == []
