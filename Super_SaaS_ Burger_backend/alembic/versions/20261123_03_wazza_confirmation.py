"""Persist the order and replay identity of a confirmed Wazza draft."""

from alembic import op
import sqlalchemy as sa

revision = "20261123_03_wazza_confirmation"
down_revision = "20261123_02_wazza_order_drafts"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("wazza_order_drafts") as batch:
        batch.add_column(sa.Column("confirmed_order_id", sa.Integer()))
        batch.add_column(sa.Column("confirmed_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("confirmation_key_hash", sa.String(64)))
        batch.add_column(sa.Column("confirmation_request_hash", sa.String(64)))
        batch.create_foreign_key(
            "fk_wazza_draft_confirmed_order_tenant", "orders",
            ["confirmed_order_id", "tenant_id"], ["id", "tenant_id"],
        )
        batch.create_unique_constraint("uq_wazza_draft_confirmation_key", ["tenant_id", "confirmation_key_hash"])
        batch.create_unique_constraint("uq_wazza_draft_confirmed_order", ["confirmed_order_id"])
        batch.create_check_constraint(
            "ck_wazza_draft_confirmation",
            "(status = 'confirmed' AND confirmed_order_id IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmation_key_hash IS NOT NULL AND confirmation_request_hash IS NOT NULL) OR "
            "(status <> 'confirmed' AND confirmed_order_id IS NULL AND confirmed_at IS NULL "
            "AND confirmation_key_hash IS NULL AND confirmation_request_hash IS NULL)",
        )


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("Online inspection required before Wazza confirmation downgrade")
    if op.get_bind().execute(sa.text(
        "SELECT 1 FROM wazza_order_drafts WHERE confirmed_order_id IS NOT NULL LIMIT 1"
    )).first():
        raise RuntimeError("Preserve Wazza confirmation history before downgrade")
    with op.batch_alter_table("wazza_order_drafts") as batch:
        batch.drop_constraint("ck_wazza_draft_confirmation", type_="check")
        batch.drop_constraint("uq_wazza_draft_confirmed_order", type_="unique")
        batch.drop_constraint("uq_wazza_draft_confirmation_key", type_="unique")
        batch.drop_constraint("fk_wazza_draft_confirmed_order_tenant", type_="foreignkey")
        batch.drop_column("confirmation_request_hash")
        batch.drop_column("confirmation_key_hash")
        batch.drop_column("confirmed_at")
        batch.drop_column("confirmed_order_id")
