from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "0030_loyalty_reais_por_ponto"
down_revision = "0029_marketing_loyalty"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "tenants" not in inspector.get_table_names():
        return

    if not _has_column(inspector, "tenants", "reais_por_ponto"):
        op.add_column("tenants", sa.Column("reais_por_ponto", sa.Numeric(10, 4), nullable=False, server_default="1"))

    if _has_column(inspector, "tenants", "points_per_real"):
        bind.execute(
            text(
                """
                UPDATE tenants
                SET reais_por_ponto = CASE
                    WHEN points_per_real IS NULL OR points_per_real <= 0 THEN 1
                    ELSE 1 / points_per_real
                END
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "tenants" not in inspector.get_table_names():
        return

    if _has_column(inspector, "tenants", "points_per_real") and _has_column(inspector, "tenants", "reais_por_ponto"):
        bind.execute(
            text(
                """
                UPDATE tenants
                SET points_per_real = CASE
                    WHEN reais_por_ponto IS NULL OR reais_por_ponto <= 0 THEN 1
                    ELSE 1 / reais_por_ponto
                END
                """
            )
        )

    if _has_column(inspector, "tenants", "reais_por_ponto"):
        op.drop_column("tenants", "reais_por_ponto")
