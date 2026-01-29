from __future__ import annotations

from datetime import datetime

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models.admin_user import AdminUser
from app.services.passwords import hash_password


def ensure_admin_users_table(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("admin_users"):
        raise RuntimeError(
            "Tabela admin_users não encontrada. Rode migrations/manual_sqlite.sql primeiro."
        )


def upsert_admin_user(
    db: Session,
    *,
    tenant_id: int,
    email: str,
    name: str,
    role: str,
    password: str | None,
) -> tuple[AdminUser, bool]:
    existing = (
        db.query(AdminUser)
        .filter(AdminUser.tenant_id == tenant_id, AdminUser.email == email)
        .first()
    )
    if existing:
        existing.name = name
        existing.role = role
        existing.active = True
        if password:
            existing.password_hash = hash_password(password)
        db.commit()
        db.refresh(existing)
        return existing, False

    if not password:
        raise ValueError("Senha é obrigatória para criar um novo admin.")

    admin = AdminUser(
        tenant_id=tenant_id,
        email=email,
        name=name,
        password_hash=hash_password(password),
        role=role,
        active=True,
        created_at=datetime.utcnow(),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin, True
