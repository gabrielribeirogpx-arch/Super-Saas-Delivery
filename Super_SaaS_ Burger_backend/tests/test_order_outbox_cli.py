import json
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from scripts import run_order_outbox


def test_stats_cli_checks_real_migration_state_without_processing_jobs(monkeypatch, capsys):
    config_path = Path(run_order_outbox.__file__).resolve().parents[1] / "alembic.ini"
    heads = ScriptDirectory.from_config(Config(str(config_path))).get_heads()
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(64))")
        for head in heads:
            connection.exec_driver_sql("INSERT INTO alembic_version VALUES (?)", (head,))

    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setattr(run_order_outbox, "engine", engine)
    monkeypatch.setattr("sys.argv", ["run_order_outbox.py", "--stats"])
    monkeypatch.setattr(run_order_outbox, "stats", lambda sessions: {"counts": {}, "oldest_unfinished_at": None})

    def forbid_processing(*args, **kwargs):
        raise AssertionError("Read-only stats must not process jobs")

    monkeypatch.setattr(run_order_outbox, "run_cycle", forbid_processing)
    monkeypatch.setattr(run_order_outbox, "serve", forbid_processing)
    monkeypatch.setattr(run_order_outbox, "retry_review", forbid_processing)
    try:
        run_order_outbox.main()
        assert json.loads(capsys.readouterr().out) == {"counts": {}, "oldest_unfinished_at": None}
    finally:
        engine.dispose()
