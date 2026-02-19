from __future__ import annotations

from random import randint

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from utils.slug import normalize_slug



def slug_exists(db: Session, slug: str, tenant_id: int) -> bool:
    tenant = db.query(Tenant).filter(Tenant.slug == slug, Tenant.id != tenant_id).first()
    return tenant is not None


def ensure_unique_slug(db: Session, base_slug: str, tenant_id: int) -> str:
    if not slug_exists(db, base_slug, tenant_id):
        return base_slug

    attempts = 0
    while attempts < 1000:
        candidate = f"{base_slug}{randint(10, 99999)}"
        if not slug_exists(db, candidate[:80], tenant_id):
            return candidate[:80]
        attempts += 1

    raise RuntimeError(f"Não foi possível gerar slug único para tenant {tenant_id}")


def migrate() -> None:
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).order_by(Tenant.id.asc()).all()
        for tenant in tenants:
            base_slug = normalize_slug(tenant.business_name or "") or "loja"
            if len(base_slug) < 3:
                base_slug = f"{base_slug}loja"
            base_slug = base_slug[:70] or "loja"
            tenant.slug = ensure_unique_slug(db, base_slug, tenant.id)
            print(f"tenant_id={tenant.id} slug={tenant.slug}")

        db.commit()
        print("Migração concluída com sucesso.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
