# Planos e assinaturas — Fase 1

## Escopo entregue

Domínio interno SQLAlchemy, três migrations Alembic separadas, catálogo idempotente e
`EntitlementService(db).evaluate(tenant_id, feature_code)`. O resultado é um dataclass
com `allowed`, `reason`, `limit`, `usage` e `effective_until`.

Esta fase é somente observação. Nenhum router, dependency de autorização, pedido,
login, entrega, configuração ou fluxo de onboarding usa o resultado para bloquear.
Não há integração de cobrança, checkout, webhook de assinatura nem job externo.
O serviço não altera status, não cria assinaturas e não executa autoflush de
alterações operacionais pendentes na sessão do chamador.

## Models e identidade

- `Plan`: `id`, `code` único (`essential`, `operation`, `pro`), `name`, `active`,
  `created_at`, `updated_at`.
- `PlanEntitlement`: `id`, `plan_id` com FK, `feature_code`, `enabled`, `limit_value`,
  `reset_period`. Unique `(plan_id, feature_code)`; valores negativos proibidos.
- `Subscription`: todos os campos de vigência, trial, cancelamento, atraso, carência
  e timestamps solicitados, além de provider e IDs externos opcionais.
  `tenant_id` tem FK para `tenants.id`; `plan_id` tem FK para `plans.id`.

Há uma assinatura interna atual por tenant, garantida por unique `tenant_id`.
Histórico de assinaturas e eventos ficará para a próxima fase. Não há vínculo por
owner, usuário, email, slug ou domínio. Os códigos do catálogo são identificadores
estáveis: alterações de nome comercial devem preservar o `code`.
`updated_at` é atualizado pelo SQLAlchemy em alterações via ORM; SQL direto deve
atualizá-lo explicitamente.

## Compatibilidade dos tenants

Um tenant persistido **sem assinatura** recebe `allowed=True`, `limit=None`,
`effective_until=None`, `reason="legacy_no_subscription"` para os dez códigos
conhecidos. O uso numérico continua disponível para observação.

Não se atribui Pro e não se cria assinatura fictícia. Isso preserva a situação atual
sem inventar direitos comerciais ou datas de contratação. A política também vale
para tenants novos sem assinatura nesta fase. Tenant inexistente e código desconhecido
não são classificados como legacy.

Uma assinatura persistida passa a ser avaliada segundo seu status e plano, inclusive
quando provider é nulo. Uma resposta negativa continua sendo exclusivamente
informativa: **nenhuma operação existente é bloqueada**. Apagar uma assinatura
restaura o fallback legacy; por isso esse fallback precisará ser explicitamente
revisto antes de qualquer enforcement comercial.

## Catálogo inicial

| Feature | Essencial (`essential`) | Operação (`operation`) | Pro (`pro`) |
| --- | --- | --- | --- |
| orders_monthly | 300 | 1500 | 5000 |
| admin_users | 1 | 3 | 10 |
| delivery_users | 1 | 5 | 15 |
| tracking | false | true | true |
| whatsapp | false | true | true |
| inventory | false | true | true |
| coupons | false | true | true |
| loyalty | false | false | true |
| custom_domain | false | false | true |
| advanced_reports | false | false | true |

- `enabled=False`: recurso desabilitado, mesmo se `limit_value` for zero ou nulo.
- `enabled=True, limit_value=0`: recurso habilitado sem capacidade adicional.
- `enabled=True, limit_value=NULL`: ilimitado; para booleanos representa permissão.
- `enabled=True, limit_value=N`: permite uma unidade adicional enquanto `usage < N`.
- `usage=None`: sem contador aplicável, não significa uso zero. Um entitlement com
  limite numérico e sem contador retorna `usage_unavailable`.

`orders_monthly` conta todos os pedidos criados no mês calendário UTC, incluindo
cancelados, no intervalo `[primeiro dia, primeiro dia do próximo mês)` e filtrados
por tenant. Não usa mês de faturamento, timezone da loja ou janela móvel.
`reset_period="monthly"` é obrigatório para esse contador.

`admin_users` conta registros ativos de `AdminUser` cujo role normalizado não seja
`delivery` (incluindo owner/admin/staff). `delivery_users` conta registros ativos
com role normalizado `delivery`. Não conta clientes, não mistura a tabela legada
`users` e não conta contas inativas. Esses limites representam capacidade simultânea,
portanto `reset_period=NULL`. Booleanos também usam `reset_period=NULL`.
Outras combinações de período retornam `unsupported_reset_period`.

## Status e vigência

O enum canônico possui apenas `inactive`, `trialing`, `active`, `past_due`,
`canceled`, `expired`, com constraint no banco e validação do ORM.

- `active`: vigente até `current_period_end`, se informado.
- `trialing`: vigente até a menor data informada entre `trial_end` e `current_period_end`.
- `past_due`: vigente somente com `grace_until` futuro, mesmo se o período já acabou.
- `inactive`, `canceled`, `expired`: sem direito comercial.
- Vigência futura (`current_period_start > agora`): sem acesso comercial até o início.
- Em `agora == effective_until`, a vigência já terminou.
- Datas naive vindas do SQLite são interpretadas como UTC.
- Assinaturas internas active/trialing sem data final não expiram implicitamente.
  A futura integração deve preencher datas de validade de assinaturas comerciais.

`cancel_at_period_end=True` em assinatura ativa não antecipa o encerramento; o acesso
permanece até a data final. `canceled` representa encerramento já efetivado.
Apenas ter `canceled_at` não cancela uma assinatura ativa. `past_due_since` é dado
informativo e não cria carência automaticamente.

Plano inativo ou entitlement ausente produz decisão negativa explícita. A permissão
comercial não habilita configurações da loja: por exemplo, WhatsApp permitido pode
coexistir com `WhatsAppConfig.is_enabled=False`. O serviço não é mecanismo de
autenticação nem de autorização; qualquer futura consulta HTTP deve validar o
acesso do solicitante ao tenant antes de chamar o serviço.

## Migrations e seed

As novas revisões formam uma cadeia após `20260716_customer_phone_otp`:

1. `20261006_01_plans`: cria somente `plans`.
2. `20261006_02_plan_entitlements`: cria somente `plan_entitlements`.
3. `20261006_03_subscriptions`: cria somente `subscriptions`.

Não alteram nem fazem backfill em tabelas operacionais. Downgrades removem apenas
as tabelas novas, em ordem inversa. O enum usa VARCHAR com CHECK, evitando tipos
nativos específicos de provider e permitindo SQLite e PostgreSQL.

Executar da raiz do backend com `DATABASE_URL` apontando para o banco correto:

```bash
python -m alembic upgrade head
python scripts/seed_plans.py
python scripts/check_alembic_single_head.py
```

O seed é explícito, transacional e não roda no startup. Reexecutar não duplica planos
ou entitlements, completa entradas ausentes e preserva valores já existentes,
inclusive alterações comerciais intencionais e planos inativos. Deve ser executado
serialmente como comando administrativo/deploy; a unique constraint protege contra
duplicação, mas a corrida entre duas execuções simultâneas pode exigir reexecução.
Não insere nem altera tenants ou assinaturas.

## Verificação e limites

Os testes cobrem toda a matriz, idempotência e catálogo parcial, booleanos, zero,
ilimitado, contadores e limites, isolamento por tenant, status, trial, carência,
expiração, cancelamento agendado, configuração operacional independente, constraints,
consulta sem autoflush e compatibilidade das operações existentes. As migrations
são verificadas em upgrade/downgrade/upgrade SQLite com preservação de dados e
schema operacional, além da geração de SQL PostgreSQL.

A validação SQL PostgreSQL não substitui um upgrade em staging PostgreSQL real.
Antes da cobrança, revisar as regras de timezone, pedidos cancelados, roles
administrativos, validade obrigatória e transição dos tenants legacy. Os contadores
são consultas ao banco, sem reserva atômica de capacidade; não são apropriados para
bloqueio concorrente sem trabalho adicional. Não há histórico de eventos comerciais.

## Próxima fase recomendada

Implementar o ciclo interno de criação/alteração de assinatura com auditoria,
transições canônicas e testes de idempotência. Definir o contrato de associação entre
identificadores externos e `Tenant.id`, as datas de validade e a política de migração
legacy. Então adicionar o adaptador do provider escolhido e seus eventos de forma
idempotente, mantendo a observação antes de ativar qualquer bloqueio.

## Resultado da validação desta implementação

- Suite completa do backend: **326 passed** (72 avisos de depreciação).
- Testes novos do domínio e migrations: **61 passed**, incluídos na suite completa.
- Suite existente do frontend (`npm test`): **4 passed**, sem falhas.
- `scripts/check_alembic_single_head.py`: aprovado, único head
  `20261006_03_subscriptions`.
- `git diff --check`: aprovado.

As migrations e o seed foram executados somente em bancos temporários de teste.
Nenhum banco de produção foi alterado. Os avisos existentes envolvem Starlette,
passlib e uso de `datetime.utcnow()` em módulos operacionais.
