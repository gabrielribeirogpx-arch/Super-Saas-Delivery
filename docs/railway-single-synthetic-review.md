# Um único review sintético no staging Railway, sem shell

## Abordagem

Serviço **one-shot separado**, sem domínio público, cron ou servidor HTTP. Start
executa `scripts/prepare_single_staging_review.py` e termina. Não modificar o
start do backend principal. Nenhum deploy, push ou PR realizado nesta entrega.
A branch precisa ser publicada, mediante autorização, para Railway executar os
arquivos; a preparação local não os disponibiliza automaticamente no GitHub.

Reutiliza guards/identidade do helper, catálogo, inbox, SubscriptionService e
KiwifyVerificationService com transporte MockTransport injetado. Nunca consulta
Kiwify real, recebe webhook ou habilita a flag da aplicação.

**Um evento permite uma única decisão final: approve OU reject.** Pode inspecionar
ambas as opções, mas testar as duas até o fim requer outro evento e autorização.
Não resetar auditoria/decisão. Testes automatizados cobrem ambos os caminhos em
bancos independentes.

## Guards e pré-requisitos

- Banco e serviço exclusivamente no projeto/environment staging.
- Tenant ativo `meuburger`, ID confirmado no contexto da sessão administrativa
  (response de login na aba Network, apenas tenant_id; não copiar tokens/PII).
  Se indisponível, confirmar com responsável pelo staging; não inventar ID.
- Plano essential ativo já semeado; o job não cria planos.
- Head aplicado: conferido pelo startup check. O job não executa migrations.
- Recusa assinatura existente incompatível e outro evento pending associado
  ao tenant. Não altera assinatura comercial nem dados de usuários.

Variáveis do job, usando nomes existentes:

```env
ENV=staging
ENVIRONMENT=staging
KIWIFY_UNTRUSTED_INGRESS_ENABLED=false
FEATURE_LEGACY_ADMIN=false
DEV_BOOTSTRAP_ALLOW=false
LOG_LEVEL=INFO
```

DATABASE_URL: referência **somente ao PostgreSQL deste staging**, conexão privada,
scheme `postgresql+psycopg://`. KIWIFY_API_CLIENT_ID e KIWIFY_API_CLIENT_SECRET
ausentes/vazios: credentials reais são recusadas. Não copiar variáveis de
produção. Não precisa JWT, admin session secret, senha de owner ou Redis no job.

Exige flags, ambiente, confirmação explícita, host/database esperados e tenant
ID + slug. Esses guards não provam propriedade do banco: conferir referência ao
serviço correto no painel. Não usar URL de produção para testar recusa.

## Executar no Railway sem shell

**PENDENTE DE CONFIGURAÇÃO MANUAL NO RAILWAY. Não houve deploy autorizado.**

1. Criar `synthetic-review-once` dentro do projeto/environment de staging,
   conectado à branch que venha a conter os arquivos. Desabilitar autodeploy.
2. Root: `Super_SaaS_ Burger_backend`.
3. Build: `python -m pip install -r requirements.txt`.
4. Sem domínio, healthcheck, schedule ou volume; uma instância. Restart policy
   **Never**, para não transformar o job em loop/cron.
5. Configurar somente as variáveis acima e referência DB de staging.
6. Confirmar host/database no painel sem revelar URL/password e substituir os
   placeholders no start (host/database/tenant ID não são passwords):

   ```sh
   python scripts/prepare_single_staging_review.py --confirm-staging --expected-db-host <HOST_PRIVADO_DB_STAGING> --expected-database <NOME_DB_STAGING> --expected-tenant-id <ID_MEUBURGER> --check-only
   ```

   Esse primeiro deploy, quando autorizado, verifica configuração sem conexão
   ou gravação. Não precisa shell.
7. Para execução efetiva, remover **somente** `--check-only` e fazer deploy manual
   do job quando autorizado. O processo termina, não abre servidor HTTP.
8. Esperar exit 0 e JSON com synthetic_only=true, real_provider_calls=false,
   billing_event_id, tenant_id e verification_status=manual_review.
   Falhas mostram apenas classe de erro, sem SQL/URL/body/secrets.
9. Abrir UI imediatamente: evidência paga simulada vale **5 minutos**. Se expirar,
   reexecutar o mesmo job manualmente; só renova evidência de evento não decidido.
   Não aumenta prazo, gera outra identidade ou apaga decisão. Não habilitar a
   Kiwify real para contornar stale evidence.

## Registros criados

Apenas vinculados ao Tenant.id confirmado de meuburger:

- 1 mapping fictício essential, conta `phase4-2-meuburger-synthetic-only`,
  namespace interno sandbox e IDs determinísticos;
- 1 intent completed interno, sem checkout externo;
- 1 subscription **inactive**, sem datas de período, criada via serviço;
  auditoria system da criação;
- **1 BillingEvent**, projeção sanitizada, identidade/hash determinísticos;
- 1 BillingManualReview com venda paga **simulada**, sem vigência confiável;
  auditoria da camada existente de verificação.

Nenhum tenant/usuário/plano novo, nenhuma senha/PII real, nenhuma subscription
active e nenhum entitlement. A subscription inactive é preparada antes da
revisão para que EntitlementService não use legacy_no_subscription neste tenant
sintético. Não adiciona enforcement comercial ao sistema operacional.

Reexecuções não duplicam registros ou apagam decisões. Lock do Tenant na
transação inicial serializa jobs PostgreSQL concorrentes; unique da inbox e
leases existentes arbitram evento/verificação. Se verificação falhar após commit,
registros iniciais podem permanecer pending; a reexecução retoma sem apagar.

## Validar pela UI

1. Owner de meuburger: abrir `Assinaturas > Revisões pendentes`. Conferir um
   evento com ID do relatório, plano Essencial e tenant correto.
2. Detalhe: IDs sanitizados, evidência paid sintética, período ausente, sem PII.
   A frase existente da tela menciona Kiwify, mas NÃO houve venda real.
3. Validar sessão ausente/role insuficiente/isolamento usando contas de QA
   existentes. O job não cria usuários ou modifica RBAC.
4. Caminho recomendado: **Aprovar**, para testar ausência de vigência. Esperado:
   binding_approved, manual_review_period_missing, subscription inactive,
   nenhum current_period_end e nenhum entitlement. Auditoria humana com tenant
   correto. Nova decisão deve ser recusada.
5. Alternativa: rejeitar com categoria; evento permanece com decisão rejected e
   auditoria humana. Não será possível aprovar esse evento depois.
6. Revisar logs do job/aplicação/gateway sem imprimir secrets/cookies/payload/PII.
   Não enviar signature ou webhook real.

O job não adiciona tela de inspeção de Subscription/entitlements/audit. Se a UI
existente não expuser esses dados, marcar confirmação pós-decisão no banco como
pendente de acesso administrativo seguro. Testes/relatório não substituem essa
validação real; não criar endpoint público de debug.

## Desabilitar/remover

Depois do ensaio, remover serviço one-shot, ou desconectar source e mantê-lo
parado sem autodeploy/restart/schedule. Remover sua referência DATABASE_URL.
Não excluir evento/subscription/auditoria para repetir decisão. Flags continuam
false no backend. Script fica inerte sem execução explícita; pode ser removido
em mudança posterior, preservando evidências. Nenhum mecanismo temporário fica
no servidor principal.

## Validação local desta entrega

- Testes novos: 4 passed; approve/reject em bancos independentes, idempotência,
  preservação de decisão, isolamento/RBAC, auditoria humana, ausência de acesso,
  tenant errado e assinatura comercial preservada. HTTP real é proibido no teste.
- Backend completo: 493 passed, 23 skipped (opt-in, não validação Railway).
- OpenAPI critical contracts: passou na configuração de referência do CI.
- Alembic: head único 20261007_02_billing_review. Nenhuma migration nova.
- git diff --check e whitespace dos arquivos novos: passaram.

Não foi executado no staging Railway. Concorrência deste novo job em PostgreSQL
real, deploy/UI e auditoria pós-decisão permanecem pendentes de execução autorizada.
