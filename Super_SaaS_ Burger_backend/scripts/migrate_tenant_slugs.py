from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from utils.slug import build_unique_slug



def slug_exists(db: Session, slug: str, tenant_id: int) -> bool:
    tenant = db.query(Tenant).filter(Tenant.slug == slug, Tenant.id != tenant_id).first()
    return tenant is not None


def ensure_unique_slug(db: Session, base_slug: str, tenant_id: int) -> str:
    return build_unique_slug(
        base_slug,
        lambda candidate: slug_exists(db, candidate, tenant_id),
    )


def migrate() -> None:
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).order_by(Tenant.id.asc()).all()
        for tenant in tenants:
            tenant.slug = ensure_unique_slug(db, tenant.business_name or "", tenant.id)
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
