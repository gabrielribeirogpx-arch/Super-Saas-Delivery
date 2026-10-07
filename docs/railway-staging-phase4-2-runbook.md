# Fase 4.2 — preparação de staging Railway

## Estado desta entrega

Modo **preparação**, sem acesso Railway. Nenhum recurso externo criado/alterado,
nenhuma credencial existente do repositório utilizada e nenhum dado de produção
acessado. Não houve deploy, push ou PR nesta fase.

Branch local: `chore/railway-staging-phase4-2`, baseada em `9248a5d` da Fase 4.1.
Esta branch precisa ser revisada/publicada antes de selecioná-la no Railway.
Não pressupor que `main` já contém os arquivos do PR #793.

**GO para criar manualmente a infraestrutura isolada. NO-GO para Fase 5:**
o deploy e a validação real abaixo ainda não aconteceram.

Todas as URLs e referências abaixo são placeholders. Criação de projeto,
serviços, banco, `DATABASE_URL`, domínios, secrets, OAuth e webhook:
**PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY**.

## Auditoria do repositório

| Item | Encontrado | Implicação |
| --- | --- | --- |
| Dockerfiles | Nenhum | Configurar o builder Railway; não reutilizar Dockerfile de produção não auditado. |
| `railway.json` / `railway.toml` / Nixpacks config | Nenhum | Root/build/start/healthcheck precisam ser definidos por serviço no painel. |
| Backend root | `Super_SaaS_ Burger_backend` | Preservar o espaço e o nome exato do diretório. |
| Backend Python | `.python-version`: 3.11 | Confirmar versão escolhida pelo builder. |
| Backend build | `requirements.txt` | `python -m pip install -r requirements.txt`. |
| Backend Procfile | `web: ./start.sh` | Não é configuração separada de staging. |
| Backend start | `start.sh` | Executa `alembic upgrade head` antes de Uvicorn, porta `PORT`, um worker. Não apontar a um banco não confirmado. |
| Backend health | `GET /health` | Retorna status healthy; o startup confere o head, mas health não testa continuamente DB/Redis. |
| Frontend root | `super_saas_frontend` | Serviço independente. |
| Frontend scripts | `npm run build`, `npm run start` | Start usa `PORT` e bind `0.0.0.0`. |
| Frontend Next | `next.config.mjs`, output standalone | Definir start explicitamente; validar JS/CSS, não só HTML/health. |
| Frontend proxy | `app/api/[...path]/route.ts` e rewrites | `STOREFRONT_BACKEND_URL` deve apontar somente para o backend de staging. |
| Frontend `.env.production` | Há defaults de API/domínios | Railway deve sobrescrever as três variáveis públicas abaixo antes do build. Valores de credenciais não foram inspecionados. |
| Backend `.env.example` | Contém `JWT_SECRET` / `JWT_EXPIRES_MIN` | O código lê **`JWT_SECRET_KEY` / `JWT_EXPIRE_MINUTES`**; não copiar cegamente o exemplo. |
| Cron existente | `scripts/run_kiwify_verification.py` | Sem agenda; com flag false imprime disabled e sai. |
| CORS original | Regex ampla Railway/subdomínios | Nesta preparação, `ENV=staging` usa somente origins explícitas e regex configurada, sem defaults amplos. Produção preservada. |

Dependências não estão integralmente travadas em lockfile no backend. Registrar
Python/Node/versões efetivas e o SHA do deploy antes de atribuir resultados ao
mesmo artefato validado na Fase 4.1.

## Arquitetura proposta e serviços

Criar projeto Railway exclusivo `fomizero-staging`, com environment chamado
`staging`. Não duplicar produção com suas variáveis, backups ou volume.

| Ordem | Serviço | Root | Build | Start | Healthcheck |
| --- | --- | --- | --- | --- | --- |
| 1 | `postgres-staging` | template oficial PostgreSQL | gerenciado | gerenciado | do template |
| 2 | `backend-staging` | `Super_SaaS_ Burger_backend` | `python -m pip install -r requirements.txt` | primeiro deploy protegido abaixo; depois `sh start.sh` | `/health` |
| 3 | `frontend-staging` | `super_saas_frontend` | `npm ci && npm run build` | `npm run start` | `/login` |
| opcional | `redis-staging` | template oficial Redis | gerenciado | gerenciado | do template |
| preparado, inativo | `billing-cron-staging` | mesmo root backend | mesmo build backend | `python scripts/run_kiwify_verification.py` | não se aplica a job |

Criar o cron como serviço vazio/inativo, sem deploy e sem schedule. Não agendar
o job nesta fase. Não confundir o job com migrations ou seed interativo.

Redis não é necessário para esta primeira validação de billing com um backend
worker. O código aceita `REDIS_URL` vazio. Se depois forem validados realtime,
rate limit distribuído ou múltiplas réplicas, criar Redis próprio e conferir os
consumidores reais; não presumir que adicionar Redis distribui todas as leases
ou rate limits. Billing usa PostgreSQL para leases/orçamento.

Frontend → proxy same-origin → backend de staging → PostgreSQL privado de
staging. Preferir backend privado; se disponibilizar URL pública de diagnóstico,
usar domínio exclusivo. Nenhum webhook real será apontado para ele.

## Variáveis reais do projeto

Os nomes abaixo foram encontrados em código/scripts existentes. Não há nova
variável de aplicação nesta fase. Segredos devem ser fornecidos no Railway e
nunca committados, exibidos em comandos, fixtures ou mensagens.

### Backend — database e processo

| Nome | Valor/configuração de staging |
| --- | --- |
| `DATABASE_URL` | Secret exclusivo do PostgreSQL criado aqui. Usar esquema `postgresql+psycopg://`; `requirements.txt` instala psycopg 3, não psycopg2. Copiar a conexão privada e ajustar apenas o prefixo no gerenciador seguro, sem imprimir a URL. |
| `ENV` | `staging` |
| `ENVIRONMENT` | `staging` |
| `PORT` | `8000` para uma porta privada estável; configurar Networking para a mesma porta. |
| `ALEMBIC_CONFIG` | Opcional; omitir para usar o `alembic.ini` do root correto. |

`DATABASE_URL`: **PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY**. Conferir a origem
da referência, host, nome do DB e serviço proprietário no projeto de staging.
Uma flag staging não prova que uma conexão pertence a staging. Nenhum script
pode descobrir essa propriedade de forma confiável só pelo nome do database.

### Backend — auth/session

| Nome | Configuração |
| --- | --- |
| `ADMIN_SESSION_SECRET` | Novo secret aleatório exclusivo, diferente de produção. |
| `JWT_SECRET_KEY` | Outro secret aleatório exclusivo de staging. |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_EXPIRE_MINUTES` | `60` |
| `ADMIN_SESSION_MAX_AGE_SECONDS` | `3600` para sessões de QA. |
| `ADMIN_SESSION_COOKIE_SECURE` | `true` |
| `ADMIN_SESSION_COOKIE_HTTPONLY` | `true` |
| `ADMIN_SESSION_COOKIE_SAMESITE` | `lax`, com proxy de mesma origem. |
| `ADMIN_SESSION_COOKIE_DOMAIN` | Vazio: host-only. |
| `COOKIE_DOMAIN` | Vazio também: é fallback, não deixar um domínio de produção. |
| `DEV_ADMIN_PASSWORD` | Ausente/vazio. O startup lê isso independentemente da flag de bootstrap. |
| `RESET_ADMIN_PASSWORD` | `false` |
| `ONBOARDING_API_TOKEN` | Ausente/vazio; nenhum onboarding público de teste necessário. |

Secrets: **PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY**. Não reutilizar senha,
hash ou sessões de admin real. A senha dos usuários sintéticos será digitada
sem eco no shell remoto, após validar o destino; não vira variável nova.

### Backend — origins, domínios e URLs

| Nome | Configuração |
| --- | --- |
| `CORS_ORIGINS` | URL HTTPS exata do frontend de staging, sem wildcard. |
| `ORIGENS_CORS` | Ausente/vazio **não é equivalente a não definida**: essa variável tem precedência. Se definida, colocar a mesma URL exata. Preferir removê-la e usar só `CORS_ORIGINS`. |
| `CORS_ALLOW_ORIGIN_REGEX` | Ausente/vazio; não é necessário regex nesta validação. |
| `PUBLIC_BASE_DOMAIN` | Base exclusiva de staging, somente hostname. |
| `PLATFORM_BASE_DOMAINS` | Somente essa base de staging. |
| `BASE_DOMAIN` | Ausente, ou igual à base de staging; nunca valor de produção. |

Não há uma variável backend `BACKEND_URL`/`PUBLIC_BACKEND_URL` a inventar:
hostname público/privado é configurado em Networking do Railway. Os nomes
`BACKEND_URL` internos do frontend são constantes derivadas de variáveis reais.

Domínios/URLs: **PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY**. Generated domains
servem ao painel de QA inicial. URLs públicas de loja por subdomínio exigem base
própria e DNS wildcard/TLS; não afirmar que funcionam automaticamente com um
único domínio gerado Railway. Billing/admin pode usar tenant_slug e paths.

### Backend — Kiwify, flags, Redis e logging

| Nome | Configuração inicial |
| --- | --- |
| `KIWIFY_UNTRUSTED_INGRESS_ENABLED` | **`false`** |
| `FEATURE_LEGACY_ADMIN` | **`false`** |
| `DEV_BOOTSTRAP_ALLOW` | **`false`** |
| `KIWIFY_ENVIRONMENT` | `sandbox`: namespace interno, não afirma existir sandbox da API Kiwify. |
| `KIWIFY_PROVIDER_ACCOUNT_ID` | Ausente/vazio; helper usa conta fictícia própria em memória. |
| `KIWIFY_API_CLIENT_ID` | Ausente/vazio. |
| `KIWIFY_API_CLIENT_SECRET` | Ausente/vazio. |
| `REDIS_URL` | Ausente/vazio inicialmente; depois somente referência a Redis de staging se necessário. |
| `LOG_LEVEL` | `INFO`; não ativar DEBUG de HTTP/SQL. |
| `META_WA_ACCESS_TOKEN`, `META_WA_PHONE_NUMBER_ID`, `META_WA_VERIFY_TOKEN` | Ausentes/vazios; não integrar WhatsApp real no teste. |

OAuth: **PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY**, apenas numa fase futura
autorizada e com conta/credentials separadas quando o provider permitir.
Webhook: **PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY**, **não configurar nesta
fase**. Não substituir a URL real Kiwify, nem fornecer Token/signature.

### Frontend

| Nome | Configuração |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | String vazia, explicitamente em build e runtime: requests same-origin. |
| `STOREFRONT_BACKEND_URL` | URL somente do backend staging, por exemplo `http://<HOST_PRIVADO_BACKEND>:8000`, sem `/api`. Definir antes do build e no runtime. |
| `NEXT_PUBLIC_PUBLIC_BASE_DOMAIN` | Base exclusiva de staging. |
| `NEXT_PUBLIC_PLATFORM_BASE_DOMAINS` | Somente a base de staging. |
| `NEXT_PUBLIC_BASE_DOMAIN` | Ausente ou mesma base de staging. |
| `PORT` | `3000`; mesma porta configurada em Networking. |
| `NODE_ENV` | `production` para executar o build Next; isso não significa usar dados de produção. |
| `NEXT_PUBLIC_STORAGE_URL`, `STOREFRONT_ASSETS_URL` | Omitir; não compartilhar storage de produção. |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Omitir: mapas não fazem parte deste teste. |

Não existe `NEXT_PUBLIC_ENVIRONMENT` no código. Não adicionar variável sem
consumidor. Ambiente é definido pelos serviços/URLs; o runtime Next usa
`NODE_ENV`. Nenhum secret deve ter prefixo `NEXT_PUBLIC_`.

## Passo a passo manual no Railway

Todos os passos externos: **PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY**.

Desabilitar Networking público do PostgreSQL e do Redis; usar apenas a rede
privada entre serviços. Essa configuração também está **PENDENTE DE
CONFIGURAÇÃO MANUAL NO RAILWAY**.

1. Criar projeto independente e environment `staging`. Desativar deploys
   automáticos por enquanto. Não clonar variáveis de produção. Registrar IDs
   de projeto/environment/serviços e os nomes de DB/host sem secrets.
2. Criar PostgreSQL exclusivo. Confirmar versão; preferir PostgreSQL 16 para
   comparabilidade com 16.15. Validar conexão privada e isolamento de backup.
3. Criar backend com o repositório `gabrielribeirogpx-arch/Super-Saas-Delivery`.
   Selecionar somente a branch preparada quando publicada. Registrar SHA.
   Definir root/build/health conforme tabela e configurar todas as variáveis
   antes de iniciar o primeiro deploy. Confirmar ausência de referências a
   recursos de produção.
4. Criar frontend sem deploy inicial. Gerar domínio HTTPS exclusivo, copiar
   sua origin exata para CORS do backend. Definir base de domínio no frontend
   e backend. Configurar proxy para host/porta do backend de staging.
5. Primeiro start backend, com os placeholders substituídos por dados **não
   secretos** previamente conferidos no painel:

   ```sh
   python scripts/prepare_railway_staging.py --confirm-staging --expected-db-host <HOST_DB_STAGING> --expected-database <DB_STAGING> --require-empty && python -m alembic upgrade head && python scripts/seed_plans.py && exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1
   ```

   Esse gate recusa flags incorretas, ambiente errado, URL divergente,
   credenciais Kiwify e database com tabelas/views fora dos schemas de sistema.
   A responsabilidade de conferir propriedade do recurso permanece no painel.
   Se o banco não estiver vazio, **parar**, inventariar o conteúdo e não apagar
   nada nem usar stamp. Remover `<...>` ao configurar o comando real.
6. Após o primeiro upgrade confirmado, trocar o start para `sh start.sh`.
   `--require-empty` é somente da primeira execução: não deixar em restarts de
   um DB agora populado. Manter uma réplica/worker inicialmente, sem deploys
   concorrentes; o start existente executa migrations a cada restart.
7. Confirmar `/health`, head e seed no shell remoto. Criar dados sintéticos
   usando o helper abaixo. Não usar `scripts/bootstrap_admin.py --force` ou
   habilitar DEV bootstrap para contornar segurança.
8. Build/deploy frontend com as variáveis **já definidas**. Conferir logs do
   build, o rewrite e a URL de upstream. Não reutilizar build antigo com
   `.env.production`. Confirmar `/login`, JS/CSS e proxy autenticado.
9. Criar cron vazio/inativo, sem schedule/deploy; criar Redis apenas se os
   testes que o exigem forem incluídos. Não habilitar a flag Kiwify.
10. Executar checklist e registrar evidências abaixo. Não fazer downgrade
    destrutivo neste DB depois de compartilhado; para rollback usar snapshot/
    restore aprovado ou um novo DB descartável.

## Migrations, seed e dados sintéticos

Comandos a executar **no shell remoto do backend correto**, usando o mecanismo
SSH disponibilizado pelo Railway. O cliente SSH não deve imprimir variáveis
ou secrets. Não executar a aplicação localmente com credenciais Railway.

```sh
python -m alembic heads
python -m alembic current
python scripts/check_alembic_single_head.py
python scripts/seed_plans.py
```

Esperado: único head/current `20261007_02_billing_review`, Essencial/Operação/Pro
e 30 entitlements. Repetir seed não duplica planos/entitlements. Não executar
os probes isolados da Fase 4.1 contra Railway: eles aceitam somente loopback e
usam DROP de schemas próprios. Não adaptar suas restrições para um DB compartilhado.

Helper sintético, após head confirmado:

```sh
python scripts/prepare_railway_staging.py --confirm-staging --expected-db-host <HOST_DB_STAGING> --expected-database <DB_STAGING> --check-only
python scripts/prepare_railway_staging.py --confirm-staging --expected-db-host <HOST_DB_STAGING> --expected-database <DB_STAGING> --batch initial
```

O primeiro comando valida configuração sem conectar e sem alegar que schema/
infra já passou. O segundo exige terminal interativo; pedir a senha de QA
sem eco, 20–72 bytes, e confirmação. Não coloca senha em argv/variáveis/logs.
Guarda somente o hash nos usuários sintéticos. Não grava secrets em fixtures.

Dados criados:

- tenants `phase4-2-a` e `phase4-2-b`, nomes `SYNTHETIC STAGING A/B`;
- A: `owner-a@example.com`, `admin-a@example.com`, `operator-a@example.com`;
  B: `owner-b@example.com`, somente contas fictícias de QA;
- planos/entitlements do catálogo existente;
- mappings com provider account `phase4-2-synthetic-only` e IDs UUID
  determinísticos, namespace interno sandbox;
- intents completados internos, sem checkout remoto;
- duas assinaturas `inactive`, sem datas de período, criadas via serviço;
- quatro eventos, dois por tenant, para approve/reject;
- respostas OAuth/vendas **simuladas** por `MockTransport` no helper, processadas
  pelo `KiwifyVerificationService` existente até `manual_review`.

Não há HTTP real à Kiwify. A configuração da aplicação permanece false; o
helper usa uma instância isolada com transporte mock injetado. A evidência
simulada não comprova pagamento real, autenticação ou vigência. A mensagem da
tela fala em venda Kiwify; todos os participantes do QA devem saber que esta
conta/tenant são sintéticos.

O helper é idempotente, recusa colisões de tenant/usuário/mapping/vínculo e
assinaturas com status/período incompatíveis. Não apaga registros nem redefine
decisões humanas. A senha é atualizada somente nas contas fictícias reconhecidas.
A aprovação exige evidência com até **5 minutos**. Reexecutar o mesmo batch
atualiza a evidência somente de reviews não decididas; usar `--batch qa02` para
novo conjunto de vendas sintéticas, sem recriar assinaturas nem apagar auditoria.

## Checklist pós-deploy

Cada item real abaixo é **PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY** até sua
execução e registro de evidência. Não importar os resultados isolados da Fase
4.1 como aprovação do staging real.

### Saúde, schema e frontend

No shell remoto, validar schema sem consultar dados de clientes:

```sh
python - <<'PY'
from sqlalchemy import inspect, text
from app.core.database import engine
from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement
from sqlalchemy.orm import Session
i = inspect(engine)
required = {'plans','plan_entitlements','subscriptions','billing_offer_mappings','billing_checkout_intents','billing_events','billing_provider_budgets','billing_manual_reviews','admin_audit_log'}
assert required <= set(i.get_table_names())
assert any(f['referred_table']=='tenants' for f in i.get_foreign_keys('subscriptions'))
with engine.connect() as c:
    assert c.execute(text('SELECT version_num FROM alembic_version')).scalars().all() == ['20261007_02_billing_review']
with Session(engine) as db:
    assert {p.code for p in db.query(Plan)} == {'essential','operation','pro'}
    assert db.query(PlanEntitlement).count() == 30
print('schema_seed_head: PASS')
PY
```

De um cliente de QA, substituir somente URLs de staging, sem credenciais:

```sh
curl --fail --silent --show-error https://<BACKEND_STAGING>/health
curl --fail --silent --show-error --output /dev/null https://<FRONTEND_STAGING>/login
curl --silent --show-error -i -X OPTIONS https://<BACKEND_STAGING>/api/admin/billing/reviews -H 'Origin: https://<FRONTEND_STAGING>' -H 'Access-Control-Request-Method: GET'
curl --silent --show-error -i -X OPTIONS https://<BACKEND_STAGING>/api/admin/billing/reviews -H 'Origin: https://forbidden.example' -H 'Access-Control-Request-Method: GET'
```

Origin exata deve ser permitida, negativa recusada e nunca retornar
`Access-Control-Allow-Origin: *`. Testar também método/header de decisão
`X-Billing-Review`; não interpretar preflight como validação de RBAC.

No serviço frontend, conferir `.next/routes-manifest.json`: destinos devem
conter somente backend staging. Conferir no DevTools requests `/api/...`
same-origin, JS/CSS 200 e ausência de URLs de API/storage produção. Navegar
login/dashboard/reviews; dashboard vazio com dados sintéticos é esperado,
erros 500 não são aceitos.

### Auth, cookies e isolamento

- Login A com tenant slug `phase4-2-a`; B com `phase4-2-b`, contas acima.
- Em HTTPS verificar cookie `admin_session`: Secure, HttpOnly, SameSite=Lax,
  sem Domain explícito. Limpar sessões antigas/service workers de QA.
- Não enviar cookie staging a endpoint de produção para testar. Conferir
  host-only/domínios distintos e geração independente dos secrets na gestão de
  configuração. Não ler/exportar secrets de produção para comparação.
- Owner/admin A vê somente reviews A. B vê somente B. Operator A não pode
  listar/decidir. Sessão ausente não acessa fila.
- Cross-tenant GET/approve/reject retorna not found, sem evidência de outro tenant.
- Cookie após logout não pode autorizar nova decisão; conferir comportamento
  existente de logout sem presumir revogação global de todas as sessões.

### Fluxo manual_review

Abrir `Assinaturas > Revisões pendentes` logo após seed/refresh. Revisar detalhe
sanitizado e confirmar tenant/plano. Aprovar o cenário approve de A; rejeitar o
outro com categoria. Não alterar Subscription.status no SQL. Nova aprovação
do mesmo evento deve ser recusada e evento rejeitado deve continuar no banco.

No shell remoto, conferir apenas dados sintéticos:

```sh
python - <<'PY'
from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.billing_event import BillingEvent
from app.models.admin_audit_log import AdminAuditLog
from app.services.entitlements import EntitlementService
with SessionLocal() as db:
    t = db.query(Tenant).filter_by(slug='phase4-2-a').one()
    s = db.query(Subscription).filter_by(tenant_id=t.id).one()
    assert s.status == SubscriptionStatus.INACTIVE
    assert s.current_period_start is None and s.current_period_end is None
    assert not EntitlementService(db).evaluate(t.id,'orders_monthly').allowed
    assert db.query(BillingEvent).filter_by(tenant_id=t.id, verification_error_code='manual_review_period_missing').count() >= 1
    for action in ('billing.manual_review_binding_approved','billing.manual_review_rejected'):
        row = db.query(AdminAuditLog).filter_by(tenant_id=t.id, action=action).first()
        assert row and row.actor_type == 'user' and row.user_id is not None
print('inactive_period_missing_human_audit: PASS')
PY
```

Os testes backend relevantes podem rodar em execução de QA com DB descartável
próprio, nunca criando/removendo schemas no banco compartilhado de staging:

```sh
python -m pytest tests/test_railway_staging_prepare.py tests/test_staging_cors.py tests/test_billing_manual_review.py tests/test_kiwify_verification.py tests/test_entitlements.py tests/test_uvicorn_access_redaction.py -q
```

Esses testes usam fixtures próprias e não certificam o deploy Railway. Se o
builder excluir pytest/testes, executar em job de QA separado, sem secrets do
DB compartilhado. Frontend: `npm test`; o smoke existente é echo, não comprova
UI. Browser real deve testar a lista, filtros, detalhe, decisões, erros, RBAC,
refresh e reconexão após restart. Não mudar DNS/cookies de produção.

OpenAPI critical contracts: executar `python scripts/check_openapi_contracts.py`
em QA separado, na configuração de referência do CI. O snapshot existente
inclui rotas legadas. Com `FEATURE_LEGACY_ADMIN=false`, o checker acusa a
ausência de `/admin/{tenant_id}/inventory/*`, `/admin/{tenant_id}/reports` e
do schema de login legado. Essa diferença foi reproduzida nesta preparação.
Não habilitar a flag no staging nem atualizar o snapshot para contornar isso.
O checker atual não certifica o contrato específico de staging; validar o
OpenAPI servido pelo deploy com a flag false e os endpoints modernos no QA
real. Uma comparação automatizada por configuração fica pendente de trabalho
separado, sem alterar funcionalidades nesta entrega.

### Logs/redaction e flags

Testar rota **desabilitada** somente com marcador público, não com secret real:

```sh
curl --silent --show-error -o /dev/null -w '%{http_code}\n' -X POST 'https://<BACKEND_STAGING>/api/webhooks/billing/kiwify?signature=phase42-public-redaction-marker' -H 'Content-Type: application/json' --data '{}'
```

Esperado 404, nenhum BillingEvent novo. Revisar app logs, Uvicorn access logs,
frontend proxy logs, exceptions e gateway logs no painel. O marcador não deve
aparecer cru; procurar sem baixar/exportar logs com dados reais. Aplicação usa
redaction já corrigida na Fase 4.1. Log de gateway não é controlado pelo formatter
Python: se persistir query bruta e Railway não fornecer supressão adequada,
manter ingress false e marcar **NO-GO para webhook**; não enviar signature real.

Verificar ausência de payloads, tokens, senha e PII. Não imprimir `env`,
DATABASE_URL, headers/cookies ou corpos de resposta autenticada nos logs do job.
Gerar somente relatório PASS/FAIL e IDs sintéticos. Verificação completa de
logs/proxy permanece **PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY**.

```sh
python - <<'PY'
import os
for k in ('KIWIFY_UNTRUSTED_INGRESS_ENABLED','FEATURE_LEGACY_ADMIN','DEV_BOOTSTRAP_ALLOW'):
    assert os.environ.get(k, '').lower() == 'false'
print('required_flags: false')
PY
python scripts/run_kiwify_verification.py
```

Job deve imprimir disabled e terminar, sem consulta externa/ativação. Não
agendar o cron mesmo que essa execução manual tenha resultado correto.

## Ações do operador, riscos e Go/No-Go

O operador deve criar os recursos, publicar/revisar a branch quando autorizado,
configurar referências privadas, gerar secrets novos, escolher domínios,
conferir o destino, executar migrations/seed/QA e registrar SHA, versão PG,
datas e resultados. Tudo isso: **PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY**.

Riscos restantes:

- Um domínio gerado Railway pode ser aceito pela política **de produção**
  ampla para `*.railway.app`. Staging agora é restrito; isso não comprova
  separação bidirecional de CORS. Preferir domínio exclusivo fora das bases
  permitidas por produção, ou tratar a revisão de produção em tarefa autorizada.
  Secrets e cookies separados continuam obrigatórios.
- Disponibilidade/build de dependências não travadas, assets standalone,
  rede privada, HTTPS/cookies e logs de gateway ainda precisam de validação real.
- Start executa migrations em restart: manter uma réplica e registrar política
  de migração serial antes de usar múltiplas réplicas.
- Evidência sintética expira em cinco minutos. Refresh não pode inventar período,
  chamar API real nem apagar decisões/auditoria.
- A assinatura é inactive: EntitlementService retorna denied, mas o sistema
  operacional continua sem enforcement comercial, conforme fases anteriores.
- Contratos oficiais de signature/vigência e credentials externas continuam
  fora desta validação. OAuth/webhook não devem ser configurados agora.

**GO para criar o ambiente manual separado. NO-GO para Fase 5** até checklist
real completo, isolamento documentado e ausência de vazamentos. Nenhum resultado
local desta entrega é apresentado como aprovação de staging real.

## Resultados locais da preparação

- Backend completo: **489 passed, 23 skipped**; os testes opt-in ignorados não
  são apresentados como validação Railway.
- Testes novos do helper/CORS: **13 passed**, incluindo idempotência, isolamento,
  ausência de HTTP real ao provider e decisão humana sem período confiável.
- Frontend: **5 arquivos de teste aprovados**.
- Build frontend: **passou**, com overrides de staging e upstream loopback
  de teste; isso não valida rede privada/HTTPS Railway.
- OpenAPI critical contracts: **passou na configuração de referência do CI**;
  diferença esperada com legacy false descrita acima.
- Alembic: head único **`20261007_02_billing_review`**. Nenhuma migration nova
  ou execução de migrations contra Railway nesta preparação.
- `git diff --check`: **passou**; arquivos novos também verificados.

Deploy, upgrade/seed no banco Railway, QA/browser HTTPS e inspeção de logs
Railway: **PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY**.
