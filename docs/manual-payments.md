# Recebimentos manuais da loja

Esta etapa permite registrar a conferência de dinheiro, Pix direto e cartão com a loja no Financeiro (`/finance`). Não cobra cartões, não consulta o banco, não faz Pix, split ou repasse e não substitui a conciliação do restaurante.

## Operação

1. Filtrar o período e a situação dos pagamentos em **Recebimentos da loja**.
2. Conferir que o dinheiro foi efetivamente recebido (inclusive no aplicativo bancário ou comprovante da adquirente).
3. Escolher **Confirmar pagamento**, revisar pedido/método/valor e aceitar **Sim, recebi o pagamento**.
4. Conferir a lista de recebidos, data, responsável e movimento financeiro.

Proprietário (`owner`), administrador (`admin`) e caixa (`cashier`) podem listar e confirmar os recebimentos do próprio tenant. Outros perfis não podem acessar os endpoints. Os IDs internos do pedido/pagamento são utilizados na requisição; o número diário é apresentado na tela junto à data para evitar confusão entre dias.

Preparo/entrega e pagamento são independentes: um pedido entregue pode continuar com pagamento pendente. A confirmação não muda o status operacional do pedido. Pedidos cancelados não podem ser confirmados manualmente.

## Cancelamento de pagamento pendente

Na situação **Pendente**, use **Cancelar pagamento**. Informe um motivo de 5 a 500 caracteres e confirme. O registro muda para cancelado sem gerar entrada ou saída de caixa. O pedido operacional não é cancelado por essa ação. Para um pedido já cancelado, seu pagamento pendente ainda pode ser cancelado.

## Registro de devolução manual

Na situação **Recebido**, use **Registrar devolução** somente depois de efetivamente devolver o valor integral ao cliente por fora do sistema. Informe o motivo e marque a confirmação de devolução. A ação registra uma saída financeira pelo valor integral do pagamento e preserva a data do recebimento original.

Não faz Pix, não aciona adquirente/processador, não devolve taxas, não cancela o pedido e não repõe ingredientes em estoque. O alimento pode já ter sido consumido; eventuais ajustes físicos de estoque devem seguir a operação de estoque. Devoluções parciais não estão disponíveis nesta etapa.

Os filtros **Cancelado** e **Devolvido** mostram o histórico com motivo, data e responsável. Históricos antigos sem motivo não recebem um motivo inventado. Os quatro totais da seção são agrupados pela data de criação do pagamento; o resumo do caixa continua usando a data do movimento financeiro. Um pagamento devolvido deixa de compor o total da situação Recebido, mas sua entrada original permanece no caixa e a saída de devolução a compensa. Taxas permanecem como despesas.

## Garantias e compatibilidade

- Reutiliza `POST /api/orders/{order_id}/payments/{payment_id}/status`, agora com transições restritas e auditoria transacional. Valor, método, tenant e responsável vêm dos registros/da sessão, sem alteração pelo payload da confirmação.
- Bloqueia o pedido com `FOR UPDATE`, compartilhando a disciplina de lock da criação de intents nativos; transição financeira também usa compare-and-set. Confirmações simultâneas/repetidas não lançam venda, taxa, estoque ou auditoria em duplicidade.
- Criação administrativa de pagamentos também bloqueia o pedido e não permite alocar valores acima do total somando pagamentos pendentes e recebidos. Confirme o registro pendente existente em vez de criar outro.
- Pagamentos identificados como nativos ou pedidos com intent nativo não podem ser registrados/alterados por essa ação manual. Não há fallback para pagamento manual de uma cobrança online.
- Transições permitidas: `pending -> paid|canceled`, `paid -> refunded`. Repetir o status atual é um no-op; não é permitido reabrir cancelados/estornados, devolver pago para pendente nem estornar algo não recebido.
- Auditoria `confirm_manual_payment` inclui usuário, tenant, pedido, valor, método e transição. Falha de auditoria/estoque/lançamento desfaz a transação inteira.
- A API exige motivo para cancelamento/devolução, inclusive sem uso da interface. Auditorias `cancel_manual_payment` e `refund_manual_payment` preservam o primeiro motivo em repetições da operação. O caminho antigo `paid -> canceled` agora é bloqueado: pagamentos recebidos devem ser tratados como devolução, nunca como cancelamento de pendência.
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
6. Em outro pagamento pendente, cancelar com motivo: zero efeito no caixa, motivo/responsável no histórico.
7. Em um pagamento recebido de teste, simular a devolução operacional e registrar a devolução integral: uma saída pelo valor integral e histórico auditável. Repetir a requisição não duplica a saída.
8. Tentar cancelar recebido, devolver pendente, reenviar sem motivo, agir em outro tenant e usar pagamento nativo: bloqueados.

Testes: `tests/test_manual_payments.py` e `tests/test_manual_payment_adjustments.py`; `tests/test_manual_payments_postgresql.py` usa exclusivamente o banco descartável local já protegido pelo fixture PostgreSQL. O CI executa concorrência real. Navegador com APIs de fixture: `MANUAL_PAYMENTS_TEST_BASE_URL=http://127.0.0.1:3000 npm run test:manual-payments:browser` e `npm run test:manual-adjustments:browser` (Chromium e puppeteer-core necessários).

## Próximas etapas

Conciliação de recebimentos e integração PSP em sandbox após acesso e aprovação do modelo; recebimentos online devem depender de confirmação confiável do provedor e nunca deste botão manual.
