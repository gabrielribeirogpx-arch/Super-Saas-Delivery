from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "0009_customers_base"
down_revision = "0008_product_config"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "customers" not in inspector.get_table_names():
        op.create_table(
            "customers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("phone", sa.String(length=30), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_customers_phone", "customers", ["phone"], unique=False)
        op.create_index("ix_customers_tenant_id", "customers", ["tenant_id"], unique=False)
        op.create_index("ix_customers_tenant_phone", "customers", ["tenant_id", "phone"], unique=False)

    inspector = inspect(bind)
    if "customer_addresses" not in inspector.get_table_names():
        op.create_table(
            "customer_addresses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
            sa.Column("street", sa.String(length=150), nullable=False),
            sa.Column("number", sa.String(length=20), nullable=False),
            sa.Column("district", sa.String(length=100), nullable=False),
            sa.Column("city", sa.String(length=100), nullable=False),
            sa.Column("zip", sa.String(length=20), nullable=False),
            sa.Column("complement", sa.String(length=150), nullable=True),
        )
        op.create_index("ix_customer_addresses_customer_id", "customer_addresses", ["customer_id"], unique=False)

    inspector = inspect(bind)
    if "orders" in inspector.get_table_names():
        jsonb_type = postgresql.JSONB(astext_type=sa.Text())
        if bind.dialect.name == "sqlite":
            jsonb_type = sa.JSON()

        columns_to_add = [
            ("customer_id", sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True)),
            ("customer_name", sa.Column("customer_name", sa.String(length=120), nullable=True)),
            ("customer_phone", sa.Column("customer_phone", sa.String(length=30), nullable=True)),
            ("delivery_address_json", sa.Column("delivery_address_json", jsonb_type, nullable=True)),
            ("payment_method", sa.Column("payment_method", sa.String(length=30), nullable=True)),
            ("payment_change_for", sa.Column("payment_change_for", sa.Numeric(10, 2), nullable=True)),
            ("order_note", sa.Column("order_note", sa.Text(), nullable=True)),
        ]

        for column_name, column in columns_to_add:
            if not _has_column(inspector, "orders", column_name):
                op.add_column("orders", column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "orders" in inspector.get_table_names():
        for column_name in [
            "order_note",
            "payment_change_for",
            "payment_method",
            "delivery_address_json",
            "customer_phone",
            "customer_name",
            "customer_id",
        ]:
            if _has_column(inspector, "orders", column_name):
                op.drop_column("orders", column_name)

    inspector = inspect(bind)
    if "customer_addresses" in inspector.get_table_names():
        if _has_index(inspector, "customer_addresses", "ix_customer_addresses_customer_id"):
            op.drop_index("ix_customer_addresses_customer_id", table_name="customer_addresses")
        op.drop_table("customer_addresses")

    inspector = inspect(bind)
    if "customers" in inspector.get_table_names():
        for index_name in ["ix_customers_tenant_phone", "ix_customers_tenant_id", "ix_customers_phone"]:
            if _has_index(inspector, "customers", index_name):
                op.drop_index(index_name, table_name="customers")
        op.drop_table("customers")
