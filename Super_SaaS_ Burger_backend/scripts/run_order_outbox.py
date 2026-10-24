"""Dedicated continuous worker; --once and --stats are useful for diagnosis."""
import argparse
import asyncio
import json
import signal
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.models
from app.core.database import SessionLocal, engine
from app.core.startup_checks import ensure_migrations_applied
from app.services.order_outbox_worker import run_cycle, run_loop, stats, retry_review


async def serve():
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await run_loop(SessionLocal, stop)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--retry", type=int, metavar="JOB_ID")
    args = parser.parse_args()
    ensure_migrations_applied(engine=engine, alembic_config_path=str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    if args.retry is not None:
        if args.retry <= 0:
            parser.error("JOB_ID must be positive")
        print(json.dumps({"requeued": retry_review(SessionLocal, args.retry)}))
    elif args.stats:
        print(json.dumps(stats(SessionLocal)))
    elif args.once:
        print(json.dumps(run_cycle(SessionLocal)))
    else:
        asyncio.run(serve())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Order outbox failed; check database, migrations and worker health")
        raise SystemExit(1)
