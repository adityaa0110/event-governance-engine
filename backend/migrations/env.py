from alembic import context

from database import Base, engine
import models  # noqa: F401

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    from config import database_url

    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _same_database(left: str, right: str) -> bool:
    if left == right:
        return True
    return ":memory:" in left and ":memory:" in right


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    from config import database_url

    url = database_url()
    app_url = engine.url.render_as_string(hide_password=False)
    standalone = None
    if _same_database(url, app_url):
        connection = engine.connect()
    else:
        standalone = create_engine(url)
        connection = standalone.connect()
    try:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()
        if standalone is not None:
            standalone.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
