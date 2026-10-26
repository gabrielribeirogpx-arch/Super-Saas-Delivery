"""Transactional order receipts and restart-safe operational effects."""
from alembic import op, context
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261023_02_order_durability"
down_revision = "20261023_01_admin_recovery"
branch_labels = None
depends_on = None


def upgrade():
    result_json = sa.JSON(none_as_null=True).with_variant(postgresql.JSONB(none_as_null=True), "postgresql")
    op.create_table("order_submissions",
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("order_id", sa.Integer()), sa.Column("response_json", result_json),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="CASCADE"),
        sa.CheckConstraint("length(key_hash) = 64 AND length(request_hash) = 64", name="ck_order_submission_hashes"),
        sa.CheckConstraint("(order_id IS NULL AND response_json IS NULL) OR (order_id IS NOT NULL AND response_json IS NOT NULL)", name="ck_order_submission_result"))
    op.create_index("ix_order_submissions_expiry", "order_submissions", ["expires_at"])
    op.create_table("order_outbox",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(32), nullable=False), sa.Column("effect", sa.String(40), nullable=False),
        sa.Column("stream", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(32)), sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_key", "effect", name="uq_order_outbox_event_effect"),
        sa.CheckConstraint("status IN ('pending','processing','done','review')", name="ck_order_outbox_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_order_outbox_attempts"))
    op.create_index("ix_order_outbox_due", "order_outbox", ["status", "next_attempt_at", "id"])
    op.create_index("ix_order_outbox_stream", "order_outbox", ["tenant_id", "order_id", "stream", "id"])
    op.create_index("ix_order_outbox_completed", "order_outbox", ["status", "completed_at"])
    op.create_table("order_effect_receipts",
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("order_id", sa.Integer(), primary_key=True), sa.Column("effect_key", sa.String(80), primary_key=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="CASCADE"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Online inspection required before order durability downgrade")
    for table in ("order_submissions", "order_outbox", "order_effect_receipts"):
        if op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("Archive order durability history before downgrade")
    op.drop_table("order_effect_receipts")
    op.drop_table("order_outbox")
    op.drop_table("order_submissions")
