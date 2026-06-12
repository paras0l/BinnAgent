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
