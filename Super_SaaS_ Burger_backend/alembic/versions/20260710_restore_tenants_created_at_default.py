from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260710_tenant_created_default"
down_revision = "20260327_driver_coords"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _columns_by_name(table_name: str) -> dict[str, dict[str, object]]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"]: column for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_table("tenants"):
        return

    columns = _columns_by_name("tenants")
    if "created_at" not in columns:
        return

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "tenants",
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            existing_nullable=False,
        )
    elif bind.dialect.name == "sqlite":
        # SQLite cannot alter a column default in place. The SQLAlchemy model already
        # supplies the default for new SQLite schemas created via metadata in tests.
        return
    else:
        op.alter_column(
            "tenants",
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            existing_nullable=False,
        )


def downgrade() -> None:
    if not _has_table("tenants"):
        return

    columns = _columns_by_name("tenants")
    if "created_at" not in columns:
        return

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return

    op.alter_column(
        "tenants",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
        nullable=False,
    )
