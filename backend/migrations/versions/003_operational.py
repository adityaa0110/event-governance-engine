"""Add locking, AI run records, traces, and wrapper signatures.

Revision ID: 003_operational
Revises: 002_extensions
Create Date: 2026-10-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "003_operational"
down_revision = "002_extensions"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table)}


def _add(table: str, column: sa.Column) -> None:
    if table in _tables() and column.name not in _columns(table):
        op.add_column(table, column)


def _ensure_extension_tables() -> None:
    """Heal a legacy database that was stamped at 002 without those objects."""
    tables = _tables()
    if "event_versions" in tables and "comment" not in _columns("event_versions"):
        op.add_column("event_versions", sa.Column("comment", sa.Text(), nullable=False, server_default=""))
    if "audit_logs" in tables and "comment" not in _columns("audit_logs"):
        op.add_column("audit_logs", sa.Column("comment", sa.Text(), nullable=False, server_default=""))
    if "recommendation_decisions" not in tables:
        op.create_table(
            "recommendation_decisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("requirement", sa.Text(), nullable=False, server_default=""),
            sa.Column("event_name", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("decision", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_recommendation_decisions_event_name", "recommendation_decisions", ["event_name"])
    if "tracking_functions" not in tables:
        op.create_table(
            "tracking_functions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_tracking_functions_name", "tracking_functions", ["name"], unique=True)


def upgrade() -> None:
    _ensure_extension_tables()
    _add("events", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    _add("validation_results", sa.Column("trace_id", sa.String(length=64), nullable=False, server_default=""))
    _add("audit_logs", sa.Column("trace_id", sa.String(length=64), nullable=False, server_default=""))
    _add("recommendation_decisions", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    _add("recommendation_decisions", sa.Column("response_json", sa.Text(), nullable=False, server_default=""))
    _add("tracking_functions", sa.Column("style", sa.String(length=32), nullable=False, server_default="auto"))
    _add("tracking_functions", sa.Column("event_arg", sa.Integer(), nullable=False, server_default="0"))
    _add("tracking_functions", sa.Column("params_arg", sa.Integer(), nullable=False, server_default="1"))
    if "ix_recommendation_decisions_idempotency_key" not in _indexes("recommendation_decisions"):
        op.create_index(
            "ix_recommendation_decisions_idempotency_key",
            "recommendation_decisions",
            ["idempotency_key"],
            unique=True,
        )
    if "ai_runs" not in _tables():
        op.create_table(
            "ai_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("model", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("prompt_version", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("input_hash", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("requirement_redacted", sa.Text(), nullable=False, server_default=""),
            sa.Column("output_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("fallback_reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("trace_id", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    op.execute("UPDATE events SET status = 'APPROVED' WHERE status = 'ACTIVE'")


def _drop_column(table: str, column: str) -> None:
    if column not in _columns(table):
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch:
            batch.drop_column(column)
    else:
        op.drop_column(table, column)


def downgrade() -> None:
    if "ai_runs" in _tables():
        op.drop_table("ai_runs")
    if "ix_recommendation_decisions_idempotency_key" in _indexes("recommendation_decisions"):
        op.drop_index("ix_recommendation_decisions_idempotency_key", table_name="recommendation_decisions")
    for table, column in (
        ("tracking_functions", "params_arg"),
        ("tracking_functions", "event_arg"),
        ("tracking_functions", "style"),
        ("recommendation_decisions", "response_json"),
        ("recommendation_decisions", "idempotency_key"),
        ("audit_logs", "trace_id"),
        ("validation_results", "trace_id"),
        ("events", "revision"),
    ):
        _drop_column(table, column)
