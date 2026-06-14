from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock


def load_reset_data_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "reset_data.py"
    spec = importlib.util.spec_from_file_location("reset_data", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_app_tables_include_business_tables_and_exclude_alembic():
    module = load_reset_data_module()

    tables = set(module.app_tables())

    assert "learners" in tables
    assert "conversation_messages" in tables
    assert "vocabulary_items" in tables
    assert "explore_feature_preferences" in tables
    assert "alembic_version" not in tables


def test_local_database_detection_accepts_local_hosts():
    module = load_reset_data_module()

    assert module.is_local_database("postgresql+asyncpg://binn:binn@localhost:5432/binn_agent")
    assert module.is_local_database("postgresql+asyncpg://binn:binn@127.0.0.1:5432/binn_agent")
    assert module.is_local_database("postgresql+asyncpg://binn:binn@db:5432/binn_agent")
    assert not module.is_local_database("postgresql+asyncpg://binn:binn@example.com/binn_agent")


def test_main_defaults_to_dry_run_without_confirm(monkeypatch):
    module = load_reset_data_module()
    reset_database = AsyncMock(return_value=0)
    monkeypatch.setattr(module, "reset_database", reset_database)

    exit_code = module.main(["--database-url", "postgresql+asyncpg://binn:binn@localhost/db"])

    assert exit_code == 0
    reset_database.assert_awaited_once()
    assert reset_database.await_args.kwargs["dry_run"] is True
    assert reset_database.await_args.kwargs["confirm"] is None


def test_main_clears_only_with_confirmation_token(monkeypatch):
    module = load_reset_data_module()
    reset_database = AsyncMock(return_value=0)
    monkeypatch.setattr(module, "reset_database", reset_database)

    exit_code = module.main(
        [
            "--database-url",
            "postgresql+asyncpg://binn:binn@localhost/db",
            "--confirm",
            "RESET_ALL_DATA",
        ]
    )

    assert exit_code == 0
    reset_database.assert_awaited_once()
    assert reset_database.await_args.kwargs["dry_run"] is False
    assert reset_database.await_args.kwargs["confirm"] == "RESET_ALL_DATA"


def test_reset_database_refuses_non_local_database_without_override():
    module = load_reset_data_module()

    exit_code = module.main(
        [
            "--database-url",
            "postgresql+asyncpg://binn:binn@example.com/prod",
            "--dry-run",
        ]
    )

    assert exit_code == 2
