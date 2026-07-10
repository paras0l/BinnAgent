import ast
from pathlib import Path


def test_alembic_migrations_have_single_head_revision() -> None:
    revisions: set[str] = set()
    parents: set[str] = set()

    for path in Path("alembic/versions").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        revision = None
        down_revision = None
        for node in tree.body:
            if not isinstance(node, ast.AnnAssign | ast.Assign):
                continue
            targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
            target_names = {target.id for target in targets if isinstance(target, ast.Name)}
            value = node.value
            if value is None:
                continue
            if "revision" in target_names:
                revision = ast.literal_eval(value)
            if "down_revision" in target_names:
                down_revision = ast.literal_eval(value)

        assert isinstance(revision, str), f"{path} is missing revision"
        revisions.add(revision)
        if isinstance(down_revision, str):
            parents.add(down_revision)
        elif isinstance(down_revision, tuple | list):
            parents.update(item for item in down_revision if isinstance(item, str))

    heads = revisions - parents
    assert heads == {"s9t0u1v2w3x4"}


def test_learner_invitation_migration_supports_shared_emails_and_relationships() -> None:
    migration = Path(
        "alembic/versions/q7r8s9t0u1v2_add_learner_email_invites.py"
    ).read_text()

    assert "learners_email_key" in migration
    assert "invite_code" in migration
    assert "invited_by_learner_id" in migration
    assert "uq_learners_invite_code" in migration
    assert "fk_learners_invited_by_learner_id" in migration


def test_email_verification_migration_adds_hashed_expiring_challenges() -> None:
    migration = Path(
        "alembic/versions/r8s9t0u1v2w3_add_email_verification_challenges.py"
    ).read_text()

    assert "email_verification_challenges" in migration
    assert "code_hash" in migration
    assert "code_salt" in migration
    assert "attempt_count" in migration
    assert "expires_at" in migration


def test_exercise_pool_migration_adds_durable_jobs_and_quality_fields() -> None:
    migration = Path(
        "alembic/versions/p6q7r8s9t0u1_add_exercise_generation_pool.py"
    ).read_text()

    assert "exercise_generation_runs" in migration
    assert "uq_exercise_generation_runs_active_dedupe" in migration
    assert "quality_score" in migration
    assert "quality_status" in migration
    assert "generator_version" in migration


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


def test_learning_memory_migration_adds_events_operations_and_governance() -> None:
    migration = Path(
        "alembic/versions/85d6e7f8a9b0_add_learning_memory_events.py"
    ).read_text()

    assert "learning_memory_events" in migration
    assert "memory_operations" in migration
    assert "writing_phrase_masteries" in migration
    assert "memory_context_logs" in migration
    assert "learner_memory_settings" in migration
    assert "emotion_rhythm_enabled" in migration
    assert "status" in migration
    assert "confidence" in migration
    assert "ix_learning_memory_events_learner_skill" in migration


def test_reflective_memory_migration_adds_episode_model_and_strategy_tables() -> None:
    migration = Path(
        "alembic/versions/b6c7d8e9f0a1_add_reflective_memory_models.py"
    ).read_text()

    assert "learning_episodes" in migration
    assert "learner_model_memories" in migration
    assert "teaching_strategy_memories" in migration
    assert "source_event_ids" in migration
    assert "last_reflected_at" in migration
    assert "uq_learning_episode_reflection_key" in migration
    assert "uq_learner_model_memory_claim" in migration
    assert "uq_teaching_strategy_memory" in migration


def test_exercise_attempts_migration_upgrades_existing_attempts_for_targets() -> None:
    migration = Path(
        "alembic/versions/d8e9f0a1b2c3_upgrade_exercise_attempts.py"
    ).read_text()

    assert "exercise_attempts" in migration
    assert "question_id" in migration
    assert "exercise_id" in migration
    assert "target_type" in migration
    assert "target_id" in migration
    assert "target_label" in migration
    assert "curriculum_node" in migration
    assert "should_update_mastery" in migration
    assert "should_create_error_pattern" in migration
    assert "should_create_memory_evidence" in migration
    assert "ix_exercise_attempts_learner_target_created" in migration


def test_learning_graph_checkpoint_migration_adds_waiting_checkpoint_table() -> None:
    migration = Path(
        "alembic/versions/f0a1b2c3d4e5_add_learning_graph_checkpoints.py"
    ).read_text()

    assert "learning_graph_checkpoints" in migration
    assert "agent_episodes.id" in migration
    assert "state_snapshot" in migration
    assert "prompt_payload" in migration
    assert "uq_learning_graph_checkpoints_active_waiting_episode" in migration
    assert "status = 'waiting_user'" in migration


def test_prompt_execution_records_migration_stores_business_indexes_only() -> None:
    migration = Path(
        "alembic/versions/1a2b3c4d5e6f_add_prompt_execution_records.py"
    ).read_text()

    assert "prompt_execution_records" in migration
    assert "langfuse_trace_id" in migration
    assert "schema_validation_status" in migration
    assert "model_policy_snapshot" in migration
    assert "raw_prompt" not in migration
    assert "raw_output" not in migration


def test_parser_run_progress_migration_adds_stage_and_progress() -> None:
    migration = Path("alembic/versions/k1f2a3b4c5d6_add_parser_run_progress.py").read_text()

    assert '"parser_runs"' in migration
    assert '"stage"' in migration
    assert '"progress"' in migration
    assert "queued" in migration
    assert "token" not in migration
    assert "cost" not in migration
    assert "latency" not in migration


def test_group_learning_migration_adds_sources_messages_and_signals() -> None:
    migration = Path("alembic/versions/m3n4o5p6q7r8_add_group_learning_tables.py").read_text()

    assert "group_learning_sources" in migration
    assert "group_learning_participants" in migration
    assert "group_learning_messages" in migration
    assert "group_learning_signals" in migration
    assert "fk_group_learning_sources_learner_id" in migration
    assert "uq_group_learning_source_learner_external_key" in migration
    assert "uq_group_learning_message_source_external" in migration
    assert "uq_group_learning_message_source_hash" in migration
    assert "ix_group_learning_signals_learner_status" in migration


def test_expression_lab_migration_adds_scoped_sessions_actions_attempts_and_events() -> None:
    migration = Path(
        "alembic/versions/s9t0u1v2w3x4_add_expression_lab.py"
    ).read_text()

    for table_name in [
        "expression_lab_sessions",
        "expression_lab_actions",
        "expression_lab_attempts",
        "expression_lab_events",
    ]:
        assert table_name in migration

    assert 'down_revision: Union[str, Sequence[str], None] = "r8s9t0u1v2w3"' in migration
    assert "agent_episodes.id" in migration
    assert "exercise_attempts.id" in migration
    assert "ondelete=\"CASCADE\"" in migration
    assert "ondelete=\"SET NULL\"" in migration
    assert "uq_expression_lab_action_session_spec" in migration
    assert "uq_expression_lab_attempt_sequence" in migration
    assert "ix_expression_lab_sessions_learner_status" in migration
    assert "ix_expression_lab_events_session_occurred" in migration
    assert "prompt_hash" in migration
    assert "raw_prompt" not in migration
    assert "raw_output" not in migration
