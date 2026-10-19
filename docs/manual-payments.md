# Recebimentos manuais da loja

Esta etapa permite registrar a conferência de dinheiro, Pix direto e cartão com a loja no Financeiro (`/finance`). Não cobra cartões, não consulta o banco, não faz Pix, split ou repasse e não substitui a conciliação do restaurante.

## Operação

1. Filtrar o período e a situação dos pagamentos em **Recebimentos da loja**.
2. Conferir que o dinheiro foi efetivamente recebido (inclusive no aplicativo bancário ou comprovante da adquirente).
3. Escolher **Confirmar pagamento**, revisar pedido/método/valor e aceitar **Sim, recebi o pagamento**.
4. Conferir a lista de recebidos, data, responsável e movimento financeiro.

Proprietário (`owner`), administrador (`admin`) e caixa (`cashier`) podem listar e confirmar os recebimentos do próprio tenant. Outros perfis não podem acessar os endpoints. Os IDs internos do pedido/pagamento são utilizados na requisição; o número diário é apresentado na tela junto à data para evitar confusão entre dias.

Preparo/entrega e pagamento são independentes: um pedido entregue pode continuar com pagamento pendente. A confirmação não muda o status operacional do pedido. Pedidos cancelados não podem ser confirmados manualmente.

## Garantias e compatibilidade

- Reutiliza `POST /api/orders/{order_id}/payments/{payment_id}/status`, agora com transições restritas e auditoria transacional. Valor, método, tenant e responsável vêm dos registros/da sessão, sem alteração pelo payload da confirmação.
- Bloqueia o pedido com `FOR UPDATE`, compartilhando a disciplina de lock da criação de intents nativos; transição financeira também usa compare-and-set. Confirmações simultâneas/repetidas não lançam venda, taxa, estoque ou auditoria em duplicidade.
- Criação administrativa de pagamentos também bloqueia o pedido e não permite alocar valores acima do total somando pagamentos pendentes e recebidos. Confirme o registro pendente existente em vez de criar outro.
- Pagamentos identificados como nativos ou pedidos com intent nativo não podem ser registrados/alterados por essa ação manual. Não há fallback para pagamento manual de uma cobrança online.
- Transições permitidas: `pending -> paid|canceled`, `paid -> refunded|canceled`. Repetir o status atual é um no-op; não é permitido reabrir cancelados/estornados, devolver pago para pendente nem estornar algo não recebido.
- Auditoria `confirm_manual_payment` inclui usuário, tenant, pedido, valor, método e transição. Falha de auditoria/estoque/lançamento desfaz a transação inteira.
- O endpoint legado de status continua permitindo registrar cancelamento/estorno contábil de pagamentos manuais, com auditoria e saída única. Não envia dinheiro ao cliente e não estorna taxas já cobradas; não foi adicionada interface de estorno nesta etapa.
- Confirmação usa a baixa de estoque já existente no financeiro. Estoque não é novamente debitado para o mesmo pedido quando já há saída de venda.
- O resumo do caixa usa a data do movimento; a lista de recebimentos e seus totais usam a data de criação do pagamento. Os valores são explicitamente separados na interface.
- Pagamentos históricos já marcados `paid` permanecem como estavam. Sem auditoria de confirmação não exibem um responsável inventado.
- O piloto de checkout (#812) continua controlado pelas mesmas variáveis. Fora dele, a criação automática antiga de pagamentos recebidos permanece; não houve migração retroativa.

## Deploy e validação

Sem migration ou variável nova. Publicar backend antes do frontend. Não realizar deploy em produção como parte deste PR.

Em staging, com o piloto de checkout configurado para a loja de teste:

1. Criar pedido manual; verificar `pending` e `paid_at = null`.
2. Abrir Financeiro e confirmar somente após recebimento simulado na operação de teste.
3. Conferir `paid`, `paid_at`, responsável, uma entrada de venda e nenhuma mudança de preparo/entrega.
4. Repetir a requisição: não deve duplicar lançamentos.
5. Testar pedido cancelado e perfil sem permissão: confirmação bloqueada.

Testes: `tests/test_manual_payments.py`; `tests/test_manual_payments_postgresql.py` usa exclusivamente o banco descartável local já protegido pelo fixture PostgreSQL. O CI executa concorrência real. Navegador com APIs de fixture: `MANUAL_PAYMENTS_TEST_BASE_URL=http://127.0.0.1:3000 npm run test:manual-payments:browser` (Chromium e puppeteer-core necessários).

## Próximas etapas

Interface de cancelamentos/estornos manuais com motivo e conciliação; integração PSP em sandbox após acesso e aprovação do modelo; recebimentos online devem depender de confirmação confiável do provedor e nunca deste botão manual.
