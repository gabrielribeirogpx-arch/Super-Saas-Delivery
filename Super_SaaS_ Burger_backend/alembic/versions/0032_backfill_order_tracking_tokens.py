from __future__ import annotations

import uuid
import sqlalchemy as sa
from alembic import op


revision = "0032_backfill_order_tracking_tokens"
down_revision = "0031_create_customer_benefits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        op.execute(
            """
            UPDATE orders
            SET tracking_token = gen_random_uuid()::text
            WHERE tracking_token IS NULL
            """
        )
    else:
        rows = bind.execute(sa.text("SELECT id FROM orders WHERE tracking_token IS NULL")).fetchall()
        for row in rows:
            bind.execute(
                sa.text("UPDATE orders SET tracking_token = :tracking_token WHERE id = :order_id"),
                {"tracking_token": str(uuid.uuid4()), "order_id": row.id},
            )


def downgrade() -> None:
    pass
