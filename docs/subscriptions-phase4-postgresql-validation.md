# Fase 4: validação isolada em PostgreSQL real

## Resultado e limites

Validação realizada sobre a main com os PRs #791 e #792 mergeados, commit
`07f7703`, na branch `test/subscriptions-postgres-staging`. Não existe staging
Railway dedicado. Nenhum banco, tenant, URL, secret ou webhook de produção foi
utilizado ou alterado. Não houve deploy nem criação de PR.

**GO técnico para preparar staging Railway isolado:** o bloqueio de migrations
foi corrigido e o upgrade do histórico completo passou em um banco PostgreSQL
16.15 realmente vazio, sem stamp ou metadata operacional pré-criado. Também
passaram downgrade até antes de `0008`, re-upgrade, downgrade até `base` e novo
upgrade ao head. **PENDENTE DE STAGING RAILWAY:** validação da infraestrutura
gerenciada; esses resultados não autorizam deploy ou automação comercial em
produção.

## PostgreSQL e migrations

PostgreSQL 16.15, imagem `postgres:16-bookworm`, container temporário exclusivo,
porta publicada apenas em loopback. Credenciais aleatórias em arquivos locais
privados; schemas exclusivos com nomes aleatórios, removidos ao final de cada
teste. Não há fallback dos validadores para `DATABASE_URL`.

Ao encerrar, foram confirmados zero schemas de teste remanescentes. O container,
seu volume temporário e os arquivos privados de credenciais foram removidos;
os processos HTTP criados pela validação também foram encerrados.

Head único confirmado: `20261007_02_billing_review`.

Migrations de billing exercitadas:

- `20261006_01_plans`;
- `20261006_02_plan_entitlements`;
- `20261006_03_subscriptions`;
- `20261006_04_billing_offers`;
- `20261006_05_billing_intents`;
- `20261006_06_billing_events`;
- `20261006_07_billing_audit`;
- `20261007_01_billing_verification`;
- `20261007_02_billing_review`.

Upgrade/downgrade/re-upgrade dessas migrations passou. Os testes inspecionam
colunas, tipos, nulabilidade, FKs, índices e constraints e exercitam violações
reais de unicidade/FKs. O seed é idempotente. Downgrades com dados de revisão,
verificação ou auditoria automática são recusados conforme os guardrails
existentes; a transação PostgreSQL preserva também DDL executado antes da recusa.
Não foram apagadas evidências para contornar esses guardrails.

A fixture de billing cria somente as tabelas operacionais sintéticas e a forma histórica
do audit log, marca explicitamente a baseline `20260716_customer_phone_otp` e
aplica as migrations de billing reais. Ela não cria as tabelas de billing via
`Base.metadata.create_all`.

### Causa raiz do bloqueio e correção

Na validação inicial, o probe `scripts/validate_billing_pg_history.py` retornou
FAIL em um schema vazio. Após a correção, o histórico completo passou também
pela CLI real do Alembic em um database novo exclusivo, posteriormente removido.

Antes da correção, `0001_create_schema` importava o metadata atual e criava estruturas
que outras revisions esperam criar. Em `0008_product_config`, a criação de
`ix_modifier_groups_product_id` encontra um índice já existente. A exception é
capturada, mas a transação PostgreSQL permanece abortada; a atualização da
versão Alembic termina em `InFailedSqlTransaction`, SQLSTATE `25P02`.

O índice nasce de `ModifierGroup.product_id = Column(..., index=True)` em
`app/models/modifier_group.py`, quando o `Base.metadata.create_all` antigo de
`0001` executa. Não nasce de `create_table(... Index(...))`, de reaproveitamento
do nome em outra tabela ou de outra chamada histórica explícita. `0008` é a
segunda criação explícita por `op.create_index`.

Estratégia escolhida: reparar as revisions históricas que impedem a execução,
sem criar nova revision/head. Uma migration corretiva depois do head não pode
consertar uma transação que já falha em `0008`, nem impedir que o metadata atual
antecipe tabelas de billing e colunas de revisions posteriores.

- `0001_create_schema`: metadata **estático**, reconstruído das 26 definições
  de models no commit `5eebc92`, que introduziu a revision. Inclui o `User`
  legado, carregado por auth/deps e não pelo `app.models.__init__`, eliminando
  dependência da ordem de imports. Mantém `create_all`/`drop_all` com checkfirst,
  mas sobre esse snapshot congelado, sem importar models da aplicação.
- `0008_product_config`: inspeciona definição e equivalência de índice antes
  de executar DDL. Mantém índices compatíveis, inclusive com outro nome;
  rejeita definição incompatível em vez de substituí-la silenciosamente.
  Inspeciona FKs de `product_id`, mantém a válida ou cria a ausente. O downgrade
  também inspeciona os objetos antes de removê-los. Não há `except: pass` em
  torno dessas operações.
- `0009_customers_base`: torna explícita a criação de `customer_tags`, que
  anteriormente dependia apenas do metadata dinâmico de `0001`. A ausência foi
  encontrada ao comparar todas as tabelas/colunas do ORM com o schema novo.
  O upgrade preserva a tabela existente. O downgrade remove a dependente antes
  de `customers`, mas recusa a operação se tags não estiverem vazias.
- `0016_delivery_user_assignment` e `0022_delivery_fk_fix`: preservam FKs
  equivalentes e evitam duplicá-las; suportam instalações legadas sem a tabela
  `users`, usando `admin_users` sem inventar uma tabela em banco existente.
  O caminho legado com `users` e seu rollback também foram testados.

Compatibilidade: revisions já aplicadas não são reexecutadas por `upgrade head`;
seus números e a cadeia de versões permanecem os mesmos. Bancos com `0008`
pendente podem possuir ou não índice/FK: os objetos válidos são preservados,
com OID do índice inalterado nos testes. Nenhum índice legítimo é apagado no
upgrade, e dados sintéticos existentes foram preservados. Um índice com o nome
esperado mas definição incompatível exige diagnóstico explícito e faz rollback
da tentativa, sem substituição automática.

As alterações históricas devem ser distribuídas no mesmo artefato para todos
os ambientes. Se uma installation já aplicada tiver drift/objetos faltantes,
`upgrade head` não reaplica revisions anteriores nem faz reparação implícita;
é necessário inventariar esse schema e planejar uma migration corretiva própria.
Isso preserva a regra de não mudar schema de bancos existentes sem necessidade.

Resultados PostgreSQL real:

- database vazio: `alembic upgrade head` PASS;
- `alembic downgrade 0007_estimated_prep_time` e `upgrade head` PASS;
- `alembic downgrade base` e novo `upgrade head` PASS, sem dados operacionais;
- índice existente, ausente ou equivalente sob nome legado: PASS;
- `0008` já aplicada: dados e OID preservados;
- FKs e constraints verificadas; exatamente um índice de lookup de `product_id`;
- todas as tabelas/colunas usadas pelo ORM estão presentes no schema novo;
- revisão com dados de tags: downgrade recusado, dados e DDL preservados.

## Dados e fluxo end-to-end

Foram criados dois tenants sintéticos, owner, admin e operator de teste, os
três planos e seus entitlements, mappings e intents internos controlados.
Nenhum identificador ou dado pessoal de clientes reais foi reutilizado.

O fluxo usa o adapter existente com respostas OAuth/vendas sintéticas via
`httpx.MockTransport`. Isso valida o código de integração e os contratos usados
pelo serviço, sem chamar a Kiwify real ou comprovar disponibilidade externa.

Fluxo validado:

`BillingEvent sanitizado → KiwifyVerificationService → manual_review → decisão
administrativa → SubscriptionService → audit log`.

- Ingestão não autenticada não ativa assinatura.
- Venda paga confirmada sem vigência confiável fica em `manual_review`.
- Aprovação confirma vínculo interno e deixa a assinatura `inactive`.
- `manual_review_period_missing` é preservado.
- `current_period_end` permanece nulo; não há período presumido.
- `EntitlementService` não concede entitlement a essa assinatura inativa.
- Rejeição preserva o evento e registra categoria e ator humano.
- As sessões administrativas e o RBAC reais são exercitados; não há override
  de autenticação no teste HTTP/browser.

## Concorrência e isolamento

Os testes PostgreSQL cobrem recebimento repetido e concorrente do mesmo evento,
duas aprovações simultâneas, disputa de workers, lease expirado, finalização de
worker obsoleto, retry após falha e tentativa de duas assinaturas correntes
para o mesmo tenant. Uma aprovação vence; a concorrente recebe conflito.

Admin do tenant A não lista nem decide eventos do B. Operator não possui acesso.
Eventos sem correlação confiável ficam invisíveis à fila de tenants. Auditoria
mantém o tenant e o ator humano corretos. Não há correlação por PII.

## Segurança e logs

Foi encontrado um vazamento no access logger padrão do Uvicorn: seu handler
próprio contornava o formatter com redaction e imprimia o query parameter
`signature`. `configure_logging()` agora encaminha `uvicorn`, `uvicorn.error`
e `uvicorn.access` pelo formatter JSON já utilizado pela aplicação.

Foi adicionado teste com a configuração real de logging do Uvicorn. Uma
requisição HTTP real também confirmou a ausência de marcadores sintéticos de
signature, token, senha e PII nos logs do backend/frontend. A resposta e a tela
administrativa exibem somente evidência sanitizada. Não há fixture com secret
real ou payload de cliente.

Isso não valida os access logs de proxies externos. Logs, retenção e redaction
do gateway Railway: **PENDENTE DE STAGING RAILWAY**.

## Frontend e feature flags

Build Next.js executado com `NEXT_PUBLIC_API_URL=''` e
`STOREFRONT_BACKEND_URL=http://127.0.0.1:8015`, substituindo explicitamente a
configuração de API de produção existente no projeto. O browser bloqueia
requests para origens externas. Backend HTTP, frontend e PostgreSQL usados
pela interface são reais e isolados.

Chromium validou listagem, filtro por evento, detalhe, aprovação, rejeição,
estado de erro 503, RBAC e isolamento entre tenants em
`/subscriptions/reviews`. A mensagem informa que o vínculo foi validado e o
acesso continua pendente por ausência de período confiável.

`KIWIFY_UNTRUSTED_INGRESS_ENABLED` continua false por padrão. Foi true somente
no processo efêmero do backend de teste, em loopback, para exercitar a ingestão;
isso não alterou configuração persistente de nenhum ambiente. Não foi criada
ativação automática nem habilitado cron externo. Cookie sem Secure foi usado
somente no HTTP loopback de teste; staging público deve usar HTTPS e Secure.

## Execução reproduzível

Requer Python com dependências backend/testes, driver `psycopg`, Playwright,
Chromium, Node e PostgreSQL real descartável. O browser usa Chromium em
`/usr/bin/chromium`. Ambos os validadores aceitam exclusivamente PostgreSQL
loopback e exigem confirmação explícita. Use uma conexão de teste fornecida
por secret local, sem imprimir seu valor.

No diretório backend, com `FOMIZERO_PHASE4_DATABASE_URL` já fornecida pelo
ambiente para o banco temporário:

```sh
export FOMIZERO_PHASE4_CONFIRM_STAGING=yes
python scripts/validate_billing_pg_history.py
python -m pytest tests/staging -q
```

O primeiro comando retorna exit 0 com `full_upgrade=PASS` após a correção.
Qualquer retorno FAIL deve bloquear o avanço; não usar stamp para mascará-lo.

No frontend, prepare o build exclusivamente local:

```sh
NEXT_PUBLIC_API_URL='' STOREFRONT_BACKEND_URL=http://127.0.0.1:8015 NEXT_TELEMETRY_DISABLED=1 npm run build
```

No backend, com as mesmas duas variáveis de teste:

```sh
python scripts/validate_billing_isolated_browser.py
```

As portas 8015/3015 devem estar livres. O script confere o rewrite do build,
gera credenciais sintéticas em memória, usa sessões reais, encerra os grupos
de processos criados e remove seu schema próprio. Não reutiliza servidores
existentes. O resultado é um JSON de verificações booleanas sem secrets/PII.

## Resultados dos testes

- PostgreSQL opt-in: **23 passed**, 42 warnings, 43,75 segundos; 12 testes de
  histórico/compatibilidade e 11 de billing/concorrência/E2E.
- Backend completo: **476 passed, 23 skipped**, 513 warnings, 83,09 segundos.
  Os 23 testes PostgreSQL são opt-in e passaram separadamente acima.
- Frontend `npm test`: **5 arquivos passaram**, nenhuma falha.
- Frontend build: passou, direcionado ao backend loopback.
- Smoke existente: passou; o script atual é somente um echo, não comprova UI.
- HTTP/Chromium real: seis verificações passaram, incluindo logs sanitizados.
- OpenAPI critical contracts: unchanged.
- Alembic: head único `20261007_02_billing_review`.
- Histórico completo PostgreSQL vazio: **PASS**, incluindo CLI e roundtrips.
- `git diff --check`: passou, incluindo verificação dos arquivos novos.

Warnings existentes não foram promovidos a falhas. A distinção entre backend
SQLite/regressão, testes PostgreSQL e browser real é preservada neste relatório.

## Preparação necessária para staging no Railway

### Quais serviços precisamos criar

Criar ambiente/projeto de staging separado, PostgreSQL exclusivo, serviço
backend e serviço frontend. Redis exclusivo será necessário se os fluxos que
dependem dele forem habilitados. Um serviço cron de reconciliação pode ser
preparado, mas deve permanecer sem agenda ativa nesta validação inicial.

### Quais variáveis de ambiente serão necessárias

Backend:

- `DATABASE_URL`: conexão privada somente do PostgreSQL de staging;
- `ENV=staging` e `ENVIRONMENT=staging`;
- `ADMIN_SESSION_SECRET` e `JWT_SECRET_KEY`: secrets exclusivos de staging;
- `ADMIN_SESSION_COOKIE_SECURE=true`, `ADMIN_SESSION_COOKIE_HTTPONLY=true`,
  `ADMIN_SESSION_COOKIE_SAMESITE=lax` para o proxy de mesma origem;
- `ADMIN_SESSION_COOKIE_DOMAIN`/`COOKIE_DOMAIN`: sem domínio de produção;
  preferir cookie host-only;
- `CORS_ORIGINS` ou `ORIGENS_CORS`: origens exatas de staging;
- `PUBLIC_BASE_DOMAIN`: domínio exclusivo de staging;
- `KIWIFY_UNTRUSTED_INGRESS_ENABLED=false`;
- `FEATURE_LEGACY_ADMIN=false`, `DEV_BOOTSTRAP_ALLOW=false` e sem
  `DEV_ADMIN_PASSWORD`;
- `REDIS_URL`: somente Redis de staging, se usado.

Frontend:

- `STOREFRONT_BACKEND_URL`: backend de staging;
- `NEXT_PUBLIC_API_URL=''`: API pelo proxy de mesma origem;
- `PORT`: fornecida pelo Railway.

Fazer novo build com essas variáveis; não reutilizar artefato apontando para
produção. Se, em uma etapa futura autorizada, houver consulta real à Kiwify,
serão necessários `KIWIFY_ENVIRONMENT`, `KIWIFY_PROVIDER_ACCOUNT_ID`,
`KIWIFY_API_CLIENT_ID` e `KIWIFY_API_CLIENT_SECRET` com conta/permissões
controladas. Não fornecer credenciais de produção para reproduzir estes testes.
Nenhum algoritmo presumido de signature ou secret de webhook é necessário
para a validação sintética desta fase.

### Quais migrations rodar

Com o bloqueio corrigido e o upgrade vazio comprovado, executar
`alembic heads` e `alembic upgrade head` no banco exclusivo de staging, até
`20261007_02_billing_review`. Rodar `scripts/seed_plans.py` conforme sua CLI
existente. Não usar stamp para esconder uma migration falhada. Downgrade com
auditoria exige política de arquivamento e ensaio de restore; não deve apagar
evidências. O histórico completo corrigido foi validado isoladamente; o upgrade
no ambiente gerenciado é **PENDENTE DE STAGING RAILWAY**.

### Como separar staging de produção

Separar projeto/ambiente, serviços, PostgreSQL, Redis, domínios, credenciais,
sessões, variáveis e backups. Não clonar PII nem tenants reais. Seed somente
dados sintéticos. Não alterar URL do webhook Kiwify. Evitar referências
Railway cruzadas entre ambientes e conferir o destino antes de qualquer
migration. Restringir acesso administrativo e de rede ao staging.

### Como validar antes do deploy

Exigir upgrade completo desde banco vazio, testes de billing PostgreSQL,
regressão backend, frontend tests/build, OpenAPI, head único e diff check.
Depois repetir o fluxo browser com dados sintéticos em staging e testar
TLS/cookies, proxy, logs de gateway, roles/extensões PostgreSQL, backup/restore
e disputa de workers em múltiplos processos/serviços. Os testes atuais de
concorrência usam conexões/sessões independentes no PostgreSQL isolado.
Validação de infraestrutura gerenciada e múltiplos serviços Railway:
**PENDENTE DE STAGING RAILWAY**.

### Quais feature flags devem permanecer desligadas

`KIWIFY_UNTRUSTED_INGRESS_ENABLED=false`, `FEATURE_LEGACY_ADMIN=false` e
`DEV_BOOTSTRAP_ALLOW=false`. Não ativar agenda de reconciliação nem automação
comercial em produção. Não há nova flag de quotas ou ativação criada nesta
fase; esses comportamentos continuam fora do escopo. Qualquer ativação de
ingress para teste futuro deve ser explícita, restrita a staging e revertida.

## Riscos restantes e próxima decisão

O bloqueio de histórico foi removido. GO para preparar e validar staging
Railway separado; a infraestrutura real ainda não está validada. Não há GO
para automação comercial/produção. Permanecem não confirmados o contrato oficial da signature
e a vigência recorrente consultável na Kiwify. Infraestrutura, frontend e logs
em Railway real são **PENDENTE DE STAGING RAILWAY**.

O fluxo de vínculo inativo pode continuar sendo preparado; nenhum resultado
desta fase autoriza ativação comercial, períodos presumidos, enforcement ou
deploy em produção.
