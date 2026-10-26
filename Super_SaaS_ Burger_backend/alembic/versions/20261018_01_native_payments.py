"""Persist isolated sandbox native-payment snapshots, attempts and events."""
from alembic import context, op
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, DateTime, ForeignKey,
    ForeignKeyConstraint, Integer, JSON, String, UniqueConstraint, func, text,
)

revision = "20261018_01_native_payments"
down_revision = "20261007_02_billing_review"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("uq_orders_id_tenant", "orders", ["id", "tenant_id"], unique=True)
    op.create_table("native_payment_intents",
        Column("id", Integer, primary_key=True),
        Column("tenant_id", Integer, ForeignKey("tenants.id"), nullable=False),
        Column("order_id", Integer, nullable=False),
        Column("public_id", String(64), nullable=False),
        Column("provider", String(40), nullable=False, server_default="internal_simulation"),
        Column("environment", String(20), nullable=False, server_default="sandbox"),
        Column("status", String(20), nullable=False, server_default="pending"),
        Column("settlement_status", String(20), nullable=False, server_default="not_settled"),
        Column("currency", String(3), nullable=False, server_default="BRL"),
        Column("total_cents", BigInteger, nullable=False),
        Column("platform_fee_cents", BigInteger, nullable=False),
        Column("merchant_before_psp_cents", BigInteger, nullable=False),
        Column("snapshot", JSON, nullable=False),
        Column("snapshot_hash", String(64), nullable=False),
        Column("paid_at", DateTime(timezone=True), nullable=True),
        Column("refunded_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
        ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], name="fk_native_intent_order_tenant"),
        UniqueConstraint("tenant_id", "order_id", name="uq_native_intent_tenant_order"),
        UniqueConstraint("id", "tenant_id", name="uq_native_intent_id_tenant"),
        UniqueConstraint("public_id", name="uq_native_intent_public"),
        CheckConstraint("environment = 'sandbox' AND provider = 'internal_simulation'", name="ck_native_intent_simulation"),
        CheckConstraint("status IN ('pending','paid','failed','canceled','refunded')", name="ck_native_intent_status"),
        CheckConstraint("settlement_status = 'not_settled'", name="ck_native_intent_not_settled"),
        CheckConstraint("currency = 'BRL' AND total_cents > 0 AND platform_fee_cents >= 0 AND merchant_before_psp_cents >= 0 AND total_cents = platform_fee_cents + merchant_before_psp_cents", name="ck_native_intent_amounts"),
        CheckConstraint("length(snapshot_hash) = 64", name="ck_native_intent_hash"),
        CheckConstraint("status NOT IN ('paid','refunded') OR paid_at IS NOT NULL", name="ck_native_intent_paid_at"),
        CheckConstraint("status != 'refunded' OR refunded_at IS NOT NULL", name="ck_native_intent_refunded_at"),
    )
    op.create_table("native_payment_attempts",
        Column("id", Integer, primary_key=True),
        Column("tenant_id", Integer, ForeignKey("tenants.id"), nullable=False),
        Column("intent_id", Integer, nullable=False),
        Column("attempt_number", Integer, nullable=False),
        Column("idempotency_key", String(120), nullable=False),
        Column("status", String(20), nullable=False, server_default="pending"),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        ForeignKeyConstraint(["intent_id", "tenant_id"], ["native_payment_intents.id", "native_payment_intents.tenant_id"], name="fk_native_attempt_intent_tenant"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_native_attempt_idempotency"),
        UniqueConstraint("intent_id", "attempt_number", name="uq_native_attempt_number"),
        CheckConstraint("attempt_number > 0 AND length(idempotency_key) > 0", name="ck_native_attempt_identity"),
        CheckConstraint("status IN ('pending','paid','failed','canceled','refunded')", name="ck_native_attempt_status"),
    )
    op.create_table("native_payment_events",
        Column("id", Integer, primary_key=True),
        Column("tenant_id", Integer, ForeignKey("tenants.id"), nullable=False),
        Column("intent_id", Integer, nullable=False),
        Column("external_event_id", String(120), nullable=False),
        Column("payload_hash", String(64), nullable=False),
        Column("target_status", String(20), nullable=False),
        Column("amount_cents", BigInteger, nullable=False),
        Column("currency", String(3), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        ForeignKeyConstraint(["intent_id", "tenant_id"], ["native_payment_intents.id", "native_payment_intents.tenant_id"], name="fk_native_event_intent_tenant"),
        UniqueConstraint("tenant_id", "external_event_id", name="uq_native_event_identity"),
        UniqueConstraint("id", "tenant_id", "intent_id", name="uq_native_event_owner"),
        CheckConstraint("length(payload_hash) = 64 AND length(external_event_id) > 0", name="ck_native_event_identity"),
        CheckConstraint("target_status IN ('paid','failed','canceled','refunded')", name="ck_native_event_status"),
        CheckConstraint("currency = 'BRL' AND amount_cents > 0", name="ck_native_event_amount"),
    )
    op.create_table("native_payment_ledger",
        Column("id", Integer, primary_key=True),
        Column("tenant_id", Integer, ForeignKey("tenants.id"), nullable=False),
        Column("intent_id", Integer, nullable=False),
        Column("event_id", Integer, nullable=False),
        Column("kind", String(20), nullable=False),
        Column("gross_delta_cents", BigInteger, nullable=False),
        Column("platform_fee_delta_cents", BigInteger, nullable=False),
        Column("merchant_delta_cents", BigInteger, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        ForeignKeyConstraint(["intent_id", "tenant_id"], ["native_payment_intents.id", "native_payment_intents.tenant_id"], name="fk_native_ledger_intent_tenant"),
        ForeignKeyConstraint(["event_id", "tenant_id", "intent_id"], ["native_payment_events.id", "native_payment_events.tenant_id", "native_payment_events.intent_id"], name="fk_native_ledger_event_owner"),
        UniqueConstraint("intent_id", "kind", name="uq_native_ledger_kind"),
        CheckConstraint("kind IN ('payment','refund')", name="ck_native_ledger_kind"),
        CheckConstraint("gross_delta_cents = platform_fee_delta_cents + merchant_delta_cents", name="ck_native_ledger_balanced"),
        CheckConstraint("(kind = 'payment' AND gross_delta_cents > 0 AND platform_fee_delta_cents >= 0 AND merchant_delta_cents >= 0) OR (kind = 'refund' AND gross_delta_cents < 0 AND platform_fee_delta_cents <= 0 AND merchant_delta_cents <= 0)", name="ck_native_ledger_sign"),
    )


def downgrade():
    if context.is_offline_mode():
        if op.get_bind().dialect.name != "postgresql":
            raise RuntimeError("Offline downgrade requires PostgreSQL")
        op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM native_payment_ledger) OR EXISTS (SELECT 1 FROM native_payment_events) OR EXISTS (SELECT 1 FROM native_payment_attempts) OR EXISTS (SELECT 1 FROM native_payment_intents) THEN RAISE EXCEPTION 'Archive native payment history before downgrade'; END IF; END $$;")
    else:
        for table in ["native_payment_ledger","native_payment_events","native_payment_attempts","native_payment_intents"]:
            if op.get_bind().execute(text(f"SELECT 1 FROM {table} LIMIT 1")).first():
                raise RuntimeError("Archive native payment history before downgrade")
    op.drop_table("native_payment_ledger")
    op.drop_table("native_payment_events")
    op.drop_table("native_payment_attempts")
    op.drop_table("native_payment_intents")
    op.drop_index("uq_orders_id_tenant", table_name="orders")
