from pathlib import Path


def test_initial_migration_enables_pgcrypto_for_gen_random_uuid() -> None:
    migration = Path("alembic/versions/d92b8a1e392d_initial_tables.py").read_text()

    assert 'CREATE EXTENSION IF NOT EXISTS "pgcrypto"' in migration
    assert "gen_random_uuid()" in migration


def test_foreign_key_migration_covers_core_tables() -> None:
    migration = Path(
        "alembic/versions/4b1f2c3d4e5f_add_foreign_key_constraints.py"
    ).read_text()

    for constraint_name in [
        "fk_learning_sessions_learner_id",
        "fk_vocabulary_items_learner_id",
        "fk_review_schedules_learner_id",
        "fk_agent_runs_thread_id",
        "fk_model_call_logs_run_id",
    ]:
        assert constraint_name in migration


def test_foreign_key_migration_deduplicates_vocabulary_case_insensitively() -> None:
    migration = Path(
        "alembic/versions/4b1f2c3d4e5f_add_foreign_key_constraints.py"
    ).read_text()

    assert "uq_vocabulary_items_learner_lower_word" in migration
    assert "lower(word)" in migration
    assert "unique=True" in migration


def test_conversation_message_migration_links_learners_and_threads() -> None:
    migration = Path(
        "alembic/versions/7c2d9e1f3a4b_add_conversation_messages.py"
    ).read_text()

    assert "conversation_messages" in migration
    assert "fk_conversation_messages_learner_id" in migration
    assert "fk_conversation_messages_thread_id" in migration
    assert "ix_conversation_messages_learner_thread_created" in migration


def test_conversation_message_sequence_migration_backfills_stable_order() -> None:
    migration = Path(
        "alembic/versions/8d3e4f5a6b7c_add_conversation_message_sequence.py"
    ).read_text()

    assert "sequence" in migration
    assert "row_number() OVER" in migration
    assert "uq_conversation_messages_thread_sequence" in migration
    assert "ix_conversation_messages_learner_thread_sequence" in migration


def test_explore_feature_preferences_migration_persists_learner_favorites() -> None:
    migration = Path(
        "alembic/versions/9e4f5a6b7c8d_add_explore_feature_preferences.py"
    ).read_text()

    assert "explore_feature_preferences" in migration
    assert "fk_explore_feature_preferences_learner_id" in migration
    assert "uq_explore_feature_preferences_learner_feature" in migration
    assert "last_used_at" in migration


def test_learning_progress_migration_persists_grammar_and_pronunciation_memory() -> None:
    migration = Path(
        "alembic/versions/a1b2c3d4e5f6_add_learning_progress_items.py"
    ).read_text()

    assert "learning_progress_items" in migration
    assert "fk_learning_progress_items_learner_id" in migration
    assert "uq_learning_progress_learner_skill_item" in migration
    assert "is_favorite" in migration
    assert "learned_at" in migration
    assert "metadata" in migration


def test_knowledge_source_sha256_migration_scopes_duplicates_to_owner() -> None:
    migration = Path(
        "alembic/versions/52a3b4c5d6e7_scope_knowledge_source_sha256_to_owner.py"
    ).read_text()

    assert "knowledge_sources_sha256_key" in migration
    assert "uq_knowledge_sources_owner_sha256" in migration
    assert '["owner_learner_id", "sha256"]' in migration


def test_vocabulary_personal_card_migration_adds_override_mastery_and_mistakes() -> None:
    migration = Path(
        "alembic/versions/74c5d6e7f8a9_add_vocabulary_personal_cards.py"
    ).read_text()

    assert "vocabulary_user_overrides" in migration
    assert "vocabulary_mastery_vectors" in migration
    assert "vocabulary_mistakes" in migration
    assert "hidden_meaning_ids" in migration
    assert "recognition" in migration
    assert "production" in migration
    assert "reason" in migration
    assert "priority" in migration
