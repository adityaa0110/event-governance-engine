"""Parameter constraints, dependency records, and review notices.

Revision ID: 004_catalogue_product
Revises: 003_operational
Create Date: 2026-10-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "004_catalogue_product"
down_revision = "003_operational"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _add(table: str, column: sa.Column) -> None:
    if table in _tables() and column.name not in _columns(table):
        op.add_column(table, column)


def upgrade() -> None:
    _add("event_parameters", sa.Column("allowed_values", sa.Text(), nullable=False, server_default="[]"))
    _add("event_parameters", sa.Column("pii", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add("recommendation_decisions", sa.Column("request_hash", sa.String(length=64), nullable=False, server_default=""))
    if "event_usages" not in _tables():
        op.create_table(
            "event_usages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_name", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("repository", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("file", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("line", sa.Integer(), nullable=True),
            sa.Column("validation_id", sa.Integer(), nullable=True),
            sa.Column("actor", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_event_usages_event_name", "event_usages", ["event_name"])
    if "notifications" not in _tables():
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("audience", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("event_name", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("kind", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("message", sa.Text(), nullable=False, server_default=""),
            sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_notifications_audience", "notifications", ["audience"])
        op.create_index("ix_notifications_event_name", "notifications", ["event_name"])


def _drop_column(table: str, column: str) -> None:
    if column not in _columns(table):
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch:
            batch.drop_column(column)
    else:
        op.drop_column(table, column)


def downgrade() -> None:
    if "notifications" in _tables():
        op.drop_table("notifications")
    if "event_usages" in _tables():
        op.drop_table("event_usages")
    _drop_column("recommendation_decisions", "request_hash")
    _drop_column("event_parameters", "pii")
    _drop_column("event_parameters", "allowed_values")
