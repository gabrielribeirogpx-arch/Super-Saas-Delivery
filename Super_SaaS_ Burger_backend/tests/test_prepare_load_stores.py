import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.core.database import Base
from app.models.admin_user import AdminUser
from app.models.menu_item import MenuItem
from app.models.tenant import Tenant
from app.models.subscription import Subscription
from app.models.whatsapp_config import WhatsAppConfig
from app.services.plan_seed import seed_plans
from app.services.passwords import verify_password
from scripts.prepare_load_stores import prepare, validate_target, SeedError, SLUGS, EMAIL, STAGING_PROJECT, STAGING_SERVICE

PASSWORD = 'synthetic-load-pass-123'

@pytest.fixture
def sessions():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db, db.begin():
        seed_plans(db)
        db.add(Tenant(slug='meuburger', name='Original', business_name='Original'))
    yield factory
    engine.dispose()


def test_target_requires_exact_staging_project_and_service():
    env = {'RAILWAY_PROJECT_ID':STAGING_PROJECT, 'RAILWAY_SERVICE_ID':STAGING_SERVICE,
           'DATABASE_URL':'postgresql+psycopg://user:secret@postgres.railway.internal/railway'}
    validate_target(env)
    for changed in ({'RAILWAY_PROJECT_ID':'production'}, {'RAILWAY_SERVICE_ID':'other'},
                    {'DATABASE_URL':'sqlite://'}, {'RAILWAY_PUBLIC_DOMAIN':'api.fomizero.com.br'}):
        with pytest.raises(SeedError): validate_target({**env, **changed})


def test_preview_creation_rerun_and_password_preservation(sessions):
    preview = prepare(sessions, None)
    assert len(preview) == 5
    with sessions() as db: assert db.query(Tenant).count() == 1
    created = prepare(sessions, PASSWORD, apply=True)
    assert len(created) == 5 and all(r['action']=='created' for r in created)
    with sessions() as db:
        assert db.query(Tenant).count() == 6
        assert db.query(MenuItem).count() == 90
        assert db.query(Subscription).count() == 5
        assert all(not row.is_enabled and not row.access_token for row in db.query(WhatsAppConfig))
        hashes = {u.id:u.password_hash for u in db.query(AdminUser)}
        assert all(verify_password(PASSWORD, h) for h in hashes.values())
        expiry = {s.id:s.current_period_end for s in db.query(Subscription)}
    again = prepare(sessions, PASSWORD, apply=True)
    assert all(r['action']=='unchanged' for r in again)
    with sessions() as db:
        assert hashes == {u.id:u.password_hash for u in db.query(AdminUser)}
        assert expiry == {s.id:s.current_period_end for s in db.query(Subscription)}
        assert db.query(Tenant).filter_by(slug='meuburger').one().name == 'Original'
    with pytest.raises(SeedError, match='Senha diferente'): prepare(sessions, 'different-test-password', apply=True)


def test_collision_rolls_back_all_earlier_inserts(sessions):
    with sessions() as db, db.begin(): db.add(Tenant(slug=SLUGS[-1], name='Existing', business_name='Existing'))
    with pytest.raises(SeedError, match='Colisao'): prepare(sessions, PASSWORD, apply=True)
    with sessions() as db:
        assert db.query(Tenant).count() == 2
        assert db.query(MenuItem).count() == 0
        assert db.query(AdminUser).count() == 0
        assert db.query(Subscription).count() == 0


def test_seeded_store_accepts_real_checkout_replay_and_status_routes(sessions, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.database import get_db
    from app.middleware import tenant_context
    from app.routers.admin_auth import router as auth
    from app.routers.public_menu import router as public
    from app.routers.orders import router as orders
    from app.services import admin_auth as session_auth
    monkeypatch.setattr(session_auth, 'ADMIN_SESSION_SECRET', 'synthetic-test-session-key-only')
    prepare(sessions, PASSWORD, apply=True)
    monkeypatch.setattr(tenant_context, 'SessionLocal', sessions)
    monkeypatch.setenv('CHECKOUT_POLICY_ENABLED','false')
    app = FastAPI()
    app.add_middleware(tenant_context.TenantContextMiddleware)
    for router in (auth,public,orders): app.include_router(router)
    def get_session():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = get_session
    with TestClient(app, base_url='https://testserver') as client:
        client.headers['X-Tenant-Slug'] = SLUGS[0]
        menu = client.get('/public/menu', params={'slug':SLUGS[0]})
        assert menu.status_code == 200
        data = menu.json()
        assert len(data['categories']) == 3
        tid = data['tenant_id']
        payload = {'store_id':tid,'customer_name':'LT-test', 'order_type':'pickup',
                   'delivery_type':'retirada','payment_method':'money',
                   'items':[{'item_id':data['categories'][0]['items'][0]['id'],'quantity':1}]}
        a = client.post('/public/orders', json=payload, headers={'Idempotency-Key':'load-fixture-checkout-test-key-0001'})
        assert a.status_code == 200, a.text
        b = client.post('/public/orders', json=payload, headers={'Idempotency-Key':'load-fixture-checkout-test-key-0001'})
        assert a.json() == b.json()
        login=client.post('/api/admin/auth/login',json={'tenant_slug':SLUGS[0],'email':EMAIL,'password':PASSWORD})
        assert login.status_code == 200, login.text
        h=client.get(f'/api/orders/{tid}/search',params={'customer':'LT-test'})
        assert h.status_code == 200, h.text
        assert h.json()['total'] == 1
        oid = h.json()['items'][0]['id']
        for status in ['EM_PREPARO','PRONTO']:
            r=client.patch(f'/api/orders/{oid}/status',json={'status':status})
            assert r.status_code == 200, r.text
        other_tid = next(s['tenant_id'] for s in prepare(sessions,None) if s['slug']==SLUGS[1])
        denied=client.get(f'/api/orders/{other_tid}/search')
        assert denied.status_code == 403
