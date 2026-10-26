# Kiwify: ingestão em quarentena e verificação secundária

## Contrato oficial consultado antes da implementação

Fontes oficiais acessíveis nesta etapa:

- [Índice da API](https://docs.kiwify.com.br/llms.txt).
- [Informações gerais](https://docs.kiwify.com.br/api-reference/general).
- [Gerar token OAuth](https://docs.kiwify.com.br/api-reference/auth/oauth).
- [Consultar venda](https://docs.kiwify.com.br/api-reference/sales/single).
- [Listar vendas](https://docs.kiwify.com.br/api-reference/sales/list).

Consulta de venda confirmada: `GET https://public-api.kiwify.com/v1/sales/{id}`;
`id` é o `order_id`. OAuth usa POST `/v1/oauth/token`, formulário com
`client_id` e `client_secret`; resposta contém `access_token`, `token_type`,
`expires_in` e `scope`. A consulta usa `Authorization: Bearer ...` e
`x-kiwify-account-id`; escopo necessário: `sales`. Cache de token usa o
`expires_in` retornado, sem presumir expiração fixa. O limite oficial é de
100 chamadas/minuto por usuário. API Key deve permitir leitura de vendas.

A resposta documenta `id`, `product.id`, `status` e datas de venda. O catálogo
de filtros lista paid, approved, pending, refunded, refused e outros status de
venda; eles não são status canônicos de assinatura.

**NÃO CONFIRMADOS:** endpoint para consultar assinatura recorrente, vínculo
autoritativo `order_id -> subscription_id`, `Subscription.plan.id` e período de
acesso obtidos via API. O índice não apresenta consulta de assinatura recorrente
e o schema de consulta de venda não declara esse vínculo. `scheduled_installment`
representa Parcelado Kiwify, não equivale à assinatura recorrente. Webhook
subscription da API bancária representa configuração de notificações, não uma
assinatura comercial. Não usar esses endpoints como substitutos.

Consequência: uma venda paga confirmada **não ativa assinatura**. A consulta
atual pode rejeitar divergência de venda/produto; respostas correspondentes vão
para `manual_review` com `sale_confirmed_subscription_unconfirmed`. Mesmo que
uma resposta inclua campos adicionais de assinatura, o adapter não os trata
como contrato oficial. Não é possível prometer operação quase automática com
as evidências oficiais disponíveis.

## Ingestão e minimização

`POST /api/webhooks/billing/kiwify`, sem sessão, recebe apenas candidatos não
autenticados. Desabilitado por padrão. `signature` não é validada, usada como
credencial ou persistida. O webhook nunca chama SubscriptionService.

Corpo máximo: 64 KiB; exige `application/json`, admite charset. Rejeita JSON
inválido, chaves duplicadas, NaN, referências inválidas e divergência entre
`subscription_id` e `Subscription.id`. IDs externos são limitados ao formato
UUID observado; novos formatos requerem contrato e revisão. Eventos sem
`order_id` não recebem identidade inventada e são rejeitados.

Persiste somente IDs de pedido, assinatura, produto, plano recorrente, tipo de
evento, timestamps ISO com timezone confirmado e hash. Datas sem timezone não
são convertidas para UTC por suposição. Customer, dados de comissão/pagamento,
tracking, nomes, contatos e credenciais são descartados. O hash canônico considera
o payload completo para detectar mudanças, mas o texto original não é guardado.

Identidade sintética provisória: SHA-256 do array JSON compacto
`["kiwify", order_id, webhook_event_type]`. Tipos distintos permanecem distintos.
Reenviar o mesmo ID com corpo diferente produz conflito, sem sobrescrever ou
aplicar efeitos. Duplicados usam a constraint existente e ON CONFLICT.
O commit termina antes da resposta 202; falha de banco retorna 503.

Respostas: 202 novo/duplicado; 409 conflito; 422 payload inválido ou sem
identidade suportada; 413 tamanho; 415 mídia; 429 rate limit; 404 integração
desabilitada. Receber 202 não significa confirmação comercial.

Tenant de query/header/cookie é ignorado. Middleware não resolve tenant nessa
rota e gera request ID próprio. Logs da aplicação redigem signature em URLs;
nenhum corpo ou resposta da API é logado pelo código de billing. Access logs
externos do Railway/proxy exigem revisão de redaction antes de habilitar tráfego.
O limitador de ingestão permite 60 requests/minuto por processo, com chave fixa
que não cresce conforme entradas do remetente. Em múltiplas réplicas, o teto é
multiplicado; configurar proteção compartilhada no edge para exposição pública.
Uma ocorrência forjada pode ocupar uma identidade provisória e causar conflito
com o envio real; isso exige revisão manual, nunca liberação de acesso.

## Estado durável e aplicação atômica

Migration `20261007_01_billing_verification` adiciona a BillingEvent:
`verification_status`, tentativas, próxima tentativa, lease/token de posse,
erro seguro e `verified_at`. Estados: pending, verified, rejected, retrying,
manual_review. São separados de `processing_status`; rejeição/revisão não
significam que o domínio foi processado.

`KiwifyVerificationService` usa claim atômico e lease de dois minutos. Não mantém
transação aberta durante HTTP; a finalização é protegida pelo token da lease,
impedindo aplicação por worker antigo. Queda permite recuperação após expiração.
Falhas temporárias, timeout, 404/408/429/5xx entram em retry com backoff de 30s
até 1h; após oito falhas vão para revisão manual. Ausência/erro de credencial,
scope ou resposta incompleta exige revisão. Não há rota para aprovação manual
ou operação administrativa que aceite uma alegação do cliente como evidência.
Espera pelo orçamento local agenda nova tentativa sem consumir o limite de
oito falhas de provider; não descartar eventos apenas por fila concorrente.

A tabela `billing_provider_budgets` serializa o orçamento HTTP entre réplicas:
uma reserva a cada três segundos para no máximo duas chamadas (OAuth + venda),
globalmente para Kiwify neste deployment. Isso deixa margem sob o limite oficial.
Outros sistemas que compartilham a mesma credencial também precisam respeitar
esse limite. URLs são fixas, sem redirects, com timeout, resposta limitada e
erros genéricos. Nenhuma chamada de cobrança/cancelamento/reembolso é feita.

O contrato interno `VerifiedSubscription` está preparado para uma futura fonte
autenticada com contrato suficiente. **KiwifySalesAPI nunca o produz hoje.**
O caminho verificado é testado com fonte sintética injetada, não habilitado por
campos do webhook. Exige conta/ambiente, venda, assinatura, produto e plano
correspondentes, evidência recente (até cinco minutos), mapping ativo e um único
BillingCheckoutIntent COMPLETED, com referência externa vinculada internamente.
Não completar intent a partir do webhook não autenticado. Não inferir tenant
por PII, slug ou valor; vínculo pré-existente divergente exige revisão.

Somente depois dessa comprovação, SubscriptionService cria/ativa/renova ou marca
past_due, e audit log/evento/assinatura são persistidos na mesma transação. Novo
método `renew_subscription` mantém validação, versão otimista e auditoria central.
Falhas de correlação, mapping, períodos ou transição revertem todas as alterações
e deixam o evento em revisão. Cancelamento exige política comercial confirmada;
não presumir cancelamento imediato. Grace period, quotas e bloqueios não foram
introduzidos. Tenants sem assinatura continuam com `legacy_no_subscription`.

## Job de verificação e reconciliação

Executar após migration, em um serviço cron do Railway com raiz no backend:

```sh
python scripts/run_kiwify_verification.py
```

Configurar cron a cada minuto (`* * * * *`). O comando termina após cada ciclo;
o agendamento Railway deve ser configurado pelo operador. Nada foi implantado
ou habilitado em produção nesta tarefa. Processa até 50 candidatos por ciclo,
respeitando as datas de retry e o orçamento compartilhado.

A cada hora, cria candidatos idempotentes de reconciliação para assinaturas
internas Kiwify active/past_due, paginando por ID. Nenhum outro provider ou tenant
legacy é alterado. Referência externa ausente/inválida é ignorada, sem inventar ID.
Conta/ambiente do job são contexto de consulta, não prova de propriedade da
assinatura. Esses candidatos não têm sale_id autoritativo e, sem consulta
documentada de assinatura, terminam em manual_review. Não completar escopo ou
período por suposição. Política de retenção/arquivamento dessa fila deve ser
definida antes de operação continuada; nenhum recibo é apagado automaticamente.

Configuração exclusivamente de ambiente:

- `KIWIFY_UNTRUSTED_INGRESS_ENABLED=true`: opt-in para este fluxo em quarentena;
- `KIWIFY_PROVIDER_ACCOUNT_ID`: conta interna configurada para o header oficial;
- `KIWIFY_ENVIRONMENT`: sandbox ou production como partição interna do Fomizero;
- `KIWIFY_API_CLIENT_ID`, `KIWIFY_API_CLIENT_SECRET`: credenciais da API oficial.

A partição sandbox não comprova sandbox no provider: a URL oficial é a mesma.
Usar somente credenciais e conta autorizadas para o ambiente escolhido.
O Token de webhook não é credencial OAuth. Sem credenciais API, revisão manual.
Startup valida escopo ao habilitar e credenciais parcialmente configuradas;
nunca imprime valores. Desabilitado mantém comportamento dos tenants existentes.

## Migração, limites e próxima etapa

Upgrade não altera tabelas operacionais nem atribui planos a tenants. Eventos
anteriores mantêm schema v1 e não são processados pelo novo worker. Downgrade
exige arquivar recibos Kiwify schema v2 antes de remover a fronteira de confiança;
não apagar histórico automaticamente. PostgreSQL real e credenciais reais ainda
não foram usados nesta tarefa.

Mesmo com signature oficialmente validada no futuro, a verificação secundária,
leases, orçamento e reconciliação permanecem. Antes de habilitar transições reais,
obter contrato oficial suficiente de assinatura/vínculo/períodos, implementar a
fonte completa, confirmar política de cancelamento e validar correlação interna.
Não criar rotas ou nomes de campos externos por hipótese.

## Validação executada

- Suíte backend completa reexecutada antes do PR: 439 testes passaram
  (418 warnings), 46,90 segundos, incluindo espera sem esgotar tentativas.
- Testes de migrations reexecutados: 3 passaram (2 warnings), 2,01 segundos.
- Upgrade/downgrade/re-upgrade SQLite, preservação de recibos antigos e bloqueio
  de downgrade com novos recibos: aprovados.
- Geração SQL PostgreSQL de upgrade/downgrade: aprovada; banco PostgreSQL real
  permanece pendente.
- OpenAPI critical contracts: inalterados, check aprovado.
- Head Alembic único: `20261007_01_billing_verification`.
- Frontend smoke existente: aprovado; executa somente echo, não navegação real.
- Whitespace: aprovado, incluindo arquivos novos não rastreados.

Testes usam somente dados sintéticos, API mockada e bancos temporários. Não
houve chamada com credenciais reais, modificação de produção ou deploy.
