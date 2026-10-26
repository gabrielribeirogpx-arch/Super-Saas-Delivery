# Kiwify: fila administrativa de revisões

Implementada sobre a main com o PR #791 mergeado. A signature continua sem
contrato oficial confirmado. O webhook é uma referência em quarentena, nunca
evidência autoritativa de pagamento, vigência ou identidade do tenant.

## Endpoints e interface

- `GET /api/admin/billing/reviews`: fila manual_review do tenant autenticado;
  filtros event_type, from_date, to_date, plan_id; limit 1–100 e offset.
- `GET /api/admin/billing/reviews/{event_id}`: detalhe sanitizado e condições
  atuais para aprovação.
- `POST /api/admin/billing/reviews/{event_id}/approve`: decisão humana de vínculo
  e, somente quando existir período confiável, ativação.
- `POST /api/admin/billing/reviews/{event_id}/reject`: motivo categorizado em
  `reason`: incorrect_binding, incorrect_plan, duplicate_sale, invalid_sale ou
  insufficient_evidence. Não aceita texto livre ou campos adicionais.

Tela em `Assinaturas > Revisões pendentes`, rota `/subscriptions/reviews`:
lista, filtros, paginação, detalhes, evidência, bloqueadores e decisão. Exibe:
“Venda confirmada pela Kiwify, mas vínculo/período da assinatura exige aprovação
administrativa.” Referências de assinatura/oferta recebidas não são apresentadas
como vínculo confirmado pelo provider.

## RBAC e isolamento

Sessão administrativa existente; require_role admin (inclui owner, conforme o
RBAC existente). O serviço revalida usuário ativo, papel e tenant no banco.
Operator, cashier e delivery não podem listar, consultar ou decidir. Tenant
informado no contexto da requisição é validado pelo mecanismo existente.

Não há papel global/plataforma criado nesta fase: cada administrador vê apenas
seu tenant. Um evento sem tenant correlacionável não é exposto a todas as lojas.
Somente uma intenção interna COMPLETED, com external_subscription_id já vinculado,
no mesmo provider/conta/ambiente, pode produzir um candidato sem vínculo anterior.
Correlação ambígua é ocultada. Mapping ausente não impede revisar um evento já
correlacionável, mas impede aprová-lo. Nenhuma correlação por PII ou valor.

POSTs exigem também `X-Billing-Review: 1`, um header não simples que impede envio
por formulário cross-site. A sessão e o RBAC continuam obrigatórios; esse header
não é um mecanismo de autenticação. A política CORS existente continua aplicável.

## Evidência e persistência

Nova tabela `billing_manual_reviews`, migration `20261007_02_billing_review`.
Registra somente referências, status paid confirmado pela API, instante da
consulta, período de fonte confiável quando disponível e decisão humana.
Referências de assinatura/oferta da projeção continuam candidatas, sujeitas à
validação humana e à intenção interna; não se tornam prova recorrente da API.

KiwifySalesAPI só produz VerifiedSale quando o contrato oficial de vendas retorna
id/produto correspondentes e status paid. Outros estados não deixam uma prova de
pagamento reutilizável. Uma nova consulta inconclusiva invalida o snapshot pago
anterior. Não persiste a resposta completa da API nem campos de Customer.

Os endpoints têm DTOs explícitos. Não expõem payload completo, dados pessoais,
dados de pagamento, public_token, conta secreta ou signature. Motivos externos são
convertidos para códigos permitidos. Não há secrets ou payloads reais em fixtures.

Os novos schemas BillingReviewRead e BillingReviewReject foram adicionados
intencionalmente ao snapshot OpenAPI. Contratos anteriores permanecem iguais.

## Decisão humana e período

Pré-condições: evento Kiwify schema v2 manual_review e pending, sem decisão
anterior ou lease ativo, venda paga confirmada nos últimos cinco minutos,
mapping ativo e plano ativo correspondente à intenção, tenant interno ativo e
correlação única. Apenas order_approved e subscription_renewed podem ser aprovados.
Bindings divergentes ou assinaturas terminais exigem tratamento separado.

Se a evidência da venda está antiga/ausente, o clique tenta uma consulta secundária
com lease/orçamento compartilhado, **somente se a integração estiver habilitada**.
Não segura a transação da requisição durante HTTP. Sem credenciais/consulta
conclusiva, não aprova. Essa atualização de evidência nunca ativa por si só.
Retries de uma revisão ainda não decidida preservam a exigência de decisão humana.

**Política confirmada: não inventar período.** Sem vigência confiável, aprovar
valida exclusivamente o vínculo comercial, cria/preserva Subscription INACTIVE
por SubscriptionService, associa o recibo e registra `binding_approved` com ator
humano. Mantém BillingEvent pending/manual_review e motivo
`manual_review_period_missing`. Não define current_period_start/end.

A interface informa: “Vínculo validado. O acesso continua pendente por ausência
de período confiável.” A assinatura inactive não concede entitlement comercial.
Nenhuma operação existente passa a consultar essa avaliação para bloquear a loja.
Tenants sem assinatura continuam com legacy_no_subscription.

Quando uma fonte autenticada completa fornecer período confiável, o worker pode
reavaliar o vínculo aprovado a cada hora e ativar **a mesma assinatura** por
SubscriptionService. Preserva o ator e a decisão originais. A API atual de vendas
não fornece esse período: a retomada com fonte completa está testada com fonte
sintética, não habilitada por contrato externo presumido.

Com período confiável já disponível e venda paga confirmada, a decisão chama o
caminho central de aplicação de prova, que usa SubscriptionService para criar,
ativar ou renovar e valida a versão. Nunca edita Subscription.status diretamente.
Uma assinatura existente ativa não é rebaixada para inactive quando faltar período.

## Atomicidade e auditoria

CAS no BillingEvent inclui estado, lease e ausência de decisão persistida.
Criação/ativação, vínculos, decisão e audit log pertencem à mesma transação.
Dupla aprovação, aprovação após processamento/rejeição e disputa concorrente
recebem conflito. Falha de auditoria desfaz toda a decisão. Rejeição conserva o
BillingEvent e não altera Subscription.

Auditoria humana usa user_id e actor_type=user:

- billing.manual_review_binding_approved;
- billing.manual_review_approved;
- billing.manual_review_rejected;
- ações de SubscriptionService e billing.event_verified quando há vigência.

Decided_by/decided_at ficam na revisão. Downgrade exige arquivamento explícito da
nova tabela antes de remover evidência ou decisões; não apaga histórico sozinho.

## Limites operacionais

KIWIFY_UNTRUSTED_INGRESS_ENABLED permanece false por padrão. Não houve deploy,
alteração de banco de produção, criação de checkout, Hotmart, validação presumida
de signature, enforcement de quotas ou bloqueio comercial automático.

Ainda faltam contrato oficial de período/vínculo recorrente e validação PostgreSQL
real. Eventos anteriores à persistência de evidência não são aprovados a partir
de um código de erro antigo; precisam de nova consulta oficial. Sem intenção
interna concluída e mapping, não há aprovação. A fila não cria essas associações
por dados de webhook. Revisões sem tenant confiável permanecem em quarentena,
fora da visualização dos administradores de tenants.

## Validação executada

- Backend completo reexecutado antes do PR: 475 passed, 513 warnings,
  71,48 segundos.
- Frontend: npm test aprovado; execução direta dos cinco arquivos confirmou
  26 testes, incluindo quatro novos de RBAC visual, decisão e renderização sanitizada.
- Build Next.js de produção: aprovado com checagem de tipos. Houve warning
  não bloqueante da otimização de uma fonte externa e do Browserslist existente.
- OpenAPI critical contracts: aprovado depois da adição intencional dos dois
  schemas; nenhum schema anterior mudou.
- Alembic: head único 20261007_02_billing_review. Testes cobrem
  upgrade/downgrade/re-upgrade SQLite, schema parity, proteção de histórico e
  geração de SQL PostgreSQL. Banco PostgreSQL real permanece pendente.
- git diff --check e whitespace de todos os arquivos novos: aprovados.

Casos incluem aprovação com vigência, aprovação apenas do vínculo, concorrência,
dupla aprovação, rejeição, RBAC, isolamento, mapping/tenant/evidência ausentes,
auditoria com rollback, renovação de evidência antiga, reconsulta inconclusiva,
datas não confiáveis do webhook, ausência de exposição de PII e futura ativação
da mesma assinatura. Testes usam apenas dados sintéticos, mocks e bancos
temporários. Validações executadas antes da abertura do Draft PR.
