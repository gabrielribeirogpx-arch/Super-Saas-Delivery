from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

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


def apply_migrations(*, alembic_config_path: Path) -> None:
    """Apply pending Alembic migrations in production-like runtime before startup checks."""
    env = os.getenv("ENVIRONMENT", os.getenv("ENV", "dev")).strip().lower()
    auto_apply_raw = os.getenv("AUTO_APPLY_MIGRATIONS", "").strip().lower()
    railway_runtime = os.getenv("RAILWAY_ENVIRONMENT", "").strip()

    if auto_apply_raw in {"0", "false", "no", "off"}:
        logger.info("%s auto migration disabled by AUTO_APPLY_MIGRATIONS", MIGRATIONS_PREFIX)
        return

    should_auto_apply = auto_apply_raw in {"1", "true", "yes", "on"}
    if auto_apply_raw == "":
        should_auto_apply = env in {"prod", "production"} or bool(railway_runtime)

    if not should_auto_apply:
        logger.info("%s auto migration skipped env=%s", MIGRATIONS_PREFIX, env)
        return

    if not alembic_config_path.exists():
        logger.critical("%s alembic config not found path=%s", MIGRATIONS_PREFIX, alembic_config_path)
        raise RuntimeError("alembic config not found")

    logger.info("%s applying migrations to head", MIGRATIONS_PREFIX)
    try:
        subprocess.run(
            [
                "python",
                "-m",
                "alembic",
                "-c",
                str(alembic_config_path),
                "upgrade",
                "head",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.critical(
            "%s migration apply failed returncode=%s stdout=%s stderr=%s",
            MIGRATIONS_PREFIX,
            exc.returncode,
            (exc.stdout or "").strip(),
            (exc.stderr or "").strip(),
        )
        raise RuntimeError("Automatic migration failed") from exc

    logger.info("%s migrations applied", MIGRATIONS_PREFIX)


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
