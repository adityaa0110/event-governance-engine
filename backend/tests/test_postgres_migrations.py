"""Upgrade and roll back the schema on PostgreSQL when a test URL is set."""

import os
from pathlib import Path

import pytest

pytest.importorskip("psycopg")

POSTGRES_URL = os.getenv("POSTGRES_TEST_URL", "")


@pytest.mark.skipif(not POSTGRES_URL, reason="POSTGRES_TEST_URL is not set")
def test_postgres_upgrade_and_rollback(monkeypatch):
    from alembic import command
    from alembic.config import Config

    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    backend = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
