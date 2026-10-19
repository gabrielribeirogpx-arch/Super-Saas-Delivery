from pathlib import Path
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import app.models
from app.core.database import Base
from app.models.tenant import Tenant
from test_billing_phase2_migrations import config,preserve_logging

def test_hotmart_migration_roundtrip_schema_parity_and_preservation(tmp_path):
    engine=sa.create_engine(f"sqlite:///{tmp_path/'hotmart-migration.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:Base.metadata.tables['hotmart_subscriptions'].drop(conn)
    with Session(engine) as db,db.begin():db.add(Tenant(id=1,slug='preserve-hotmart'))
    cfg=config(str(engine.url))
    command.stamp(cfg,'20261018_01_native_payments')
    command.upgrade(cfg,'head')
    def include(obj,name,kind,reflected,compared):
        table=obj if kind=='table' else getattr(obj,'table',None)
        return table is None or table.name=='hotmart_subscriptions'
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn,opts={'include_object':include,'compare_type':True}),Base.metadata)==[]
        assert conn.execute(sa.text('SELECT slug FROM tenants WHERE id=1')).scalar()=='preserve-hotmart'
    command.downgrade(cfg,'20261018_01_native_payments')
    assert 'hotmart_subscriptions' not in sa.inspect(engine).get_table_names()
    command.upgrade(cfg,'head')
    engine.dispose()
