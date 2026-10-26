"""Full history probe in a NEW owned schema on loopback PostgreSQL only.

Never defaults to DATABASE_URL. Never repairs/stamps a failed upgrade.
"""
import json
import logging
import os
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import sqlalchemy as sa


def main():
    value = os.environ.get("FOMIZERO_PHASE4_DATABASE_URL")
    if not value or os.environ.get("FOMIZERO_PHASE4_CONFIRM_STAGING") != "yes":
        print("Isolated PostgreSQL URL and explicit confirmation required")
        return 2
    url = sa.engine.make_url(value)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        print("This probe accepts loopback PostgreSQL only; production is forbidden")
        return 2
    schema = "fomizero_phase4_history_" + uuid4().hex
    engine = sa.create_engine(url, hide_parameters=True)
    with engine.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": "-csearch_path=" + schema})
    root = Path(__file__).resolve().parents[1]
    cfg = Config()
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", scoped.render_as_string(hide_password=False).replace("%", "%%"))
    migrations = []
    class History(logging.Handler):
        def emit(self, record):
            message = record.getMessage()
            if message.startswith("Running upgrade "):
                migrations.append(message)
    handler = History()
    logger = logging.getLogger("alembic.runtime.migration")
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    result = {"head": ScriptDirectory.from_config(cfg).get_heads(), "database": "isolated_postgresql"}
    try:
        command.upgrade(cfg, "head")
        result["full_upgrade"] = "PASS"
    except Exception as error:
        result.update(full_upgrade="FAIL", error_class=type(error).__name__,
            sqlstate=getattr(getattr(error, "orig", None), "sqlstate", None),
            last_migration=migrations[-1] if migrations else None)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        with engine.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["full_upgrade"] == "PASS" else 1


if __name__ == "__main__":
    try:
        result = main()
    except Exception as error:
        # Connection/setup errors must not print a credential-bearing URL.
        print(json.dumps({"probe_setup": "FAIL", "error_class": type(error).__name__}))
        result = 2
    raise SystemExit(result)
