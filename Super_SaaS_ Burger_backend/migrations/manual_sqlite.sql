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
