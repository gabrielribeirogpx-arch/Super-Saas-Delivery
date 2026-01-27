# Migrações manuais

## 2024-XX-XX — adicionar `active` em `modifiers`

Se o banco já existir, execute:

```sql
ALTER TABLE modifiers ADD COLUMN active BOOLEAN NOT NULL DEFAULT 1;
```

