from src.prompts import prompt_registry


def test_prompt_registry_renders_prompt_with_hash_and_schema() -> None:
    rendered = prompt_registry.render(
        prompt_id="writing_phrase.import",
        version="v1",
        variables={"topic": "online learning", "task_type": "generate"},
    )

    assert rendered.prompt_id == "writing_phrase.import"
    assert rendered.version == "v1"
    assert "online learning" in rendered.prompt
    assert len(rendered.prompt_hash) == 64
    assert rendered.output_schema == "WritingPhraseImportOutput"
    assert rendered.output_schema_json is not None


def test_prompt_registry_lists_core_prompts() -> None:
    ids = {item.id for item in prompt_registry.list()}

    assert {
        "conversation.summary",
        "dictionary.lookup",
        "essay.scoring",
        "explore.capability_rerank",
        "exercise.generate",
        "graph.feedback",
        "graph.node",
        "group_learning.signal_extract",
        "reading.material_generation",
        "tutor.chat",
        "vocabulary.agent.extract",
        "vocabulary.detail_html_extract",
        "vocabulary.local_enrichment",
        "grammar.micro_lesson.structured",
        "writing_phrase.import",
    } <= ids
