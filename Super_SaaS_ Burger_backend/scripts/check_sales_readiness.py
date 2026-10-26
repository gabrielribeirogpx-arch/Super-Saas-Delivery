"""Read-only production preflight. Never creates a checkout or charges a buyer."""
from pathlib import Path
import argparse
import logging
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from app.core.database import SessionLocal
from app.core.hotmart_config import hotmart_settings
from app.services.billing_common import BillingError
from app.services.hotmart_billing import HotmartBilling
from app.services.public_signup import public_signup_settings


def main():
    # httpx INFO request URLs can contain OAuth query credentials.
    # This standalone diagnostic intentionally prints only its own safe results.
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-auth', action='store_true', help='Also verify OAuth without creating a checkout or charge')
    args = parser.parse_args()
    checks = []
    def check(label, valid):
        checks.append(bool(valid)); print(('OK: ' if valid else 'PENDENTE: ') + label)
    signup = public_signup_settings()
    check('Aplicação configurada para produção', os.getenv('ENV', '').lower() == 'production')
    check('Cadastro público, CAPTCHA, suporte e termos configurados', signup.ready)
    check('Origem canônica de vendas autorizada', 'https://fomizero.com.br' in signup.origins)
    settings = None
    try:
        settings = hotmart_settings()
        check('Hotmart habilitada no ambiente production', settings.enabled and settings.environment == 'production')
    except BillingError:
        check('Configuração Hotmart válida', False)
    try:
        with SessionLocal() as db:
            heads = db.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
            check('Migração Hotmart aplicada', '20261023_01_admin_recovery' in heads)
            offers = HotmartBilling(db, settings).offers() if settings and settings.enabled else []
            check('Três planos e mapeamentos de produção disponíveis',
                {o['code'] for o in offers} == {'essential', 'operation', 'pro'}
                and settings is not None and len(offers) == len(settings.offers))
    except Exception:
        check('Banco e catálogo acessíveis (detalhes omitidos)', False)
    if args.verify_auth:
        if settings and settings.enabled and settings.environment == 'production':
            from app.services.hotmart_api import HotmartAPI, HotmartUnavailable
            api = HotmartAPI(settings)
            try:
                api._headers()
                check('Autenticação OAuth de produção (sem cobrança)', True)
            except HotmartUnavailable:
                check('Autenticação OAuth de produção (sem cobrança)', False)
            finally:
                api.close()
        else:
            check('Autenticação OAuth de produção (sem cobrança)', False)
    print('VERIFICAR NO PAINEL: DNS/TLS raiz e wildcard, frontend, webhook, cron a cada 5 min, Pixel/Hotmart e termos publicados.')
    print('VERIFICAR NA META: domínio verificado, mesmo conjunto de dados no site e Hotmart, eventos e ausência de duplicação.')
    print('LIMITAÇÃO: preços/recorrência no checkout e uma compra real completa não são comprovados por este diagnóstico.')
    print('Nenhum checkout ou pagamento foi criado. Não exiba variáveis ou tokens para compartilhar o resultado.')
    return 0 if all(checks) else 1

if __name__ == '__main__':
    raise SystemExit(main())
