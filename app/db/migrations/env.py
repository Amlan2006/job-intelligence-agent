import asyncio

from alembic import context

from app.config import get_settings
from app.db.models import Base
from app.db.session import create_database


def configure(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    engine, _ = create_database(get_settings().database_url)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(configure)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=get_settings().database_url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
