"""Exercise Wazza confirmation through separate sessions on migrated PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from sqlalchemy import inspect

from app.core import config
from app.models.finance import CashMovement, OrderPayment
from app.models.menu_item import MenuItem
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.models.order import Order
from app.models.order_durability import OrderSubmission
from app.models.wazza_mcp import WazzaOrderDraft
from app.services.wazza_mcp_auth import authenticate_credential, issue_credential, require_scope
from app.services.wazza_mcp_confirmation import DraftConfirmArguments, order_draft_confirm
from app.services.wazza_mcp_errors import McpToolError
from app.services.wazza_mcp_identity import VerifiedCustomerIdentity
from app.services.wazza_mcp_order_drafts import (
    DraftAddItemArguments, DraftCreateArguments, DraftDeliveryArguments, DraftPaymentArguments,
    DraftRefArguments, order_draft_add_item, order_draft_create, order_draft_quote,
    order_draft_set_delivery, order_draft_set_payment,
)


def test_postgresql_confirmation_serializes_across_workers(pg, monkeypatch):
    engine, _, sessions = pg
    monkeypatch.setattr(config, "WAZZA_MCP_ORDER_CONFIRM_ENABLED", True)
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "postgres-test-only-quote-signing-secret")
    monkeypatch.delenv("CHECKOUT_POLICY_ENABLED", raising=False)
    foreign_keys = inspect(engine).get_foreign_keys("wazza_order_drafts")
    assert any(
        key["constrained_columns"] == ["confirmed_order_id", "tenant_id"]
        and key["referred_table"] == "orders"
        and key["referred_columns"] == ["id", "tenant_id"]
        for key in foreign_keys
    )

    identity = VerifiedCustomerIdentity("5511999999999", "postgres-conversation", 0, 0)
    with sessions.begin() as db:
        item = MenuItem(tenant_id=1, name="Burger", price_cents=1800, active=True)
        db.add(item)
        db.flush()
        group = ModifierGroup(tenant_id=1, product_id=item.id, name="Adicionais")
        db.add(group)
        db.flush()
        option = ModifierOption(group_id=group.id, name="Queijo", price_delta=Decimal("1.25"))
        db.add(option)
        db.flush()
        credentials = [
            issue_credential(db, tenant_id=1, name=name, scopes=("order:draft", "order:create")).token
            for name in ("PostgreSQL test connection A", "PostgreSQL test connection B")
        ]
        draft = order_draft_create(
            db, 1, DraftCreateArguments(idempotency_key="postgres-create-0001"), identity,
        )["draft"]
        ref = {"draft_id": draft["draft_id"]}
        order_draft_add_item(db, 1, DraftAddItemArguments(
            **ref, idempotency_key="postgres-add-item-01", item_id=item.id, modifier_option_ids=[option.id],
        ), identity)
        order_draft_set_delivery(db, 1, DraftDeliveryArguments(
            **ref, idempotency_key="postgres-delivery-01", fulfillment_type="pickup",
        ), identity)
        order_draft_set_payment(db, 1, DraftPaymentArguments(
            **ref, idempotency_key="postgres-payment-01", payment_method="pix",
        ), identity)
        quote = order_draft_quote(db, 1, DraftRefArguments(**ref), identity)["quote"]
    barrier = Barrier(3)

    def confirm(attempt):
        key, token = attempt
        arguments = DraftConfirmArguments(
            **ref, confirmation_token=quote["confirmation_token"], idempotency_key=key,
        )
        barrier.wait(timeout=10)
        try:
            with sessions.begin() as db:
                credential = authenticate_credential(db, token, enabled=True)
                require_scope(credential, "order:create")
                return order_draft_confirm(db, credential.tenant_id, arguments, identity)
        except McpToolError as exc:
            return exc.code

    # Two deliveries of the same attempt and a competing attempt are independent
    # transactions. Whichever attempt commits first owns the draft.
    attempts = [
        ("postgres-confirm-a", credentials[0]),
        ("postgres-confirm-a", credentials[1]),
        ("postgres-confirm-b", credentials[1]),
    ]
    with ThreadPoolExecutor(max_workers=3) as workers:
        results = list(workers.map(confirm, attempts))

    with sessions() as db:
        order = db.query(Order).filter_by(channel="wazza_mcp").one()
        draft = db.query(WazzaOrderDraft).one()
        payment = db.query(OrderPayment).one()
        assert draft.confirmed_order_id == order.id
        assert db.query(OrderSubmission).one().order_id == order.id
        assert (payment.order_id, payment.status, payment.paid_at) == (order.id, "pending", None)
        assert payment.amount_cents == 1925
        assert db.query(CashMovement).count() == 0
        expected = {**ref, "order_id": order.id}
        assert results in (
            [expected, expected, "draft_already_confirmed"],
            ["draft_already_confirmed", "draft_already_confirmed", expected],
        )
