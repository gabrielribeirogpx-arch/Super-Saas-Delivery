from __future__ import annotations

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.config import DATABASE_URL

logger = logging.getLogger(__name__)
MIGRATIONS_PREFIX = "[MIGRATIONS]"


def validate_database_environment() -> None:
    env = os.getenv("ENVIRONMENT", os.getenv("ENV", "dev")).strip().lower()
    if env in {"prod", "production"} and DATABASE_URL.startswith("sqlite"):
        logger.critical("%s SQLite is forbidden in production", MIGRATIONS_PREFIX)
        raise RuntimeError("SQLite is forbidden in production environment")


def run_migrations_on_startup(*, alembic_config_path: Path) -> None:
    if not alembic_config_path.exists():
        logger.critical("%s alembic config not found path=%s", MIGRATIONS_PREFIX, alembic_config_path)
        raise RuntimeError("alembic config not found")

    logger.info("%s running automatic migrations", MIGRATIONS_PREFIX)
    try:
        config = Config(str(alembic_config_path))
        command.upgrade(config, "head")
    except Exception:
        logger.exception("%s automatic migration failed", MIGRATIONS_PREFIX)
        raise

    logger.info("%s automatic migrations applied", MIGRATIONS_PREFIX)


def ensure_migrations_applied(*, engine: Engine, alembic_config_path: Path) -> None:
    env = os.getenv("ENVIRONMENT", os.getenv("ENV", "dev")).strip().lower()
    if env == "test":
        logger.info("%s skipped migration check in test environment", MIGRATIONS_PREFIX)
        return

    if not alembic_config_path.exists():
        logger.critical("%s alembic config not found path=%s", MIGRATIONS_PREFIX, alembic_config_path)
        raise RuntimeError("alembic config not found")

    alembic_cfg = Config(str(alembic_config_path))
    script_directory = ScriptDirectory.from_config(alembic_cfg)
    expected_heads = set(script_directory.get_heads())

    with engine.connect() as connection:
        inspector = inspect(connection)
        if "alembic_version" not in inspector.get_table_names():
            logger.critical("%s alembic_version table missing", MIGRATIONS_PREFIX)
            raise RuntimeError("Database has no migration state")

        current_rows = connection.exec_driver_sql("SELECT version_num FROM alembic_version").fetchall()

    current_heads = {row[0] for row in current_rows if row and row[0]}
    if current_heads != expected_heads:
        logger.critical(
            "%s pending migration detected current=%s expected=%s",
            MIGRATIONS_PREFIX,
            sorted(current_heads),
            sorted(expected_heads),
        )
        raise RuntimeError("Pending migrations detected")

    logger.info("%s migration state verified", MIGRATIONS_PREFIX)
