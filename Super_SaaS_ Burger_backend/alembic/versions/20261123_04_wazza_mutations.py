"""Durable Wazza order changes and restaurant review history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261123_04_wazza_mutations"
down_revision = "20261123_03_wazza_confirmation"
branch_labels = None
depends_on = None


def upgrade():
    document = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "wazza_order_mutations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("proposal_hash", sa.String(64), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("proposal", document, nullable=False),
        sa.Column("evidence", document),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("decision_reason", sa.String(300)),
        sa.Column("resolution_reason", sa.String(300)),
        sa.Column("decided_by", sa.Integer()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.Integer()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"]),
        sa.UniqueConstraint("tenant_id", "key_hash"),
        sa.UniqueConstraint("tenant_id", "order_id", "proposal_hash"),
        sa.CheckConstraint("action IN ('edit', 'cancel')", name="ck_wazza_mutation_action"),
        sa.CheckConstraint(
            "state IN ('pending_review', 'rejected', 'manual_resolution', 'applied', 'failed')",
            name="ck_wazza_mutation_state",
        ),
    )
    op.create_index("ix_wazza_mutations_tenant_state", "wazza_order_mutations", ["tenant_id", "state", "id"])


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("Online inspection required before Wazza order mutation downgrade")
    if op.get_bind().execute(sa.text("SELECT 1 FROM wazza_order_mutations LIMIT 1")).first():
        raise RuntimeError("Preserve Wazza order mutation history before downgrade")
    op.drop_table("wazza_order_mutations")
