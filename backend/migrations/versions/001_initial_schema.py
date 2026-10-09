"""Create the base governance tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-10-09

Databases that already applied the previous empty revision are not replayed.
New databases create the tables here; later revisions add columns idempotently.
"""

from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="1.0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("replacement", sa.String(length=128), nullable=True),
        sa.Column("platforms", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("aliases", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("owner", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("trigger", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_events_id", "events", ["id"])
    op.create_index("ix_events_event_name", "events", ["event_name"], unique=True)
    op.create_index("ix_events_status", "events", ["status"])

    op.create_table(
        "event_parameters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False, server_default="string"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_event_parameters_event_id", "event_parameters", ["event_id"])

    op.create_table(
        "event_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("snapshot_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_event_versions_event_name", "event_versions", ["event_name"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("after_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])

    op.create_table(
        "validation_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="api"),
        sa.Column("actor", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("events_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issues_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_validation_results_id", "validation_results", ["id"])


def downgrade() -> None:
    op.drop_index("ix_validation_results_id", table_name="validation_results")
    op.drop_table("validation_results")
    op.drop_index("ix_audit_logs_entity_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_event_versions_event_name", table_name="event_versions")
    op.drop_table("event_versions")
    op.drop_index("ix_event_parameters_event_id", table_name="event_parameters")
    op.drop_table("event_parameters")
    op.drop_index("ix_events_status", table_name="events")
    op.drop_index("ix_events_event_name", table_name="events")
    op.drop_index("ix_events_id", table_name="events")
    op.drop_table("events")
