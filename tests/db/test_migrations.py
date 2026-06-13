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
