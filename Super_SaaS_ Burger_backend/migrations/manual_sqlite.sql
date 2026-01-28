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
