-- Manual SQLite migration: add `active` column to modifiers.
-- Database path defaults to ./super_saas.db (see DATABASE_URL in app/core/config.py).
--
-- Usage:
-- 1) Stop the API.
-- 2) Run from the repo root:
--    sqlite3 ./super_saas.db < migrations/manual_sqlite.sql
-- 3) Restart the API.

ALTER TABLE modifiers
ADD COLUMN active BOOLEAN NOT NULL DEFAULT 1;

-- Fase 3.1 - Financeiro raiz (order_payments / cash_movements)
CREATE TABLE IF NOT EXISTS order_payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  method TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  fee_cents INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'paid',
  paid_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_order_payments_tenant_id ON order_payments (tenant_id);
CREATE INDEX IF NOT EXISTS ix_order_payments_order_id ON order_payments (order_id);

CREATE TABLE IF NOT EXISTS cash_movements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  type TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT,
  amount_cents INTEGER NOT NULL,
  reference_type TEXT,
  reference_id INTEGER,
  occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_cash_movements_tenant_id ON cash_movements (tenant_id);
CREATE INDEX IF NOT EXISTS ix_cash_movements_occurred_at ON cash_movements (occurred_at);

-- Fase 4 - Estoque
CREATE TABLE IF NOT EXISTS inventory_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  unit TEXT NOT NULL,
  cost_cents INTEGER NOT NULL DEFAULT 0,
  current_stock REAL NOT NULL DEFAULT 0,
  min_stock_level REAL NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_inventory_items_tenant_id ON inventory_items (tenant_id);

CREATE TABLE IF NOT EXISTS inventory_movements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  inventory_item_id INTEGER NOT NULL,
  type TEXT NOT NULL,
  quantity REAL NOT NULL,
  reason TEXT,
  order_id INTEGER,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_inventory_movements_tenant_id ON inventory_movements (tenant_id);
CREATE INDEX IF NOT EXISTS ix_inventory_movements_item_id ON inventory_movements (inventory_item_id);
CREATE INDEX IF NOT EXISTS ix_inventory_movements_order_id ON inventory_movements (order_id);

CREATE TABLE IF NOT EXISTS menu_item_ingredients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  menu_item_id INTEGER NOT NULL,
  inventory_item_id INTEGER NOT NULL,
  quantity REAL NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_menu_item_ingredients_tenant_id ON menu_item_ingredients (tenant_id);
CREATE INDEX IF NOT EXISTS ix_menu_item_ingredients_menu_item_id ON menu_item_ingredients (menu_item_id);

CREATE TABLE IF NOT EXISTS modifier_ingredients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  modifier_id INTEGER NOT NULL,
  inventory_item_id INTEGER NOT NULL,
  quantity REAL NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_modifier_ingredients_tenant_id ON modifier_ingredients (tenant_id);
CREATE INDEX IF NOT EXISTS ix_modifier_ingredients_modifier_id ON modifier_ingredients (modifier_id);

-- Fase 6 - Admin auth (RBAC + auditoria)
CREATE TABLE IF NOT EXISTS admin_users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  email TEXT NOT NULL,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'admin',
  active INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(tenant_id, email)
);

CREATE INDEX IF NOT EXISTS ix_admin_users_tenant_id ON admin_users (tenant_id);

CREATE TABLE IF NOT EXISTS admin_audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id INTEGER,
  meta_json TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_admin_audit_log_tenant_id ON admin_audit_log (tenant_id);
CREATE INDEX IF NOT EXISTS ix_admin_audit_log_user_id ON admin_audit_log (user_id);
CREATE INDEX IF NOT EXISTS ix_admin_audit_log_created_at ON admin_audit_log (created_at);

-- Fase 7 - Admin login attempts (rate limit)
CREATE TABLE IF NOT EXISTS admin_login_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  email TEXT NOT NULL,
  failed_count INTEGER NOT NULL DEFAULT 0,
  first_failed_at DATETIME,
  last_failed_at DATETIME,
  locked_until DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(tenant_id, email)
);

CREATE INDEX IF NOT EXISTS ix_admin_login_attempts_tenant_id ON admin_login_attempts (tenant_id);
CREATE INDEX IF NOT EXISTS ix_admin_login_attempts_email ON admin_login_attempts (email);
CREATE INDEX IF NOT EXISTS ix_admin_login_attempts_created_at ON admin_login_attempts (created_at);

-- Fase 8 - KDS (Kitchen Display System)
ALTER TABLE menu_items
ADD COLUMN production_area TEXT NOT NULL DEFAULT 'COZINHA';

ALTER TABLE order_items
ADD COLUMN production_area TEXT NOT NULL DEFAULT 'COZINHA';

ALTER TABLE orders
ADD COLUMN production_ready_areas_json TEXT NOT NULL DEFAULT '[]';

-- Fase 10 - WhatsApp Real (config + logs)
CREATE TABLE IF NOT EXISTS whatsapp_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  provider TEXT NOT NULL DEFAULT 'mock',
  phone_number_id TEXT,
  waba_id TEXT,
  access_token TEXT,
  verify_token TEXT,
  webhook_secret TEXT,
  is_enabled INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_whatsapp_config_tenant_id ON whatsapp_config (tenant_id);

CREATE TABLE IF NOT EXISTS whatsapp_message_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  direction TEXT NOT NULL,
  to_phone TEXT,
  from_phone TEXT,
  template_name TEXT,
  message_type TEXT NOT NULL,
  payload_json TEXT,
  status TEXT NOT NULL,
  error TEXT,
  provider_message_id TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_whatsapp_message_log_tenant_id ON whatsapp_message_log (tenant_id);
CREATE INDEX IF NOT EXISTS ix_whatsapp_message_log_tenant_created ON whatsapp_message_log (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_whatsapp_message_log_to_phone ON whatsapp_message_log (to_phone);

-- Fase 11 - IA (configs + logs)
CREATE TABLE IF NOT EXISTS ai_configs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  provider TEXT NOT NULL DEFAULT 'mock',
  enabled INTEGER NOT NULL DEFAULT 0,
  model TEXT,
  temperature REAL,
  system_prompt TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(tenant_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_configs_tenant_id ON ai_configs (tenant_id);

CREATE TABLE IF NOT EXISTS ai_message_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  phone TEXT,
  direction TEXT NOT NULL,
  provider TEXT NOT NULL,
  prompt TEXT,
  raw_response TEXT,
  parsed_json TEXT,
  error TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_ai_message_logs_tenant_id ON ai_message_logs (tenant_id);
CREATE INDEX IF NOT EXISTS ix_ai_message_logs_phone ON ai_message_logs (phone);
