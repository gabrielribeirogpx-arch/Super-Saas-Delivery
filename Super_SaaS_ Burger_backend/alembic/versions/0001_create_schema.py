from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# Frozen from all model definitions at 5eebc92 (including the legacy User
# loaded by auth/deps, not app.models.__init__). No live app imports allowed.
revision = "0001_create_schema"
down_revision = None
branch_labels = None
depends_on = None


def _metadata():
    metadata = sa.MetaData()
    sa.Table(
        "admin_audit_log",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_admin_audit_log_id",
        metadata.tables["admin_audit_log"].c["id"],
        unique=False,
    )
    sa.Index(
        "ix_admin_audit_log_tenant_id",
        metadata.tables["admin_audit_log"].c["tenant_id"],
        unique=False,
    )
    sa.Index(
        "ix_admin_audit_log_user_id",
        metadata.tables["admin_audit_log"].c["user_id"],
        unique=False,
    )
    sa.Table(
        "admin_login_attempts",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("first_failed_at", sa.DateTime(), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(), nullable=True),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "email", name="uq_admin_login_attempts_tenant_email"
        ),
    )
    sa.Index(
        "ix_admin_login_attempts_email",
        metadata.tables["admin_login_attempts"].c["email"],
        unique=False,
    )
    sa.Index(
        "ix_admin_login_attempts_id",
        metadata.tables["admin_login_attempts"].c["id"],
        unique=False,
    )
    sa.Index(
        "ix_admin_login_attempts_tenant_id",
        metadata.tables["admin_login_attempts"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "admin_users",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_admin_users_tenant_email"),
    )
    sa.Index("ix_admin_users_id", metadata.tables["admin_users"].c["id"], unique=False)
    sa.Index(
        "ix_admin_users_tenant_id",
        metadata.tables["admin_users"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "ai_configs",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_ai_configs_tenant_id",
        metadata.tables["ai_configs"].c["tenant_id"],
        unique=True,
    )
    sa.Table(
        "ai_message_logs",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("parsed_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_ai_message_logs_phone",
        metadata.tables["ai_message_logs"].c["phone"],
        unique=False,
    )
    sa.Index(
        "ix_ai_message_logs_tenant_id",
        metadata.tables["ai_message_logs"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "cash_movements",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("reference_type", sa.String(), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_cash_movements_occurred_at",
        metadata.tables["cash_movements"].c["occurred_at"],
        unique=False,
    )
    sa.Index(
        "ix_cash_movements_tenant_id",
        metadata.tables["cash_movements"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "customer_stats",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("total_orders", sa.Integer(), nullable=False),
        sa.Column("total_spent", sa.Integer(), nullable=False),
        sa.Column("last_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opt_in", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_customer_stats_phone",
        metadata.tables["customer_stats"].c["phone"],
        unique=False,
    )
    sa.Index(
        "ix_customer_stats_tenant_id",
        metadata.tables["customer_stats"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "inventory_items",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("cost_cents", sa.Integer(), nullable=False),
        sa.Column("current_stock", sa.Float(), nullable=False),
        sa.Column("min_stock_level", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_inventory_items_tenant_id",
        metadata.tables["inventory_items"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "menu_categories",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_menu_categories_tenant_id",
        metadata.tables["menu_categories"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "modifier_groups",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_modifier_groups_tenant",
        metadata.tables["modifier_groups"].c["tenant_id"],
        unique=False,
    )
    sa.Index(
        "ix_modifier_groups_tenant_id",
        metadata.tables["modifier_groups"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "orders",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("cliente_nome", sa.String(), nullable=False),
        sa.Column("cliente_telefone", sa.String(), nullable=False),
        sa.Column("itens", sa.Text(), nullable=False),
        sa.Column("endereco", sa.Text(), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=False),
        sa.Column("tipo_entrega", sa.String(), nullable=False),
        sa.Column("forma_pagamento", sa.String(), nullable=False),
        sa.Column("valor_total", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("items_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("production_ready_areas_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_orders_cliente_telefone",
        metadata.tables["orders"].c["cliente_telefone"],
        unique=False,
    )
    sa.Index(
        "ix_orders_tenant_id", metadata.tables["orders"].c["tenant_id"], unique=False
    )
    sa.Table(
        "processed_messages",
        metadata,
        sa.Column("message_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("message_id"),
    )
    sa.Table(
        "tenants",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_name", sa.String(), nullable=False),
        sa.Column("waba_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index("ix_tenants_waba_id", metadata.tables["tenants"].c["waba_id"], unique=True)
    sa.Table(
        "whatsapp_config",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("phone_number_id", sa.String(), nullable=True),
        sa.Column("waba_id", sa.String(), nullable=True),
        sa.Column("access_token", sa.String(), nullable=True),
        sa.Column("verify_token", sa.String(), nullable=True),
        sa.Column("webhook_secret", sa.String(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_whatsapp_config_tenant_id",
        metadata.tables["whatsapp_config"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "whatsapp_message_log",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("to_phone", sa.String(), nullable=True),
        sa.Column("from_phone", sa.String(), nullable=True),
        sa.Column("template_name", sa.String(), nullable=True),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_whatsapp_message_log_tenant_created",
        metadata.tables["whatsapp_message_log"].c["tenant_id"],
        metadata.tables["whatsapp_message_log"].c["created_at"],
        unique=False,
    )
    sa.Index(
        "ix_whatsapp_message_log_tenant_id",
        metadata.tables["whatsapp_message_log"].c["tenant_id"],
        unique=False,
    )
    sa.Index(
        "ix_whatsapp_message_log_to_phone",
        metadata.tables["whatsapp_message_log"].c["to_phone"],
        unique=False,
    )
    sa.Table(
        "whatsapp_outbound_log",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("template", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("variables_json", sa.Text(), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_whatsapp_outbound_log_order_id",
        metadata.tables["whatsapp_outbound_log"].c["order_id"],
        unique=False,
    )
    sa.Index(
        "ix_whatsapp_outbound_log_phone",
        metadata.tables["whatsapp_outbound_log"].c["phone"],
        unique=False,
    )
    sa.Index(
        "ix_whatsapp_outbound_log_tenant_id",
        metadata.tables["whatsapp_outbound_log"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "conversations",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("telefone", sa.String(), nullable=True),
        sa.Column("estado", sa.String(), nullable=True),
        sa.Column("dados", sa.Text(), nullable=True),
        sa.Column("last_order_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_conversations_telefone",
        metadata.tables["conversations"].c["telefone"],
        unique=False,
    )
    sa.Index(
        "ix_conversations_tenant_id",
        metadata.tables["conversations"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "inventory_movements",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_inventory_movements_inventory_item_id",
        metadata.tables["inventory_movements"].c["inventory_item_id"],
        unique=False,
    )
    sa.Index(
        "ix_inventory_movements_order_id",
        metadata.tables["inventory_movements"].c["order_id"],
        unique=False,
    )
    sa.Index(
        "ix_inventory_movements_tenant_id",
        metadata.tables["inventory_movements"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "menu_items",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("production_area", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["menu_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_menu_items_tenant_category",
        metadata.tables["menu_items"].c["tenant_id"],
        metadata.tables["menu_items"].c["category_id"],
        unique=False,
    )
    sa.Index(
        "ix_menu_items_tenant_id",
        metadata.tables["menu_items"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "modifiers",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["group_id"], ["modifier_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_modifiers_group_id",
        metadata.tables["modifiers"].c["group_id"],
        unique=False,
    )
    sa.Index(
        "ix_modifiers_tenant_id",
        metadata.tables["modifiers"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "order_items",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("modifiers_json", sa.Text(), nullable=True),
        sa.Column("production_area", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_order_items_order_id",
        metadata.tables["order_items"].c["order_id"],
        unique=False,
    )
    sa.Index(
        "ix_order_items_tenant_id",
        metadata.tables["order_items"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "order_payments",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("fee_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_order_payments_order_id",
        metadata.tables["order_payments"].c["order_id"],
        unique=False,
    )
    sa.Index(
        "ix_order_payments_tenant_id",
        metadata.tables["order_payments"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index("ix_users_email", metadata.tables["users"].c["email"], unique=True)
    sa.Index("ix_users_id", metadata.tables["users"].c["id"], unique=False)
    sa.Index(
        "ix_users_tenant_id", metadata.tables["users"].c["tenant_id"], unique=False
    )
    sa.Table(
        "menu_item_ingredients",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_menu_item_ingredients_inventory_item_id",
        metadata.tables["menu_item_ingredients"].c["inventory_item_id"],
        unique=False,
    )
    sa.Index(
        "ix_menu_item_ingredients_menu_item_id",
        metadata.tables["menu_item_ingredients"].c["menu_item_id"],
        unique=False,
    )
    sa.Index(
        "ix_menu_item_ingredients_tenant_id",
        metadata.tables["menu_item_ingredients"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "menu_item_modifier_groups",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=False),
        sa.Column("modifier_group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"]),
        sa.ForeignKeyConstraint(["modifier_group_id"], ["modifier_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_menu_item_modifier_groups_item_group",
        metadata.tables["menu_item_modifier_groups"].c["tenant_id"],
        metadata.tables["menu_item_modifier_groups"].c["menu_item_id"],
        metadata.tables["menu_item_modifier_groups"].c["modifier_group_id"],
        unique=True,
    )
    sa.Index(
        "ix_menu_item_modifier_groups_tenant_id",
        metadata.tables["menu_item_modifier_groups"].c["tenant_id"],
        unique=False,
    )
    sa.Table(
        "modifier_ingredients",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("modifier_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["modifier_id"], ["modifiers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index(
        "ix_modifier_ingredients_inventory_item_id",
        metadata.tables["modifier_ingredients"].c["inventory_item_id"],
        unique=False,
    )
    sa.Index(
        "ix_modifier_ingredients_modifier_id",
        metadata.tables["modifier_ingredients"].c["modifier_id"],
        unique=False,
    )
    sa.Index(
        "ix_modifier_ingredients_tenant_id",
        metadata.tables["modifier_ingredients"].c["tenant_id"],
        unique=False,
    )
    return metadata


def upgrade() -> None:
    _metadata().create_all(bind=op.get_bind())


def downgrade() -> None:
    _metadata().drop_all(bind=op.get_bind())
