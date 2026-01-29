#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.core.config import DEV_BOOTSTRAP_ALLOW, IS_DEV  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.services.admin_bootstrap import (  # noqa: E402
    ensure_admin_users_table,
    upsert_admin_user,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap de admin para DEV.")
    parser.add_argument("--tenant", type=int, required=True, help="Tenant ID")
    parser.add_argument("--email", required=True, help="Email do admin")
    parser.add_argument("--password", help="Senha do admin")
    parser.add_argument("--name", required=True, help="Nome do admin")
    parser.add_argument("--role", default="admin", help="Role do admin (ex: OWNER)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Permite executar sem DEV_BOOTSTRAP_ALLOW=1",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not DEV_BOOTSTRAP_ALLOW and not args.force:
        print(
            "Bootstrap DEV desabilitado. "
            "Defina DEV_BOOTSTRAP_ALLOW=1 ou use --force."
        )
        return 1

    try:
        ensure_admin_users_table(engine)
    except RuntimeError as exc:
        print(str(exc))
        return 1

    db = SessionLocal()
    try:
        admin, created = upsert_admin_user(
            db,
            tenant_id=args.tenant,
            email=args.email,
            name=args.name,
            role=args.role,
            password=args.password,
        )
    except ValueError as exc:
        print(str(exc))
        return 1
    finally:
        db.close()

    action = "created" if created else "updated"
    print(f"Admin {action}: tenant={admin.tenant_id} email={admin.email}")
    if IS_DEV:
        password_info = args.password if args.password else "<mantida>"
        print(f"Resumo DEV -> Tenant: {admin.tenant_id} | Email: {admin.email} | Senha: {password_info}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
