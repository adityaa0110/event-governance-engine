"""Schema changes belong to Alembic revisions under backend/migrations.

Startup applies `alembic upgrade head`. This module no longer creates tables.
"""


def upgrade_schema() -> None:
    raise RuntimeError("Schema changes run through Alembic, not upgrade_schema()")
