"""Create isolated load-test fixtures only in the known Railway staging backend."""
import argparse
from datetime import datetime, timedelta, timezone
import getpass
import json
import os
from pathlib import Path
import sys

BACKEND = Path('/app') if Path('/app/app').is_dir() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
STAGING_PROJECT = 'c1935217-cfa1-4b4b-b758-18074d9123bb'
STAGING_SERVICE = '0f528e50-311c-447c-b0d6-f08941784c85'
DOMAIN = 'super-saas-delivery-production.up.railway.app'
MAX_STORES = 30
SLUGS = tuple(f'carga-{i:02d}' for i in range(1, 6))

def store_slugs(count):
    if type(count) is not int or not 1 <= count <= MAX_STORES:
        raise SeedError('Informe --count entre 1 e 30.')
    return tuple(f'carga-{i:02d}' for i in range(1, count + 1))
EMAIL = 'carga@example.com'
MARKER = 'fomizero-load-stores-v1'


class SeedError(ValueError):
    pass


def validate_target(env):
    from sqlalchemy.engine import make_url
    if env.get('RAILWAY_PROJECT_ID') != STAGING_PROJECT or env.get('RAILWAY_SERVICE_ID') != STAGING_SERVICE:
        raise SeedError('Execute somente no SSH do Backend - Staging do projeto Fomizero Staging.')
    domain = env.get('RAILWAY_PUBLIC_DOMAIN')
    if domain and domain != DOMAIN:
        raise SeedError('Dominio do servico difere do staging esperado.')
    try:
        is_postgres = make_url(env.get('DATABASE_URL', '')).get_backend_name() == 'postgresql'
    except Exception:
        is_postgres = False
    if not is_postgres:
        raise SeedError('DATABASE_URL PostgreSQL obrigatoria; nenhuma alteracao realizada.')


def prepare(sessions, password, *, apply=False, count=5):
    slugs = store_slugs(count)
    import app.models  # register all metadata
    from app.models.admin_user import AdminUser
    from app.models.menu_category import MenuCategory
    from app.models.menu_item import MenuItem
    from app.models.plan import Plan
    from app.models.subscription import Subscription, SubscriptionStatus
    from app.models.tenant import Tenant
    from app.models.whatsapp_config import WhatsAppConfig
    from app.services.entitlements import EntitlementService
    from app.services.passwords import hash_password, verify_password
    from app.services.subscriptions import SubscriptionActor, SubscriptionService

    if apply and (not password or len(password) < 12 or len(password.encode('utf-8')) > 72):
        raise SeedError('Use uma senha de teste com pelo menos 12 caracteres e ate 72 bytes.')
    now = datetime.now(timezone.utc)
    result = []
    with sessions() as db, db.begin():
        # Serialize invocations without changing schema or existing catalog values.
        if db.bind.dialect.name == 'postgresql':
            from sqlalchemy import text
            db.execute(text('SELECT pg_advisory_xact_lock(841005)'))
        plan = db.query(Plan).filter_by(code='operation', active=True).one_or_none()
        if plan is None:
            raise SeedError('Plano operation ativo nao encontrado; catalogo nao foi alterado.')
        for slug in slugs:
            name = f'TESTE DE CARGA {slug} [{MARKER}]'
            external_id = f'{MARKER}:{slug}'
            tenant = db.query(Tenant).filter_by(slug=slug).one_or_none()
            created = tenant is None
            if created and not apply:
                result.append({'slug': slug, 'action': 'create', 'categories': 3, 'products': 18})
                continue
            if created:
                tenant = Tenant(slug=slug, name=name, business_name=name, is_active=True,
                                manual_open_status=True, points_enabled=False, delivery_fee=0,
                                estimated_prep_time='20 minutos')
                db.add(tenant)
                db.flush()
                db.add(AdminUser(tenant_id=tenant.id, name='Operador de carga', email=EMAIL,
                                 password_hash=hash_password(password), role='owner', active=True))
                db.add(WhatsAppConfig(tenant_id=tenant.id, provider='mock', is_enabled=False))
                for c in range(1, 4):
                    category = MenuCategory(tenant_id=tenant.id, name=f'Categoria teste {c}', sort_order=c, active=True)
                    db.add(category)
                    db.flush()
                    for p in range(1, 7):
                        db.add(MenuItem(tenant_id=tenant.id, category_id=category.id,
                            name=f'Produto teste {c}-{p}', description='Produto sintetico. Nao produzir.',
                            price_cents=1000+c*100+p*10, active=True, production_area='COZINHA'))
                # Local synthetic contract: exercise normal Hotmart quota/plan guards.
                # No HotmartSubscription binding, checkout, payment or provider call is created.
                service = SubscriptionService(db, clock=lambda: now)
                actor = SubscriptionActor('system', origin=MARKER, correlation_id=slug)
                sub = service.create_subscription(tenant.id, plan.id, actor=actor,
                    provider='hotmart', provider_subscription_id=external_id)
                service.activate_subscription(tenant.id, sub.id, actor=actor,
                    current_period_start=now, current_period_end=now+timedelta(days=7))
                db.flush()
            else:
                sub = db.query(Subscription).filter_by(tenant_id=tenant.id).one_or_none()
                users = db.query(AdminUser).filter_by(tenant_id=tenant.id).all()
                wa = db.query(WhatsAppConfig).filter_by(tenant_id=tenant.id).all()
                if (tenant.name != name or tenant.business_name != name or not tenant.is_active
                    or tenant.waba_id or tenant.custom_domain or tenant.points_enabled
                    or sub is None or sub.provider != 'hotmart' or sub.provider_subscription_id != external_id
                    or sub.plan_id != plan.id or sub.status != SubscriptionStatus.ACTIVE
                    or len(users) != 1 or users[0].email != EMAIL or users[0].role != 'owner' or not users[0].active
                    or len(wa) != 1 or wa[0].is_enabled or wa[0].provider != 'mock'
                    or any(getattr(wa[0], f) for f in ('access_token','waba_id','phone_number_id','verify_token','webhook_secret'))
                    or db.query(MenuCategory).filter_by(tenant_id=tenant.id).count() != 3
                    or db.query(MenuItem).filter_by(tenant_id=tenant.id).count() != 18):
                    raise SeedError(f'Colisao ou fixture modificada: {slug}. Nada sera sobrescrito.')
                if apply and not verify_password(password, users[0].password_hash):
                    raise SeedError('Senha diferente da criacao anterior. Credenciais nao foram alteradas.')
            entitlement = EntitlementService(db).evaluate(tenant.id, 'orders_monthly', now=now)
            if not entitlement.allowed or entitlement.limit is None or entitlement.limit - entitlement.usage < 100:
                raise SeedError(f'Loja {slug} sem acesso ou com menos de 100 pedidos disponiveis na cota.')
            result.append({'slug':slug, 'tenant_id':tenant.id, 'email':EMAIL,
                'action':'created' if created else 'unchanged', 'categories':3, 'products':18,
                'orders_remaining':entitlement.limit-entitlement.usage,
                'expires_at':sub.current_period_end.isoformat()})
        if not apply:
            db.rollback()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, choices=range(1, MAX_STORES + 1), default=5, help='Total desejado de lojas, incluindo as existentes (padrao 5).')
    parser.add_argument('--apply', action='store_true', help='Criar lojas ausentes; sem esta opcao apenas inspeciona.')
    args = parser.parse_args()
    try:
        validate_target(os.environ)
        from app.core.database import SessionLocal
        password = None
        if args.apply:
            password = getpass.getpass('Senha exclusiva dos administradores de teste (min. 12 caracteres): ')
            if password != getpass.getpass('Repita a senha: '):
                raise SeedError('As senhas nao coincidem.')
        result = prepare(SessionLocal, password, apply=args.apply, count=args.count)
        print(json.dumps({'mode':'applied' if args.apply else 'preview', 'stores':result}, indent=2))
        return 0
    except SeedError as error:
        print(str(error), file=sys.stderr)
    except Exception as error:
        # Never print SQL parameters, hashes, passwords or database connection strings.
        print(f'Preparacao interrompida ({type(error).__name__}); transacao revertida.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
