from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from alembic import op
import sqlalchemy as sa


revision = "0018_order_public_tracking"
down_revision = "0017_delivery_logs"
branch_labels = None
depends_on = None


DEFAULT_TRACKING_TTL_DAYS = 7


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _generate_tracking_token() -> str:
    return str(uuid.uuid4())


def _default_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=DEFAULT_TRACKING_TTL_DAYS)


def upgrade() -> None:
    if not _table_exists("orders"):
        return

    columns = _column_names("orders")

    if "tracking_token" not in columns:
        op.add_column("orders", sa.Column("tracking_token", sa.String(length=36), nullable=True))
    if "tracking_expires_at" not in columns:
        op.add_column("orders", sa.Column("tracking_expires_at", sa.DateTime(timezone=True), nullable=True))
    if "tracking_revoked" not in columns:
        op.add_column("orders", sa.Column("tracking_revoked", sa.Boolean(), nullable=True))

    bind = op.get_bind()
    orders_table = sa.table(
        "orders",
        sa.column("id", sa.Integer),
        sa.column("tracking_token", sa.String),
        sa.column("tracking_expires_at", sa.DateTime(timezone=True)),
        sa.column("tracking_revoked", sa.Boolean),
    )
    existing_orders = bind.execute(sa.select(orders_table.c.id)).all()

    for row in existing_orders:
        bind.execute(
            orders_table.update()
            .where(orders_table.c.id == row.id)
            .values(
                tracking_token=_generate_tracking_token(),
                tracking_expires_at=_default_expires_at(),
                tracking_revoked=False,
            )
        )

    op.alter_column("orders", "tracking_token", nullable=False)
    op.alter_column("orders", "tracking_expires_at", nullable=False)
    op.alter_column("orders", "tracking_revoked", nullable=False, server_default=sa.false())

    indexes = _indexes_by_name("orders")
    if "ix_orders_tracking_token" not in indexes:
        op.create_index("ix_orders_tracking_token", "orders", ["tracking_token"], unique=True)


def downgrade() -> None:
    if not _table_exists("orders"):
        return

    indexes = _indexes_by_name("orders")
    if "ix_orders_tracking_token" in indexes:
        op.drop_index("ix_orders_tracking_token", table_name="orders")

    columns = _column_names("orders")
    if "tracking_revoked" in columns:
        op.drop_column("orders", "tracking_revoked")
    if "tracking_expires_at" in columns:
        op.drop_column("orders", "tracking_expires_at")
    if "tracking_token" in columns:
        op.drop_column("orders", "tracking_token")
