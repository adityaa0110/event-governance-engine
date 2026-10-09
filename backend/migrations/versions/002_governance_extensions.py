"""Add review comments, recommendation decisions, and tracking wrappers.

Revision ID: 002_extensions
Revises: 001_initial
Create Date: 2026-10-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "002_extensions"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    if table not in inspect(bind).get_table_names():
        return set()
    return {column["name"] for column in inspect(bind).get_columns(table)}


def upgrade() -> None:
    if "event_versions" in inspect(op.get_bind()).get_table_names() and "comment" not in _columns("event_versions"):
        op.add_column("event_versions", sa.Column("comment", sa.Text(), nullable=False, server_default=""))
    if "audit_logs" in inspect(op.get_bind()).get_table_names() and "comment" not in _columns("audit_logs"):
        op.add_column("audit_logs", sa.Column("comment", sa.Text(), nullable=False, server_default=""))
    tables = set(inspect(op.get_bind()).get_table_names())
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


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "tracking_functions" in tables:
        op.drop_index("ix_tracking_functions_name", table_name="tracking_functions")
        op.drop_table("tracking_functions")
    if "recommendation_decisions" in tables:
        op.drop_index("ix_recommendation_decisions_event_name", table_name="recommendation_decisions")
        op.drop_table("recommendation_decisions")
    if "comment" in _columns("audit_logs"):
        op.drop_column("audit_logs", "comment")
    if "comment" in _columns("event_versions"):
        op.drop_column("event_versions", "comment")
