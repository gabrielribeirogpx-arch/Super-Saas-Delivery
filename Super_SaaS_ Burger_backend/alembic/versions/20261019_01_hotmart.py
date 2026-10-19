"""Scoped Hotmart subscription bindings and durable cancellation queue."""
from alembic import op
import sqlalchemy as sa
revision = "20261019_01_hotmart"
down_revision = "20261018_01_native_payments"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("hotmart_subscriptions",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("tenant_id",sa.Integer(),sa.ForeignKey("tenants.id"),nullable=False),
        sa.Column("subscription_id",sa.Integer(),nullable=False),
        sa.Column("account_id",sa.String(255),nullable=False),
        sa.Column("environment",sa.String(20),nullable=False),
        sa.Column("subscriber_code",sa.String(255),nullable=False),
        sa.Column("product_id",sa.String(255),nullable=False),
        sa.Column("external_plan_id",sa.String(255),nullable=False),
        sa.Column("last_transaction",sa.String(255)),
        sa.Column("reconcile_at",sa.DateTime(timezone=True)),
        sa.Column("last_event_at",sa.DateTime(timezone=True)),
        sa.Column("cancel_status",sa.String(20),nullable=False,server_default="none"),
        sa.Column("cancel_requested_by",sa.Integer(),sa.ForeignKey("admin_users.id")),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint("account_id","environment","subscriber_code",name="uq_hotmart_subscriber_scope"),
        sa.UniqueConstraint("tenant_id",name="uq_hotmart_tenant"),
        sa.ForeignKeyConstraint(["subscription_id","tenant_id"],["subscriptions.id","subscriptions.tenant_id"],name="fk_hotmart_subscription_tenant"),
        sa.CheckConstraint("environment IN ('sandbox','production')",name="ck_hotmart_environment"),
        sa.CheckConstraint("cancel_status IN ('none','pending','confirmed')",name="ck_hotmart_cancel_status"))

def downgrade():
    connection=op.get_bind()
    if connection.execute(sa.text("SELECT COUNT(*) FROM hotmart_subscriptions")).scalar():
        raise RuntimeError("Archive Hotmart billing bindings before downgrade")
    op.drop_table("hotmart_subscriptions")
