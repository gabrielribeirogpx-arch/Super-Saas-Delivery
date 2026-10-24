from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker
from test_billing_phase2 import db, make_subscription, Status, NOW
from app.models.tenant import Tenant
from app.models.hotmart_subscription import HotmartSubscription
from app.services.hotmart_reconciliation import reconcile


def test_overdue_and_unreviewed_stores_cannot_be_starved_by_low_ids(db):
    for tenant_id in range(3, 63):
        db.add(Tenant(id=tenant_id, slug=f"review-{tenant_id}"))
    db.commit()
    for tenant_id in range(3, 63):
        sub = make_subscription(db, Status.ACTIVE, tenant_id=tenant_id, provider="hotmart")
        db.add(HotmartSubscription(tenant_id=tenant_id, subscription_id=sub.id, account_id="growth",
            environment="sandbox", subscriber_code=f"SUB{tenant_id}", product_id="123", external_plan_id="456"))
    db.commit()
    seen = []
    class API:
        def subscription(self, code, product):
            seen.append(code)
            return {"status": "ACTIVE", "plan": {"id": "456"}}
        def purchases(self, code):
            return []
    settings = SimpleNamespace(account_id="growth", environment="sandbox")
    sessions = sessionmaker(bind=db.bind)
    # Low IDs become due again before all 60 bindings have ever been reviewed.
    for hour in range(3):
        assert reconcile(sessions, settings, API(), NOW + timedelta(hours=hour))[1] == 0
    assert len(set(seen)) == 60
    # Third cycle starts with the last never-reviewed stores, not SUB3 again.
    assert seen[50:60] == [f"SUB{i}" for i in range(53, 63)]
