import asyncio
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from test_billing_phase2 import db, make_subscription
from test_order_durability import sessions, submit
from app.models.menu_item import MenuItem
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.models.order import Order
from app.models.tenant import Tenant
from app.routers import public_menu
from app.services.product_configuration import list_modifier_groups_for_products


def test_eighteen_product_menu_uses_one_modifier_query(db):
    db.add_all([MenuItem(id=i, tenant_id=1, name=f'Item {i}', price_cents=1000) for i in range(1, 19)])
    db.commit()
    tenant = db.get(Tenant, 1)
    statements = []
    def capture(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    event.listen(db.bind, 'before_cursor_execute', capture)
    try:
        menu = public_menu._build_menu_payload(db, tenant, 'https://example.test')
    finally:
        event.remove(db.bind, 'before_cursor_execute', capture)
    assert len(menu.items_without_category) == 18
    assert all(not item.modifier_groups for item in menu.items_without_category)
    assert sum('FROM modifier_groups' in s for s in statements) == 1


def test_batched_modifiers_preserve_tenant_filter_order_and_active_options(db):
    db.add_all([MenuItem(id=1, tenant_id=1, name='A', price_cents=1000),
                MenuItem(id=2, tenant_id=2, name='B', price_cents=1000)])
    db.flush()
    db.add_all([ModifierGroup(id=1, tenant_id=1, product_id=1, name='Last', order_index=2),
                ModifierGroup(id=2, tenant_id=1, product_id=1, name='First', order_index=1, required=True, min_selection=1, max_selection=2),
                ModifierGroup(id=3, tenant_id=2, product_id=2, name='Other'),
                ModifierGroup(id=4, tenant_id=1, product_id=1, name='Inactive', active=False)])
    db.flush()
    db.add_all([ModifierOption(id=1, group_id=2, name='Last option', price_delta=Decimal('1.25'), order_index=2),
                ModifierOption(id=2, group_id=2, name='First option', order_index=1),
                ModifierOption(id=3, group_id=2, name='Inactive option', is_active=False)])
    db.commit()
    result = list_modifier_groups_for_products(db, tenant_id=1, product_ids=[1, 2], only_active_options=True)
    assert set(result) == {1}
    assert [g['id'] for g in result[1]] == [2, 1]
    group = result[1][0]
    assert group['required'] and group['min_selection'] == 1 and group['max_selection'] == 2
    assert [o['id'] for o in group['options']] == [2, 1]
    assert group['options'][1]['price_delta'] == Decimal('1.25')
    all_options = list_modifier_groups_for_products(db, tenant_id=1, product_ids=[1], only_active_options=False)
    assert len(all_options[1][0]['options']) == 3


def test_pickup_skips_preflight_but_runs_transaction_capacity_check(sessions, monkeypatch):
    from app.services import hotmart_access
    original = hotmart_access.require_hotmart_order_capacity
    calls = []
    def capacity(db, tenant_id):
        calls.append(tenant_id)
        return original(db, tenant_id)
    def unexpected(*args):
        pytest.fail('pickup without an address must not perform external preflight')
    monkeypatch.setattr(public_menu, 'require_feature', unexpected)
    monkeypatch.setattr(hotmart_access, 'require_hotmart_order_capacity', capacity)
    assert submit(sessions).tracking_token
    assert calls == [1]


def test_pickup_inactive_subscription_still_cannot_create_order(db):
    make_subscription(db, tenant_id=1, provider='hotmart')
    payload = public_menu.PublicOrderPayload(order_type='pickup', delivery_type='RETIRADA',
        items=[{'item_id': 1, 'quantity': 1}])
    with pytest.raises(HTTPException) as error:
        asyncio.run(public_menu._create_order_for_tenant(db, db.get(Tenant, 1), payload))
    assert error.value.status_code == 403
    assert db.query(Order).count() == 0


def test_pickup_exhausted_quota_still_cannot_create_order(db):
    from datetime import datetime, timedelta, timezone
    from app.models.subscription import SubscriptionStatus
    from app.models.plan_entitlement import PlanEntitlement
    sub = make_subscription(db, tenant_id=1, provider='hotmart', status=SubscriptionStatus.ACTIVE)
    sub.current_period_start = datetime.now(timezone.utc) - timedelta(days=1)
    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=1)
    entitlement = db.query(PlanEntitlement).filter_by(plan_id=sub.plan_id, feature_code='orders_monthly').one()
    entitlement.limit_value = 0
    db.commit()
    payload = public_menu.PublicOrderPayload(order_type='pickup', delivery_type='RETIRADA',
        items=[{'item_id': 1, 'quantity': 1}])
    with pytest.raises(HTTPException) as error:
        asyncio.run(public_menu._create_order_for_tenant(db, db.get(Tenant, 1), payload))
    assert error.value.status_code == 403
    assert db.query(Order).count() == 0
