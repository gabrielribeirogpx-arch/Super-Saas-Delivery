#!/usr/bin/env python3
"""Run after alembic upgrade head: python scripts/seed_plans.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.services.plan_seed import seed_plans  # noqa: E402


def main() -> None:
    with SessionLocal.begin() as db:
        seed_plans(db)
    print("Catálogo de planos e entitlements inicializado.")


if __name__ == "__main__":
    main()
