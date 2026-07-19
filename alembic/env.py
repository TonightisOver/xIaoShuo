import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from src.api.models.db_models import (  # noqa: F401 - register with Base
    CareerSystem,
    Chapter,
    ChapterBlueprint,
    ChapterVersion,
    Character,
    CharacterArc,
    CharacterCareer,
    Conversation,
    KnowledgeEntity,
    KnowledgeEntityState,
    KnowledgeExtractionLog,
    KnowledgeTriple,
    LLMConfig,
    LongFormProgress,
    Message,
    Novel,
    Outline,
    OutlineSyncSuggestion,
    PowerSystem,
    ReaderSimulation,
    Scene,
    StoryBible,
    Storyline,
    StorylineCharacter,
    Task,
    Volume,
    WorldSetting,
)

# Import settings for dynamic URL
from src.core.config import get_settings

# Import your models' Base
from src.core.database import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url from settings — use the async URL directly (asyncpg driver)
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here, for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Emits SQL as a script without needing a live DBAPI connection.
    The async URL (postgresql+asyncpg) works for offline DDL generation.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure context with a live connection and run migrations."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async() -> None:
    """Run migrations in 'online' mode using an async engine (asyncpg).

    Replaces the previous sync psycopg2-based engine. Uses the project's
    async DATABASE_URL (postgresql+asyncpg) directly, eliminating the
    psycopg2-binary dependency.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Online migration entry — bridges sync Alembic CLI to async engine."""
    asyncio.run(run_migrations_online_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
