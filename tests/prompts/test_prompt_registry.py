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
        "exercise.unit_candidates",
        "exercise.unit_review",
        "graph.feedback",
        "graph.node",
        "group_learning.signal_extract",
        "reading.material_generation",
        "tutor.chat",
        "vocabulary.agent.extract",
        "vocabulary.detail_html_extract",
        "vocabulary.local_enrichment",
        "vocabulary.learning_supplement",
        "grammar.micro_lesson.structured",
        "writing_phrase.import",
    } <= ids


def test_vocabulary_learning_supplement_prompt_binds_structured_schema() -> None:
    rendered = prompt_registry.render(
        prompt_id="vocabulary.learning_supplement",
        version="v1",
        variables={
            "canonical_form": "shut down",
            "entry_type": "phrasal_verb",
            "existing_entry": "{}",
            "requested_sections": "common_errors, must_remember",
        },
    )

    assert "shut down" in rendered.prompt
    assert "common_errors, must_remember" in rendered.prompt
    assert rendered.output_schema == "VocabularyLearningSupplementOutput"
    assert rendered.output_schema_json is not None
