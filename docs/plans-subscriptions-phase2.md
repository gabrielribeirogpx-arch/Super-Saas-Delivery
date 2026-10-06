# Planos e assinaturas — Fase 2

## Objetivo e escopo

Ciclo interno auditável de assinaturas e infraestrutura de correlação para futuros
providers. Parte da Fase 1 integrada à `main` no PR #787. Não há webhook de billing,
chamada de API, segredo, checkout real, cobrança, reconciliação externa, quota em
produção nem bloqueio por plano. Nenhum router operacional chama os novos serviços.
O único ajuste em router é permitir leitura compatível de atores automáticos no
endpoint administrativo de auditoria já existente.

## Models

### BillingOfferMapping

`billing_offer_mappings`: `id`, `provider`, `environment`, `provider_account_id`,
`external_product_id`, `external_offer_id`, `plan_id`, `active`, `created_at`,
`updated_at`. FK para `plans.id`.

A combinação `(provider, environment, provider_account_id, external_product_id,
external_offer_id)` é única. Todos os componentes são obrigatórios e não vazios,
evitando a ambiguidade de unicidade com NULL. O plano é sempre passado explicitamente;
não há inferência por preço ou nome. Mapping inativo ou plano inativo não é resolvido.
IDs externos são sensíveis a maiúsculas/minúsculas e não são derivados de emails.

Providers são códigos extensíveis em minúsculas, como `kiwify` ou `future_provider`.
Ambientes válidos são `sandbox` e `production`; não há estado compartilhado entre eles.
Os adapters futuros deverão normalizar os nomes externos desses ambientes.

### BillingCheckoutIntent

`billing_checkout_intents`: campos solicitados, mais `provider_account_id` obrigatório
para correlação sem mistura de contas. FKs para `Tenant.id` e `Plan.id`. O token é
produzido por `secrets.token_urlsafe(32)`: 256 bits de aleatoriedade criptográfica,
43 caracteres, sem dependência de IDs, email, slug, preço ou nome. Tem constraint única.
O token é um identificador de correlação, não autenticação nem prova de pagamento.

Estados: `pending`, `completed`, `expired`, `canceled`. Não compartilha enum com
assinaturas ou eventos. `expires_at` é obrigatório; no instante da expiração, um
intent pendente já não pode ser concluído ou correlacionado a evento.

`BillingCatalogService` permite criar/resolver mappings, criar/consultar intents,
registrar um ID futuro de checkout (`bind_checkout`), concluir e expirar intents.
Nenhuma dessas operações chama providers ou ativa uma assinatura.

O binding de checkout é imutável e tem unique `(provider, provider_account_id,
environment, external_checkout_id)`. NULL permite intents ainda sem checkout.
A conclusão preserva bindings existentes quando um argumento não é informado,
rejeita substituições e usa UPDATE condicional de status/validade para impedir duas
conclusões concorrentes. Um intent concluído em tempo hábil pode ser ligado a um
evento recebido depois da sua data de expiração; intents pendentes expirados,
explicitamente expirados ou cancelados são rejeitados.

### BillingEvent

`billing_events`: todos os campos de inbox solicitados. `schema_version` é inteiro
positivo e `attempt_count` não pode ser negativo. Tem timestamps de recebimento,
ocorrência e processamento, campos de tentativa/erro e links internos opcionais.

Estados próprios: `pending`, `processing`, `processed`, `failed`, `dead_letter`.
Esta fase apenas recebe e correlaciona eventos internos como `pending`; não há worker,
job, processamento automático nem tradução de estados externos. Os demais campos
preparam a infraestrutura para a próxima fase. Um registro `processed` exige
`processed_at` no banco.

A barreira de idempotência é a unique constraint:

```text
(provider, provider_account_id, environment, provider_event_id)
```

`BillingInboxService.receive_event()` usa `INSERT ... ON CONFLICT DO NOTHING RETURNING`
em PostgreSQL e SQLite. Duas entregas concorrentes produzem um único registro; a
resposta informa `created=True/False`. SQLite deve suportar RETURNING (3.35+).

Duplicação legítima conserva ID, status, contagem de tentativas e links. Reutilização
da mesma identidade com hash, tipo, schema ou data de ocorrência diferentes é
rejeitada com `event_identity_payload_mismatch`, sem sobrescrever o registro original.
O hash é SHA-256 de JSON canônico (chaves ordenadas, UTF-8, sem NaN), não hash dos bytes
HTTP originais. A futura autenticação de webhook deve verificar os bytes originais
antes de chamar a inbox e não reutilizar este hash como assinatura de autenticidade.

## Fluxo interno e correlação

1. Um operador autorizado configura explicitamente a oferta externa e seu `Plan.id`.
2. O sistema cria um intent com `Tenant.id`, plano, conta, provider, ambiente e validade.
3. Um adapter futuro registrará o ID do checkout no intent e transportará o token opaco
   como correlação, conforme as capacidades documentadas do provider.
4. Após autenticar o evento no adapter, o sistema poderá registrá-lo na inbox.
5. O código interno resolve o intent/tenant por IDs confiáveis e chama `link_event`.
   A ligação valida tenant, conta, provider e ambiente; vínculos já definidos são
   imutáveis. Se ambos intent concluído e assinatura forem ligados, um ID externo de
   assinatura previamente associado ao intent deve coincidir com a assinatura.
6. O futuro processador fará a tradução canônica e chamará `SubscriptionService`,
   em uma unidade de trabalho com a conclusão do evento.

A inbox não extrai tenant ou plano de payload, email ou nome. Sem correlação segura,
o evento continua pendente e sem tenant; não existe fallback por email.
`link_event` é API interna confiável, não uma fronteira pública de autorização.
Apenas ter um token público não autoriza alterar assinatura. Antes de aplicar um
pagamento, o futuro adapter/processador deverá também verificar que o plano da oferta
mapeada coincide com o plano desejado no intent.

FKs compostas `(subscription_id, tenant_id)` e `(checkout_intent_id, tenant_id)`
impedem ligações cruzadas no banco. Se um desses IDs estiver preenchido, `tenant_id`
é obrigatório. Em SQLite, enforcement de FKs requer `PRAGMA foreign_keys=ON` na
conexão; os serviços também validam os vínculos. A configuração global de conexões
legadas não foi alterada nesta fase. `Subscription.provider` continua sendo metadata; o serviço de ciclo
não conhece nenhum provider específico. Para correlacionar somente pelo ID externo
de assinatura, a Fase 3 precisará de um vínculo explícito e scoped por conta/ambiente;
a Fase 2 não implementa essa busca nem presume unicidade global desse ID.

## SubscriptionService e transições

Métodos: `create_subscription`, `start_trial`, `activate_subscription`, `mark_past_due`,
`schedule_cancellation`, `cancel_subscription`, `expire_subscription`, `change_plan`.
Toda mutação exige `tenant_id`; transições também exigem o ID interno da assinatura.
A consulta é filtrada por ambos. Planos de criação, ativação e mudança precisam estar
ativos. Provider é metadata opcional; IDs externos só são aceitos quando há provider.

| Estado anterior | Próximos estados permitidos |
| --- | --- |
| inactive | trialing, active, canceled |
| trialing | active, canceled, expired |
| active | past_due, canceled, expired |
| past_due | active, canceled, expired |
| canceled | expired |
| expired | nenhum |

Regras adicionais:

- Criação sempre começa em `inactive`; `start_trial` concede trial com data final futura.
- Ativação requer início não futuro e fim estritamente futuro. Reativar `past_due`
  limpa atraso/carência e registra o período informado; mantém cancelamento agendado.
- `mark_past_due` só parte de active. Carência é opcional; se informada, deve ser futura.
- Cancelamento agendado só em trialing/active/past_due, com vigência efetiva futura;
  não muda o status nem encerra acesso. Repetir agendamento é rejeitado.
- Cancelamento efetivo registra `canceled_at`, limpa o agendamento e encerra carência.
- Expiração de trialing/active/past_due exige fim efetivo conhecido e já alcançado;
  carência futura impede expiração prematura.
- Exceção explícita: canceled pode virar expired após `canceled_at`, mesmo se o período
  contratado originalmente ainda fosse futuro, pois o acesso já foi encerrado.
- Inactive pode ser cancelado para encerrar uma contratação não ativada.
- Mudança de plano é imediata, sem prorata ou cobrança, mantém o status e registra
  plano anterior/novo. Não é permitida em canceled/expired nem para o mesmo plano.
- Não existe reabertura arbitrária de estados terminais. Uma futura política de nova
  contratação/renovação após expired exigirá transição explícita e auditada.

## Uma assinatura corrente e histórico

Mantém-se a unique `subscriptions.tenant_id` da Fase 1. É uma garantia mais forte:
existe um único registro interno por tenant, em qualquer estado; não há duas linhas
correntes e não se libera outra linha quando a anterior termina. O histórico está
nos registros de auditoria append-only com snapshots antes/depois, não em assinaturas
concorrentes ou em registros sobrepostos de contratos. Nenhuma transição apaga audit log.

O campo `Subscription.version`, inicialmente 1 para registros existentes, usa controle
otimista do SQLAlchemy. UPDATEs verificam a versão no banco e a incrementam. O serviço
usa também `SELECT FOR UPDATE` onde o banco suporta e aceita `expected_version` para
rejeitar comandos baseados em leitura antiga. SQLite não fornece row lock equivalente;
versão, unique constraints e UPDATEs condicionais continuam sendo as barreiras.

SQLite pode retornar erro transitório de lock sob concorrência. O chamador deve fazer
rollback e repetir a transação completa; não continuar uma sessão falha. Não existe
job ou reconciliador nesta fase. Alterações diretas via SQL/Core em assinaturas não
participam automaticamente da versão/auditoria e não são APIs de negócio autorizadas.

## Transações e audit log

Assinatura e audit log são gravados na mesma transação, com flush antes da conclusão.
Falha de validação, conflito de versão ou falha no audit log não deixa transição parcial.
Os serviços iniciam/commitam uma transação se a sessão estiver ociosa. Se já houver uma
transação (inclusive por leitura anterior), usam um savepoint; o chamador é responsável
por commit/rollback externo. A implementação inicia o BEGIN físico do SQLite antes do
savepoint para impedir que alterações escapem de um rollback externo.

Preferir sessão dedicada e unidade de trabalho explícita, principalmente para combinar
evento, intent e assinatura:

```python
with SessionLocal.begin() as db:
    subscription = SubscriptionService(db).create_subscription(tenant_id, plan_id)
    SubscriptionService(db).activate_subscription(
        tenant_id, subscription.id, current_period_end=period_end
    )
```

O audit log administrativo existente ganhou `actor_type` (`user`, `system`, `provider`)
e `user_id` nullable. Constraints impedem atribuir user_id a ator automático ou omitir
o ID humano em ator user. Registros existentes continuam como user, sem modificar IDs.
Chamadas existentes a `log_admin_action` continuam com o comportamento anterior.

`SubscriptionActor` informa origem, ator e correlation ID opcional. Atores humanos
precisam pertencer ao mesmo tenant e estar ativos. Operações automáticas usam ID nulo,
sem usuário fictício. O chamador continua responsável pela autorização de negócio.

Ações: `subscription.created`, `subscription.trial_started`, `subscription.activated`,
`subscription.past_due`, `subscription.cancellation_scheduled`, `subscription.canceled`,
`subscription.expired`, `subscription.plan_changed`. Os logs incluem tenant, ID interno,
origem, correlation ID, snapshots de estado/datas/versão e IDs dos planos anterior/novo.
Não guardam payload externo, secrets, customer ID ou token do intent.

O endpoint de auditoria aceita `user_id=null` e retorna `actor_type`; mantém autenticação,
isolamento e todos os campos/valores antigos de logs humanos. Nenhuma inbox ou payload
novo é exposto por endpoint administrativo ou público.

## Payload protegido e retenção

O `raw_payload` **não contém o payload original**. O serviço o descarta após calcular
o hash e persiste somente `{"redacted": true, "payload_hash": ..., "schema_version": ...}`.
Não retém nomes, emails, documentos, endereços, cartões, tokens ou credenciais.
Não há logging do payload completo nem de erros contendo conteúdo externo.
O limite de entrada interna é 1 MiB de JSON canônico.

A política de retenção da representação protegida é 90 dias; a limpeza administrativa
ou política de armazenamento deverá ser implementada antes do primeiro ingresso externo.
Não há job de retenção nesta fase. As identidades únicas e hashes precisam ser mantidos
como tombstones enquanto o provider puder reenviar eventos, evitando que exclusão
prematura elimine a idempotência. Auditoria segue a retenção administrativa existente;
nenhuma rotina desta fase remove histórico. A ausência de payload original impede
replay bruto; adapters futuros devem definir um DTO canônico mínimo sem PII para replay,
se necessário, sem relaxar a proteção adotada aqui.

## Compatibilidade legacy

`EntitlementService` não foi alterado. Tenant persistido sem assinatura continua com
`legacy_no_subscription`. Criar mapping, intent ou evento não cria/ativa uma assinatura.
Não há backfill de tenants nem atribuição automática de plano. Transições internas
só acontecem quando os novos serviços forem chamados explicitamente. Nenhuma decisão
comercial é aplicada a operações existentes ou muda configuração operacional da loja.

## Migrations

Cadeia única após `20261006_03_subscriptions`:

1. `20261006_04_billing_offers`: mappings.
2. `20261006_05_billing_intents`: intents.
3. `20261006_06_billing_events`: inbox, unique de idempotência e links.
4. `20261006_07_billing_audit`: versão/unique composta em subscriptions, FK composta
   da inbox para assinatura, ator automático no audit log.

Aplique antes de executar o código novo, a partir de um banco já na Fase 1. Não há
alteração em pedidos, usuários, tenants, WhatsApp ou outras tabelas operacionais.
SQLite usa batch nas alterações de constraints. PostgreSQL usa DDL nativo, sem enum
de provider. As revisões da Fase 1 não foram modificadas.

```bash
python -m alembic upgrade head
python scripts/check_alembic_single_head.py
python -m pytest -q tests/test_billing_phase2.py tests/test_billing_phase2_migrations.py
```

Downgrade até Fase 1 funciona quando todos os audit logs possuem user_id humano. Se
existirem registros automáticos com user_id nulo, a primeira etapa **recusa o downgrade**,
antes de alterar schema, para não apagar histórico nem inventar ator humano ao restaurar
NOT NULL. Arquivar com preservação e uma política autorizada é pré-requisito; a migration
não faz isso automaticamente. Downgrade de tabelas novas remove seu conteúdo, como
qualquer reversão de schema; preserve os registros necessários antes de aplicá-lo.
Os testes validam tanto o roundtrip seguro como a recusa sem perda de histórico.

Os testes de migrations da Fase 1 foram ajustados para continuarem verificando seu
schema histórico, sem exigir campos introduzidos apenas na Fase 2.

## Riscos restantes e preparação da Fase 3 Kiwify

- Validar upgrade/downgrade e concorrência em PostgreSQL real de staging. Nesta fase
  houve execução SQLite, verificação de paridade schema/model e geração de SQL PostgreSQL.
- Definir contrato documentado do provider: autenticação do ingresso, escopo da conta,
  IDs de produto/oferta/evento, propagação do token e vínculo scoped da assinatura externa.
- Definir tradução de eventos/estados, precedência temporal, renovação de períodos,
  recontratação de estados terminais e repetição idempotente de comandos comerciais.
  Idempotência de inbox não substitui processamento idempotente ou ordenação de eventos.
- Implementar claim/lease, atualização atômica de processed, retries/backoff e dead letter,
  em transação com a alteração de assinatura. Campos existem; worker não foi implementado.
- Definir DTO canônico mínimo de replay e executar retenção antes do ingresso externo.
- Somente então adicionar o adapter Kiwify, secrets e webhook autenticado em uma fase
  separada, mantendo observação e sem ativar bloqueios por consequência dessa integração.

## Resultados executados

- `python -m pytest -q`: **398 passed**; 353 avisos de depreciação (Starlette,
  passlib e defaults existentes com `datetime.utcnow()`).
- `python -m pytest -q tests/test_billing_phase2.py tests/test_billing_phase2_migrations.py`:
  **72 passed**, incluindo concorrência real em conexões SQLite separadas, unicidade,
  matriz de transições, rollback, audit automático, isolamento e migrations.
- `npm test` no frontend existente: **4 passed**, sem falhas.
- `python scripts/check_alembic_single_head.py`: aprovado;
  único head `20261006_07_billing_audit`.
- Upgrade/downgrade/upgrade da Fase 1 à Fase 2 em SQLite: aprovado;
  dados históricos e schema operacional preservados; models e schema comparados.
- Geração de SQL de upgrade/downgrade PostgreSQL: aprovada, sem enum nativo externo.
- `git diff --check` e whitespace dos arquivos novos: aprovados.

Nenhum banco de produção foi alterado. As migrations foram executadas somente em
bancos temporários de teste. Implementação preparada na branch local
`feat/subscription-lifecycle-phase2`; sem integração externa ou ativação de bloqueios.

## Revisão intencional do contrato AdminAuditRead (PR #788)

O CI `Validate OpenAPI critical contracts` encontrou exatamente três diferenças:
adição de `properties.actor_type`, adição de `properties.user_id.anyOf` e remoção
de `properties.user_id.type`. O snapshot crítico inclui **todos** os components,
mesmo quando o path da auditoria não está na seleção de paths críticos. A mudança
não é causada por versão de dependência ou inclusão de novo endpoint; faltou
atualizar o snapshot para a mudança de auditoria já implementada na Fase 2.

| Campo | Antes | Agora |
| --- | --- | --- |
| user_id | chave obrigatória, integer | chave obrigatória, integer ou null |
| actor_type | ausente | string, default `user`, opcional no schema; sempre retornado pelo endpoint |

`Optional[int]` sem valor default mantém `user_id` na lista `required` no Pydantic.
Nullable significa que a chave pode conter null, não que possa ser omitida. Logs
humanos preservam o ID numérico e todos os campos anteriores. Logs automáticos
representam a ausência de usuário humano com null e informam `system` ou `provider`.

A alteração é necessária para a arquitetura da Fase 2 e para as constraints do audit
log. Não existe compatibilidade total com clientes antigos que validam todas as
respostas como `user_id: number`: esses clientes precisam aceitar `number | null`.
A adição de `actor_type` é aditiva para leitores tolerantes a campos extras; leitores
que rejeitam propriedades extras também precisam atualizar seu schema. Não há
regressão nos payloads humanos existentes.

Consumidores encontrados no repositório:

- A tela Next.js `app/(admin)/audit/page.tsx` usa nome/email e não lê nem tipa `user_id`.
  Já aceita nome/email nulos; não exige alteração para consumir esta resposta.
- O cliente `src/api/generated.ts` contém somente funções/types de delivery e não
  contém `AdminAuditRead` ou `/api/admin/audit`; não há cliente gerado de auditoria
  a regenerar no repositório. Um cliente externo gerado do contrato anterior deverá
  ser regenerado com o snapshot novo.
- A UI administrativa legada em `app/routers/admin.py` usa `user_id` como fallback
  de rótulo. O JSON nullable não causa erro de execução, mas pode apresentar `#null`
  para ator automático sem nome. Essa limitação cosmética é registrada; a correção
  de contrato não altera esse renderer legado.

Um inteiro sentinela/usuário fictício atribuiria falsamente a operação a humano;
omitir logs automáticos eliminaria observabilidade. Um endpoint versionado separado
seria alternativa para consumidores externos estritos, mas exige contrato e migração
próprios e não se justifica pelos consumidores internos encontrados. A opção mantida
é `user_id` nullable com `actor_type` explícito, conforme a Fase 2.

Snapshot aprovado: `Super_SaaS_ Burger_backend/contracts/openapi_snapshot.json`.
Somente `AdminAuditRead` foi alterado no snapshot. Testes novos verificam o schema
aprovado, a obrigatoriedade da chave, payload humano anterior e serialização de
atores user/system/provider; o teste HTTP de auditoria também verifica provider.

Validação da correção de contrato: OpenAPI critical contracts aprovado; **404 testes
backend aprovados**, incluindo **7 testes focados** de contrato/auditoria; `npm test`
com **4 aprovados**; `npm run test:smoke` aprovado. O script smoke atual apenas imprime
uma mensagem e não exercita a interface; não foi modificado nesta correção.
Head Alembic único e `git diff --check` aprovados. Nenhum schema funcional, migration
ou fluxo de assinatura foi revertido para atender ao snapshot.
