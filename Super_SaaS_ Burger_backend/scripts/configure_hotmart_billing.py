"""Explicit catalog mapping and sanitized readiness check. Never charges anyone."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.core.hotmart_config import hotmart_settings
from app.models.plan import Plan
from app.services.billing_catalog import BillingCatalogService
from app.models.billing_offer_mapping import BillingOfferMapping

def main():
    settings=hotmart_settings()
    if not settings.enabled:
        print("Hotmart disabled; no catalog changes")
        return 1
    with SessionLocal() as db,db.begin():
        for offer in settings.offers:
            plan=db.query(Plan).filter_by(code=offer.plan_code,active=True).one_or_none()
            if plan is None:
                raise RuntimeError("Configured internal plan is unavailable; seed/review catalog first")
            key=dict(provider="hotmart",environment=settings.environment,provider_account_id=settings.account_id,
                external_product_id=offer.product_id,external_offer_id=offer.plan_id)
            mapping=db.query(BillingOfferMapping).filter_by(**key).one_or_none()
            if mapping is None:
                BillingCatalogService(db).create_mapping(**key,plan_id=plan.id)
            elif mapping.plan_id!=plan.id or not mapping.active:
                raise RuntimeError("Existing mapping requires explicit review")
    print("Hotmart offer mappings ready. Provider credentials, checkout prices and recurring product approval require staging validation.")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
