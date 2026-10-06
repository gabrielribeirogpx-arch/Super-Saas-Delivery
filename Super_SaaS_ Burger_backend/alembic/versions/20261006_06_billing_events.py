"""Create the durable billing inbox and concurrency idempotency barrier."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_06_billing_events"
down_revision = "20261006_05_billing_intents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "billing_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("provider_account_id", sa.String(255), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_status", sa.Enum("pending", "processing", "processed", "failed", "dead_letter", native_enum=False, create_constraint=True, name="billing_event_status"), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(255), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", name="fk_billing_event_tenant"), nullable=True),
        # Replaced with a tenant-scoped composite FK by the next migration.
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id", name="fk_billing_event_subscription"), nullable=True),
        sa.Column("checkout_intent_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["checkout_intent_id", "tenant_id"], ["billing_checkout_intents.id", "billing_checkout_intents.tenant_id"], name="fk_billing_event_intent_tenant"),
        sa.UniqueConstraint("provider", "provider_account_id", "environment", "provider_event_id", name="uq_billing_event_identity"),
        sa.CheckConstraint("environment IN ('sandbox', 'production')", name="ck_billing_event_environment"),
        sa.CheckConstraint("length(provider) > 0 AND length(provider_account_id) > 0 AND length(provider_event_id) > 0", name="ck_billing_event_identity"),
        sa.CheckConstraint("length(payload_hash) = 64", name="ck_billing_event_hash"),
        sa.CheckConstraint("attempt_count >= 0 AND schema_version >= 1", name="ck_billing_event_attempts_schema"),
        sa.CheckConstraint("(subscription_id IS NULL AND checkout_intent_id IS NULL) OR tenant_id IS NOT NULL", name="ck_billing_event_links_tenant"),
        sa.CheckConstraint("processing_status != 'processed' OR processed_at IS NOT NULL", name="ck_billing_event_processed"),
    )
    op.create_index("ix_billing_events_tenant_id", "billing_events", ["tenant_id"])
    op.create_index("ix_billing_events_processing_status", "billing_events", ["processing_status"])


def downgrade():
    op.drop_index("ix_billing_events_processing_status", table_name="billing_events")
    op.drop_index("ix_billing_events_tenant_id", table_name="billing_events")
    op.drop_table("billing_events")
