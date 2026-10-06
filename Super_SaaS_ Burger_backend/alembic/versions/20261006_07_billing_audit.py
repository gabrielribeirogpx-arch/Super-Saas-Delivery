"""Version subscriptions and support truthful automatic audit actors."""
from alembic import context, op
import sqlalchemy as sa

revision = "20261006_07_billing_audit"
down_revision = "20261006_06_billing_events"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("subscriptions") as batch:
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_unique_constraint("uq_subscriptions_id_tenant", ["id", "tenant_id"])
    with op.batch_alter_table("billing_events") as batch:
        batch.drop_constraint("fk_billing_event_subscription", type_="foreignkey")
        batch.create_foreign_key("fk_billing_event_subscription_tenant", "subscriptions", ["subscription_id", "tenant_id"], ["id", "tenant_id"])
    with op.batch_alter_table("admin_audit_log") as batch:
        batch.add_column(sa.Column("actor_type", sa.String(20), nullable=False, server_default="user"))
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
        batch.create_check_constraint("ck_admin_audit_actor", "(actor_type = 'user' AND user_id IS NOT NULL) OR (actor_type IN ('system', 'provider') AND user_id IS NULL)")


def downgrade():
    # Restoring NOT NULL must never delete history or invent a human actor.
    if context.is_offline_mode():
        if op.get_bind().dialect.name != "postgresql":
            raise RuntimeError("Offline downgrade requires PostgreSQL or an online audit preflight")
        op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM admin_audit_log WHERE user_id IS NULL) THEN RAISE EXCEPTION 'Archive automatic audit records before downgrade'; END IF; END $$;")
    elif op.get_bind().execute(sa.text("SELECT COUNT(*) FROM admin_audit_log WHERE user_id IS NULL")).scalar_one():
        raise RuntimeError("Archive automatic audit records before downgrade; no history will be deleted or assigned to a human")
    with op.batch_alter_table("admin_audit_log") as batch:
        batch.drop_constraint("ck_admin_audit_actor", type_="check")
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("actor_type")
    with op.batch_alter_table("billing_events") as batch:
        batch.drop_constraint("fk_billing_event_subscription_tenant", type_="foreignkey")
        batch.create_foreign_key("fk_billing_event_subscription", "subscriptions", ["subscription_id"], ["id"])
    with op.batch_alter_table("subscriptions") as batch:
        batch.drop_constraint("uq_subscriptions_id_tenant", type_="unique")
        batch.drop_column("version")
