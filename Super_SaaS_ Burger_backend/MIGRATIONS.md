# Migrações manuais

## Como aplicar no SQLite

### Banco novo (dev)

1. Gere o banco rodando a API (tabelas via `Base.metadata.create_all`).
2. Em seguida, aplique o arquivo manual:

```bash
sqlite3 ./super_saas.db < migrations/manual_sqlite.sql
```

### Banco existente (importante)

1. Faça backup do arquivo `super_saas.db`.
2. Aplique o arquivo manual **de forma incremental**:

```bash
sqlite3 ./super_saas.db < migrations/manual_sqlite.sql
```

> Se estiver em desenvolvimento, é aceitável recriar o banco do zero.

## 2024-XX-XX — adicionar `active` em `modifiers`

Se o banco já existir, execute:

```sql
ALTER TABLE modifiers ADD COLUMN active BOOLEAN NOT NULL DEFAULT 1;
```

## 2024-XX-XX — criar `order_items`

Se o banco já existir, execute:

```sql
CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  menu_item_id INTEGER,
  name VARCHAR NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  unit_price_cents INTEGER NOT NULL DEFAULT 0,
  subtotal_cents INTEGER NOT NULL DEFAULT 0,
  modifiers_json TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_order_items_tenant_id ON order_items (tenant_id);
CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items (order_id);
```

## 2024-XX-XX — criar `order_payments` e `cash_movements`

Se o banco já existir, execute:

```sql
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
```

## 2024-XX-XX — auth admin (RBAC + auditoria)

Se o banco já existir, execute o manual:

```bash
sqlite3 ./super_saas.db < migrations/manual_sqlite.sql
```

Isso cria as tabelas `admin_users` e `admin_audit_log` e os índices.

### Observação de hash

As senhas de admin usam `passlib` com `bcrypt`. Se `bcrypt` não estiver disponível no ambiente,
o backend faz fallback para `hashlib.pbkdf2_hmac` (hash prefixado com `pbkdf2$`), e as senhas
devem ser redefinidas após instalar `bcrypt` novamente.

## 2024-XX-XX — KDS (Kitchen Display System)

Se o banco já existir, execute:

```sql
ALTER TABLE menu_items ADD COLUMN production_area TEXT NOT NULL DEFAULT 'COZINHA';
ALTER TABLE order_items ADD COLUMN production_area TEXT NOT NULL DEFAULT 'COZINHA';
ALTER TABLE orders ADD COLUMN production_ready_areas_json TEXT NOT NULL DEFAULT '[]';
```
