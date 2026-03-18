from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0025_customer_account_fields"
down_revision = "0024_order_daily_number"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "customers" in inspector.get_table_names() and not _has_column(inspector, "customers", "email"):
        op.add_column("customers", sa.Column("email", sa.String(length=150), nullable=True))

    inspector = inspect(bind)
    if "customer_addresses" in inspector.get_table_names():
        if not _has_column(inspector, "customer_addresses", "cep"):
            op.add_column("customer_addresses", sa.Column("cep", sa.String(length=20), nullable=True))
        if not _has_column(inspector, "customer_addresses", "neighborhood"):
            op.add_column("customer_addresses", sa.Column("neighborhood", sa.String(length=100), nullable=True))
        if not _has_column(inspector, "customer_addresses", "state"):
            op.add_column("customer_addresses", sa.Column("state", sa.String(length=2), nullable=True))

        op.execute("UPDATE customer_addresses SET cep = COALESCE(cep, zip, '')")
        op.execute("UPDATE customer_addresses SET neighborhood = COALESCE(neighborhood, district, '')")

        if bind.dialect.name != "sqlite":
            op.alter_column("customer_addresses", "cep", existing_type=sa.String(length=20), nullable=False)
            op.alter_column("customer_addresses", "neighborhood", existing_type=sa.String(length=100), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "customer_addresses" in inspector.get_table_names():
        if _has_column(inspector, "customer_addresses", "state"):
            op.drop_column("customer_addresses", "state")
        inspector = inspect(bind)
        if _has_column(inspector, "customer_addresses", "neighborhood"):
            op.drop_column("customer_addresses", "neighborhood")
        inspector = inspect(bind)
        if _has_column(inspector, "customer_addresses", "cep"):
            op.drop_column("customer_addresses", "cep")

    inspector = inspect(bind)
    if "customers" in inspector.get_table_names() and _has_column(inspector, "customers", "email"):
        op.drop_column("customers", "email")
