# Migrações manuais

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
