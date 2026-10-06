# Kiwify — Fase 3A: contrato de ingestão

Consulta realizada em 2026-10-06. **Implementação de ingestão pendente de confirmação
do contrato de autenticação.** A identidade sintética para eventos associados
a uma cobrança foi autorizada como decisão provisória da Fase 3A. Este documento
não declara o endpoint ou o adapter implementados.

Diagnóstico atualizado em 2026-10-06 com evidência de uma requisição HTTP e de
payloads reais de teste, relatados pelo usuário. A confirmação abaixo vale para
essas capturas; não estabelece garantias gerais do provedor. Não foram recebidos
ou armazenados o valor de `signature` nem o payload com dados pessoais.

## Fontes oficiais

- [Como funcionam os webhooks?](https://ajuda.kiwify.com.br/pt-br/article/como-funcionam-os-webhooks-2ydtgl/)
- [Webhooks (pt-br)](https://kiwify.notion.site/Webhooks-pt-br-c77eb84be10c42e6bb97cd391bca9dce),
  documentação vinculada pela central de ajuda. A abertura direta retornou 404;
  o conteúdo indexado pelo mecanismo de pesquisa foi consultado. Confirmar com
  documentação acessível ou captura real antes de habilitar recebimento.
- [Como criar um produto de assinatura](https://ajuda.kiwify.com.br/pt-br/article/como-criar-um-produto-de-assinatura-9crmrj/)
- [Como integrar com a Zapier?](https://ajuda.kiwify.com.br/pt-br/article/como-integrar-com-a-zapier-1o77sks/)

As referências em `docs.kiwify.com.br` encontradas na pesquisa descrevem também
webhooks financeiros da `conta-public-api.kiwify.com`, com eventos de depósitos e
saques. Não foi confirmada a aplicabilidade desses mecanismos de autenticação aos
webhooks de vendas de produtos. Não importar seus headers, chaves ou assinaturas
para o adapter de billing de produtos.

## Contrato confirmado e limites da evidência

O envio é POST com JSON. A configuração permite selecionar produto e eventos.
O painel permite testar e consultar requisição/resposta nos logs. Falhas podem
ser reenviadas manualmente, inclusive por seleção de registros.

O conteúdo técnico indexado informa confirmação HTTP 2xx, até cinco reenvios em
caso de falha, redirecionamento 3xx tratado como falha e espera de até 40 segundos.
Intervalos, backoff e igualdade do payload/identificadores entre tentativas são
**NÃO CONFIRMADOS**. A existência do botão de reenvio não prova estabilidade de
um identificador ou imutabilidade do corpo.

| Conceito | Campo encontrado no exemplo oficial | Limitação |
| --- | --- | --- |
| Tipo do evento | `webhook_event_type` | Exemplo: `order_approved`; catálogo completo NÃO CONFIRMADO |
| Venda/pedido | `order_id`, `order_ref` | Não são apresentados como ID exclusivo de evento |
| Conta/loja | `store_id` | Correspondência com conta configurada no Fomizero NÃO CONFIRMADA |
| Assinatura | `subscription_id`, `Subscription.id` | Presentes em vendas recorrentes; política para divergência NÃO CONFIRMADA |
| Cliente | `Customer` | ID estável de cliente NÃO CONFIRMADO; não usar email/CPF/telefone como ID |
| Produto | `Product.product_id` | Identificador externo; não inferir plano pelo nome |
| Oferta | `Product.product_offer_id` | Apenas quando a venda usa oferta |
| Plano externo recorrente | `Subscription.plan.id` | Não presumir equivalência com ID de oferta ou Plan interno |
| Datas da venda | `created_at`, `updated_at`, `approved_date`, `refunded_at` | Exemplo contém datas sem timezone; timezone e timestamp do evento NÃO CONFIRMADOS |
| Datas recorrentes | `Subscription.start_date`, `Subscription.next_payment`, `Subscription.customer_access.access_until` | Exemplos ISO com UTC; não são necessariamente instante de ocorrência do evento |
| Ambiente | Nenhum campo confirmado | Origem oficial sandbox/produção NÃO CONFIRMADA |
| Referência de checkout Fomizero | Nenhum campo confirmado | Não interpretar tracking como correlação confiável |

`Subscription`, cobranças e `subscription_id` são opcionais, associados a vendas
recorrentes. `Customer` pode ser nulo em eventos de afiliados sem acesso aos dados
do comprador. Não exigir PII para receber um evento.

## Evidência real de teste — CONFIRMADA na captura relatada

A requisição apresentou `Content-Type: application/json` e query parameter
`signature`, cujo valor deve ser tratado como secreto. Também foram observados:

- `user-agent: axios/0.23.0`;
- `accept: application/json, text/plain, */*`;
- `traceparent`.

Não foi observado header específico de autenticação da Kiwify nessa requisição.
Isso não prova ausência de mecanismos de autenticação em todas as requisições.
User-agent, accept e traceparent não autenticam o remetente.

Campos cuja presença foi confirmada no payload de teste:

- `order_id`, `order_ref`, `order_status`, `product_type`, `payment_method`;
- `store_id`, `payment_merchant_id`;
- `created_at`, `updated_at`, `approved_date`, `refunded_at`;
- `webhook_event_type`;
- `Product.product_id`, `Product.product_name`;
- `Customer`, `Commissions`, `TrackingParameters`.

O valor observado foi `webhook_event_type = billet_created`, com
`product_type = membership`. A presença desses campos não confirma valores
nulos/formatos de todas as datas, nem um instante canônico de ocorrência.
`membership` não comprova uma assinatura recorrente ou seu vínculo interno.

Não havia `event_id` explícito nem `subscription_id` explícito nesse evento.
Essa ausência é confirmada para a captura, não para todos os eventos Kiwify.
Não inferir assinatura por email, telefone, nome ou `order_id`.

`Product.product_id` é uma referência externa confirmada e candidata ao lookup
de `BillingOfferMapping`. A captura inicial não confirmou um ID de oferta;
as evidências recorrentes posteriores fundamentam a normalização abaixo.
A equivalência entre conta e `store_id` e um mapping existente continuam não
confirmados. Não associar automaticamente
produto a plano; `Product.product_name` não é chave de correlação.

### Evidências adicionais de assinatura e normalização autorizada

O usuário confirmou capturas reais de teste de `billet_created`, `order_approved`
e `subscription_renewed`. Nos payloads recorrentes foram confirmados
`subscription_id`, `Subscription.id`, `Subscription.plan.id`,
`Subscription.status`, `Subscription.start_date`, `Subscription.next_payment`,
`Subscription.plan.frequency` e cobranças concluídas e futuras.
Nas capturas recorrentes, `subscription_id == Subscription.id`.
Não extrapolar essa igualdade para payloads ainda não observados; divergências
futuras deverão ser tratadas explicitamente, sem escolher um ID silenciosamente.

| Campo interno | Fonte confirmada / decisão para a Fase 3A |
| --- | --- |
| `external_sale_id` | `order_id` |
| `external_subscription_id` | `subscription_id`, quando presente |
| `external_product_id` | `Product.product_id` |
| `external_offer_id` | `Subscription.plan.id`, quando presente |
| `event_type` | `webhook_event_type` |

O uso do plano recorrente como `external_offer_id` é a convenção interna
explicitamente autorizada para esta integração. Não afirma que
`Subscription.plan.id` e `Product.product_offer_id` sejam o mesmo identificador.
Não substituir um pelo outro automaticamente. O lookup futuro usará produto e
plano recorrente no escopo configurado, apenas como candidato de correlação.
Não inferir status interno a partir de `Subscription.status`, nem plano pelo nome.

## Autenticação — semântica NÃO CONFIRMADA

Uma captura do painel enviada pelo usuário confirma a existência de um campo
`Token` na configuração do webhook de produtos. Seu valor não foi transcrito,
armazenado neste documento ou usado em código. A relação entre esse Token e o
query parameter `signature` ainda não foi confirmada por comparação local.

Não foi encontrada especificação oficial aplicável a vendas de produtos que
confirme header de autenticação, token/secret configurável, assinatura
criptográfica, algoritmo ou formato da mensagem assinada. O JSON documentado
também não apresenta credencial de autenticação. A evidência real agora confirma
Content-Type e os headers listados acima, além do parâmetro `signature` na URL.
A semântica desse parâmetro permanece **NÃO CONFIRMADA**: não se sabe se
corresponde ao token configurado pela Kiwify, a uma assinatura criptográfica ou
a outro mecanismo. Não implementar verificação antes dessa confirmação.

Isso não permite concluir que o provedor não tem autenticação; significa que a
evidência consultada não a especifica. Não implementar HMAC, Bearer,
`X-KIWIFY-SIGNATURE`, verificação presumida de `signature` ou validação por
formato do payload.
Não criar `KIWIFY_WEBHOOK_SECRET` nem outras configurações com semântica presumida.

É necessária confirmação da relação entre `signature` e a configuração do
webhook, por documentação aplicável ou evidência controlada, sem compartilhar
valores secretos ou dados pessoais.
Sem essa confirmação, não registrar endpoint público que grave eventos como
confiáveis. Não aceitar um evento apenas porque contém IDs ou `store_id`.

## Event ID e idempotência — decisão provisória autorizada

O exemplo não documenta `event_id` ou outro identificador exclusivo de evento.
`order_id` identifica a venda; usá-lo sozinho colidiria entre aprovação e reembolso.
Nenhum `event_id` explícito apareceu nas capturas relatadas. A interface de logs
permaneceu vazia após `Testar Webhook`, mostrando `Exibindo 1 de 0 páginas`, e
`Reenviar webhooks` ficou desabilitado. Portanto, os testes não forneceram um
mecanismo observável para reenviar a mesma ocorrência. Isso não comprova que
eventos de vendas reais não gerem logs; também não comprova estabilidade ou
imutabilidade do corpo em reenvios e retries.

Por decisão explícita do usuário, a Fase 3A adotará identidade sintética
determinística **somente para eventos associados a uma cobrança**, com `order_id`
e `webhook_event_type` válidos. Representação equivalente à fórmula solicitada:

```text
identity_input = UTF-8(JSON compacto do array ["kiwify", order_id, webhook_event_type])
provider_event_id = SHA-256(identity_input).hexdigest()
```

A codificação do array terá `ensure_ascii=False` e separadores `(',', ':')`,
sem espaços adicionados nem normalização dos IDs. O array evita ambiguidade de
concatenação. A mesma combinação sempre gera a mesma identidade, sem PII e sem
usar o hash do payload como identidade. Não usar apenas `order_id` ou apenas
`subscription_id`. Tipo diferente da mesma venda gera identidade distinta; por
exemplo, `order_approved` e `refund` devem ser distintos. `refund` é um exemplo
ilustrativo fornecido pelo usuário, não um nome técnico confirmado por captura.

Eventos sem associação confirmada a cobrança não devem receber identidade
inventada ou emprestada de assinatura/pedido. Não aplicar essa fórmula
indiscriminadamente a cancelamento, atraso ou tipos ainda não observados.

Persistir separadamente `payload_hash` do JSON canônico para detectar a anomalia
de mesma identidade com payload diferente; tratar como conflito, sem sobrescrever
o evento ou duplicar efeitos. A identidade composta pode reunir ocorrências
distintas do mesmo tipo para o mesmo pedido. Isso é um risco conhecido, não uma
garantia oficial de unicidade. Reavaliar a estratégia quando houver um reenvio
real observável e comparar também eventos diferentes da mesma venda/assinatura.

A inbox existente possui constraint única em
`(provider, provider_account_id, environment, provider_event_id)`, inserção
`ON CONFLICT DO NOTHING` e comparação de hash do JSON canônico para identificar
o mesmo ID com conteúdo diferente. Esses mecanismos não substituem a definição
de uma identidade externa correta. Após confirmar a autenticação, reutilizar
essa inbox com a estratégia provisória autorizada;
não duplicá-la nem reconhecer sucesso antes do commit durável.

## Eventos de assinatura

A captura do painel confirma opções com os rótulos: Boleto gerado, Pix gerado,
Carrinho abandonado, Compra recusada, Compra aprovada, Reembolso, Chargeback,
Assinatura cancelada, Assinatura atrasada e Assinatura renovada. Esses rótulos
confirmam as categorias disponíveis na interface, não os valores técnicos de
`webhook_event_type`, campos ou garantias de entrega de cada categoria.

Os nomes técnicos confirmados nas capturas são `billet_created`, `order_approved`
e `subscription_renewed`. Nenhum deles confirma o contrato de atraso ou cancelamento.
A ajuda de Zapier
confirma categorias de venda aprovada, reembolso, chargeback, renovação e
cancelamento de assinatura. Isso não confirma os nomes de `webhook_event_type`
no transporte direto de webhooks.

Nomes técnicos de pagamento recusado, atraso, cancelamento,
reembolso, chargeback e fim de assinatura são **NÃO CONFIRMADOS**. Não inventar
enums ou converter esses eventos em status internos.

A documentação de produtos recorrentes confirma retentativas de cobrança por
cinco dias quando o cartão é recusado na renovação. Isso é diferente de retry
de entrega do webhook e não define grace period do Fomizero.

## Implementação prevista após confirmação

Endpoint solicitado: `POST /api/webhooks/billing/kiwify`, sem sessão de usuário
ou dependência de assinatura ativa. Adapter solicitado: `KiwifyBillingProvider`,
com verificação do corpo bruto, identificação, normalização e extração de
referências. **Ambos ainda não foram criados.**

O fluxo deve validar tamanho, Content-Type e JSON, autenticar segundo contrato
confirmado, identificar o evento, minimizar os dados, persistir na inbox e
confirmar somente após commit. Deve terminar em `BillingEvent` com status
`pending`; não chamar `SubscriptionService`.

Contrato normalizado previsto: provider, identidade/tipo/instante do evento,
conta/ambiente, IDs externos de venda/assinatura/cliente/produto/oferta e hash.
Campos sem fonte confiável permanecerão nulos quando suportado; não preencher
timestamps ou IDs fictícios. Conta, ambiente e identidade são obrigatórios na
inbox e exigem uma origem explicitamente definida antes da ingestão.

O lookup de `BillingOfferMapping` deve usar somente produto/oferta e escopo
confirmado. Produzir apenas candidato de correlação, sem ativar assinatura.
Ausência de mapping não deve rejeitar um evento válido. `tenant_id`,
`subscription_id` e `checkout_intent_id` devem permanecer nulos sem correlação
interna confiável; nunca vincular por PII, slug ou valor.

Respostas a implementar e testar: sucesso para novo/duplicado após persistência;
erro genérico para autenticação inválida, JSON inválido, tipo incompatível,
tamanho excessivo, identidade inválida/conflitante e indisponibilidade de banco.
Eventos desconhecidos autenticados poderão permanecer pending se a identidade
for válida. Status HTTP exatos serão definidos junto da implementação.

## Segurança e revisão da base

`BillingEvent.raw_payload` guarda atualmente somente recibo redigido, hash e
versão do schema; não guarda o corpo original. Preservar essa minimização e,
se necessário, ampliar com projeção permitida de referências externas, sem
PII, credenciais, URLs de acesso ou dados de pagamento. Retenção dessa projeção
precisa ser definida antes de operação em produção. Não criar criptografia
caseira ou exposição administrativa do corpo original.

O middleware de tenant atualmente consulta query, cookie e headers. A futura
rota deve evitar resolução operacional de tenant e nunca tomar essas entradas
como correlação de billing. O middleware de observabilidade registra path e
identificadores de requisição/tenant, sem corpo ou headers de autenticação.
Para a nova rota, revisar também identificadores controlados pelo remetente e
access logs do servidor/proxy antes de escolher o transporte de credenciais.

A evidência de `signature` em query torna obrigatória a proposta de remover seu
valor de URLs registradas em logs, traces, métricas, relatórios de erro e access
logs de servidor/proxy. Nunca registrar a URL completa com query, headers
completos ou o corpo completo; não expor `signature` em respostas/exceptions.
Essa é uma proposta de segurança para a futura implementação, não uma declaração
de redaction já implementada.

O payload real contém nome, email, telefone, documento, IP, endereço, dados de
boleto e informações de comissão. Excluir esses dados da projeção persistida e
dos logs. Descartar por padrão `Customer`, `Commissions`, dados de boleto e
`TrackingParameters`; não preservar objetos inteiros para obter um ID.
`Product.product_name` também é desnecessário à correlação por ID. Permitir na
futura projeção somente referências externas confirmadas e necessárias, tipo de
evento, versão e hash; timestamps apenas após confirmar sua semântica. Não
persistir `signature`, URLs de acesso ou um payload completo como fixture de teste.

Nenhum comportamento de Subscription, entitlements ou tenants foi alterado.
`legacy_no_subscription` permanece conforme a Fase 1. Nenhum banco de produção
foi alterado e nenhuma migration foi criada.

## Validação e próximos passos

Sem um contrato confirmado, não há testes de webhook autenticado ou ingestão
Kiwify implementados. Validação executada da base existente em 2026-10-06:

- Backend completo: `404 passed`, 354 warnings, 35,21 segundos.
- OpenAPI critical contracts: inalterados, check aprovado.
- Alembic single head: `20261006_07_billing_audit`, check aprovado.
- `npm run test:smoke`: aprovado; o script existente executa apenas `echo`,
  sem exercício real de telas ou navegação.
- `git diff --check`: aprovado. Como o documento ainda é untracked, seu
  whitespace também foi verificado separadamente.

Não considerar esses resultados como validação de uma integração ainda ausente.

Nesta atualização, somente documentação foi alterada e o whitespace foi
verificado novamente. A suíte acima foi executada no diagnóstico anterior,
não repetida nem apresentada como teste de webhook real.

### Confirmações e capturas ainda necessárias

O requisito para iniciar código é confirmar, por comparação local ou evidência
aplicável, que `signature` corresponde ao Token configurado na Kiwify. Informar
somente o resultado da comparação, nunca os valores. Até lá, não implementar
comparação, endpoint ou adapter de ingestão.

Compra aprovada e renovação já foram capturadas em teste. Para ampliar o contrato,
capturar assinatura atrasada e cancelada. Quando logs de uma ocorrência real
estiverem disponíveis, comparar seu envio original com reenvio manual, mantendo
IDs fictícios consistentes na anonimização. Não condicionar a decisão sintética
provisória a um botão de reenvio indisponível nos testes; reavaliá-la com essa
evidência futura. Retries automáticos continuam exigindo evidência própria;
reenvio manual não prova contrato de retry.

Depois de confirmar autenticação, implementar e testar todo o
caminho de ingestão, incluindo concorrência, commit/falhas, logs sem dados
sensíveis e ausência de alterações de assinatura. Manter um único head Alembic;
evitar migrations se uma projeção sanitizada no recibo existente for suficiente.

A Fase 3B continua reservada para correlação confiável, processamento dos eventos,
transições auditáveis via SubscriptionService e política comercial de períodos
e grace. Não iniciá-la antes de concluir e revisar a Fase 3A.
