from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_add_missing_admin_tables"
down_revision = "e005_create_tenant_public_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("admin_users"):
        op.create_table(
            "admin_users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=False, server_default="admin"),
            sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "email", name="uq_admin_users_tenant_email"),
        )
        op.create_index("ix_admin_users_id", "admin_users", ["id"], unique=False)
        op.create_index("ix_admin_users_tenant_id", "admin_users", ["tenant_id"], unique=False)

    if not inspector.has_table("admin_login_attempts"):
        op.create_table(
            "admin_login_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("first_failed_at", sa.DateTime(), nullable=True),
            sa.Column("last_failed_at", sa.DateTime(), nullable=True),
            sa.Column("locked_until", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "tenant_id",
                "email",
                name="uq_admin_login_attempts_tenant_email",
            ),
        )
        op.create_index("ix_admin_login_attempts_id", "admin_login_attempts", ["id"], unique=False)
        op.create_index(
            "ix_admin_login_attempts_tenant_id",
            "admin_login_attempts",
            ["tenant_id"],
            unique=False,
        )
        op.create_index(
            "ix_admin_login_attempts_email",
            "admin_login_attempts",
            ["email"],
            unique=False,
        )

    if not inspector.has_table("admin_audit_log"):
        op.create_table(
            "admin_audit_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("entity_type", sa.String(), nullable=True),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("meta_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_admin_audit_log_id", "admin_audit_log", ["id"], unique=False)
        op.create_index("ix_admin_audit_log_tenant_id", "admin_audit_log", ["tenant_id"], unique=False)
        op.create_index("ix_admin_audit_log_user_id", "admin_audit_log", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("admin_audit_log"):
        op.drop_index("ix_admin_audit_log_user_id", table_name="admin_audit_log")
        op.drop_index("ix_admin_audit_log_tenant_id", table_name="admin_audit_log")
        op.drop_index("ix_admin_audit_log_id", table_name="admin_audit_log")
        op.drop_table("admin_audit_log")

    if inspector.has_table("admin_login_attempts"):
        op.drop_index("ix_admin_login_attempts_email", table_name="admin_login_attempts")
        op.drop_index("ix_admin_login_attempts_tenant_id", table_name="admin_login_attempts")
        op.drop_index("ix_admin_login_attempts_id", table_name="admin_login_attempts")
        op.drop_table("admin_login_attempts")

    if inspector.has_table("admin_users"):
        op.drop_index("ix_admin_users_tenant_id", table_name="admin_users")
        op.drop_index("ix_admin_users_id", table_name="admin_users")
        op.drop_table("admin_users")
