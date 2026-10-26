"""Fresh history and partially bootstrapped legacy schemas on real PostgreSQL."""

from alembic import command
from alembic.script import ScriptDirectory
import pytest
import sqlalchemy as sa

from conftest import HEAD
from app.core.database import Base
import app.models

BEFORE = "0007_estimated_prep_time"
PRODUCT = "0008_product_config"
INDEX = "ix_modifier_groups_product_id"


def product_indexes(engine):
    return [
        idx
        for idx in sa.inspect(engine).get_indexes("modifier_groups")
        if idx["column_names"] == ["product_id"]
    ]


def assert_product_schema(engine):
    indexes = product_indexes(engine)
    assert len(indexes) == 1 and not indexes[0]["unique"]
    fks = [
        fk
        for fk in sa.inspect(engine).get_foreign_keys("modifier_groups")
        if fk["constrained_columns"] == ["product_id"]
    ]
    assert len(fks) == 1
    assert fks[0]["referred_table"] == "menu_items" and fks[0]["referred_columns"] == [
        "id"
    ]


def head_constraints(engine):
    inspector = sa.inspect(engine)
    # Freezing 0001 must not omit tables/columns that the existing ORM uses.
    for table in Base.metadata.sorted_tables:
        assert inspector.has_table(table.name), table.name
        assert set(table.c.keys()) <= {
            c["name"] for c in inspector.get_columns(table.name)
        }, table.name
    assert_product_schema(engine)
    assignment = [
        fk
        for fk in inspector.get_foreign_keys("orders")
        if fk["constrained_columns"] == ["assigned_delivery_user_id"]
    ]
    assert len(assignment) == 1 and assignment[0]["referred_table"] == "admin_users"
    assert any(
        u["column_names"] == ["tenant_id", "email"]
        for u in inspector.get_unique_constraints("admin_users")
    )
    assert any(
        fk["referred_table"] == "tenants" and fk["constrained_columns"] == ["tenant_id"]
        for fk in inspector.get_foreign_keys("subscriptions")
    )
    assert any(
        u["column_names"] == ["plan_id", "feature_code"]
        for u in inspector.get_unique_constraints("plan_entitlements")
    )
    assert any(
        check["name"] == "ck_admin_audit_actor"
        for check in inspector.get_check_constraints("admin_audit_log")
    )
    with engine.connect() as conn:
        assert conn.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalars().all() == [HEAD]


def insert_preserved_group(engine):
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO modifier_groups (id, tenant_id, name, active) "
                "VALUES (1, 1, 'Synthetic preserved group', true)"
            )
        )


def preserved_group(engine):
    with engine.connect() as conn:
        assert (
            conn.execute(
                sa.text("SELECT name FROM modifier_groups WHERE id=1")
            ).scalar_one()
            == "Synthetic preserved group"
        )


def test_empty_full_history_and_downgrade_before_product_config(history_pg):
    engine, cfg = history_pg
    assert sa.inspect(engine).get_table_names() == []
    assert ScriptDirectory.from_config(cfg).get_heads() == [HEAD]
    command.upgrade(cfg, "head")
    head_constraints(engine)
    insert_preserved_group(engine)
    command.downgrade(cfg, BEFORE)
    preserved_group(engine)
    assert "product_id" not in {
        c["name"] for c in sa.inspect(engine).get_columns("modifier_groups")
    }
    command.upgrade(cfg, "head")
    head_constraints(engine)
    preserved_group(engine)


def test_frozen_baseline_preserves_existing_bootstrapped_tables(history_pg):
    engine, cfg = history_pg
    module = ScriptDirectory.from_config(cfg).get_revision("0001_create_schema").module
    frozen = module._metadata()
    assert len(frozen.tables) == 26
    assert "plans" not in frozen.tables and "customers" not in frozen.tables
    assert "product_id" not in frozen.tables["modifier_groups"].c
    frozen.create_all(engine)
    insert_preserved_group(engine)
    with engine.connect() as conn:
        oid = conn.execute(
            sa.text("SELECT 'modifier_groups'::regclass::oid")
        ).scalar_one()
    command.upgrade(cfg, "head")
    head_constraints(engine)
    preserved_group(engine)
    with engine.connect() as conn:
        assert (
            conn.execute(
                sa.text("SELECT 'modifier_groups'::regclass::oid")
            ).scalar_one()
            == oid
        )


@pytest.mark.parametrize("index_name", [INDEX, None, "legacy_modifier_product_lookup"])
def test_existing_product_column_with_present_absent_or_equivalent_index(
    history_pg, index_name
):
    engine, cfg = history_pg
    command.upgrade(cfg, BEFORE)
    with engine.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE modifier_groups ADD COLUMN product_id integer")
        )
        conn.execute(
            sa.text(
                "ALTER TABLE modifier_groups ADD CONSTRAINT legacy_product_fk "
                "FOREIGN KEY (product_id) REFERENCES menu_items(id)"
            )
        )
        if index_name:
            conn.execute(
                sa.text(f'CREATE INDEX "{index_name}" ON modifier_groups (product_id)')
            )
        original_oid = (
            conn.execute(
                sa.text(
                    "SELECT oid FROM pg_class WHERE relname=:name "
                    "AND relnamespace=current_schema()::regnamespace"
                ),
                {"name": index_name},
            ).scalar_one()
            if index_name
            else None
        )
    insert_preserved_group(engine)
    command.upgrade(cfg, "head")
    head_constraints(engine)
    preserved_group(engine)
    if index_name:
        assert product_indexes(engine)[0]["name"] == index_name
        with engine.connect() as conn:
            assert (
                conn.execute(
                    sa.text(
                        "SELECT oid FROM pg_class WHERE relname=:name "
                        "AND relnamespace=current_schema()::regnamespace"
                    ),
                    {"name": index_name},
                ).scalar_one()
                == original_oid
            )
    command.downgrade(cfg, BEFORE)
    preserved_group(engine)
    command.upgrade(cfg, "head")
    head_constraints(engine)


def test_existing_product_column_without_fk_or_index(history_pg):
    engine, cfg = history_pg
    command.upgrade(cfg, BEFORE)
    with engine.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE modifier_groups ADD COLUMN product_id integer")
        )
    command.upgrade(cfg, PRODUCT)
    assert_product_schema(engine)


def test_applied_product_revision_not_reexecuted_and_keeps_data(history_pg):
    engine, cfg = history_pg
    command.upgrade(cfg, PRODUCT)
    insert_preserved_group(engine)
    with engine.connect() as conn:
        oid = conn.execute(
            sa.text("SELECT 'ix_modifier_groups_product_id'::regclass::oid")
        ).scalar_one()
    command.upgrade(cfg, "head")
    preserved_group(engine)
    head_constraints(engine)
    with engine.connect() as conn:
        assert (
            conn.execute(
                sa.text("SELECT 'ix_modifier_groups_product_id'::regclass::oid")
            ).scalar_one()
            == oid
        )


def test_incompatible_existing_index_is_not_silently_replaced(history_pg):
    engine, cfg = history_pg
    command.upgrade(cfg, BEFORE)
    with engine.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE modifier_groups ADD COLUMN product_id integer")
        )
        conn.execute(sa.text(f"CREATE INDEX {INDEX} ON modifier_groups (tenant_id)"))
    with pytest.raises(RuntimeError, match="incompatible definition"):
        command.upgrade(cfg, PRODUCT)
    with engine.connect() as conn:
        assert (
            conn.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == BEFORE
        )
    assert next(
        i
        for i in sa.inspect(engine).get_indexes("modifier_groups")
        if i["name"] == INDEX
    )["column_names"] == ["tenant_id"]


def test_legacy_users_fk_path_roundtrip(history_pg):
    engine, cfg = history_pg
    command.upgrade(cfg, "0015_delivery_timestamps")
    assert sa.inspect(engine).has_table("users")
    command.upgrade(cfg, "0016_delivery_user_assignment")
    old = "fk_orders_assigned_delivery_user_id_users"
    assert any(
        fk["name"] == old for fk in sa.inspect(engine).get_foreign_keys("orders")
    )
    command.upgrade(cfg, "0022_delivery_fk_fix")
    assert any(
        fk["referred_table"] == "admin_users"
        and fk["constrained_columns"] == ["assigned_delivery_user_id"]
        for fk in sa.inspect(engine).get_foreign_keys("orders")
    )
    command.downgrade(cfg, "03c4fd22a767")
    assert any(
        fk["name"] == old for fk in sa.inspect(engine).get_foreign_keys("orders")
    )
    command.upgrade(cfg, "head")
    head_constraints(engine)


def test_existing_schema_without_legacy_users_keeps_valid_admin_fk(history_pg):
    engine, cfg = history_pg
    command.upgrade(cfg, "0015_delivery_timestamps")
    # Real legacy deployments were bootstrapped without importing User.
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE users"))
    command.upgrade(cfg, "0016_delivery_user_assignment")
    fks = sa.inspect(engine).get_foreign_keys("orders")
    assert any(
        fk["referred_table"] == "admin_users"
        and fk["constrained_columns"] == ["assigned_delivery_user_id"]
        for fk in fks
    )
    command.upgrade(cfg, "0022_delivery_fk_fix")
    command.downgrade(cfg, "03c4fd22a767")
    fks = sa.inspect(engine).get_foreign_keys("orders")
    assert any(
        fk["referred_table"] == "admin_users"
        and fk["constrained_columns"] == ["assigned_delivery_user_id"]
        for fk in fks
    )
    command.downgrade(cfg, "0015_delivery_timestamps")
    assert "assigned_delivery_user_id" not in {
        c["name"] for c in sa.inspect(engine).get_columns("orders")
    }


def test_existing_unnamed_or_alternative_admin_fk_is_not_duplicated(history_pg):
    engine, cfg = history_pg
    command.upgrade(cfg, "0015_delivery_timestamps")
    with engine.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE orders ADD COLUMN assigned_delivery_user_id integer")
        )
        conn.execute(
            sa.text(
                "ALTER TABLE orders ADD CONSTRAINT legacy_assigned_admin "
                "FOREIGN KEY (assigned_delivery_user_id) REFERENCES admin_users(id)"
            )
        )
    command.upgrade(cfg, "head")
    head_constraints(engine)
    command.downgrade(cfg, "03c4fd22a767")
    fks = [
        fk
        for fk in sa.inspect(engine).get_foreign_keys("orders")
        if fk["constrained_columns"] == ["assigned_delivery_user_id"]
    ]
    assert len(fks) == 1 and fks[0]["name"] == "legacy_assigned_admin"


def test_existing_customer_tags_kept_and_nonempty_downgrade_refused(history_pg):
    engine, cfg = history_pg
    command.upgrade(cfg, "0009_customers_base")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO tenants (id, business_name, slug, manual_open_status) "
                "VALUES (1, 'Synthetic', 'phase4-history', true)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO customers (id, tenant_id, name, phone) "
                "VALUES (1, 1, 'Synthetic', 'synthetic-reference')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO customer_tags (id, tenant_id, customer_id, tag) "
                "VALUES (1, 1, 1, 'synthetic-tag')"
            )
        )
        oid = conn.execute(
            sa.text("SELECT 'customer_tags'::regclass::oid")
        ).scalar_one()
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT 'customer_tags'::regclass::oid")).scalar_one()
            == oid
        )
        assert (
            conn.execute(
                sa.text("SELECT tag FROM customer_tags WHERE id=1")
            ).scalar_one()
            == "synthetic-tag"
        )
    with pytest.raises(RuntimeError, match="Archive customer_tags"):
        command.downgrade(cfg, BEFORE)
    # PostgreSQL rolls back all earlier DDL in the same failed downgrade.
    head_constraints(engine)
    with engine.connect() as conn:
        assert (
            conn.execute(
                sa.text("SELECT tag FROM customer_tags WHERE id=1")
            ).scalar_one()
            == "synthetic-tag"
        )
