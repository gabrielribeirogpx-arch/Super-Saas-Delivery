# Roteiro de teste manual (WhatsApp)

## Fase 1 — Camada de gestão (order_items)

1. **Criar pedido via Swagger com modifiers**
   - Endpoint: `POST /api/orders/{tenant_id}`
   - Corpo com `modifiers` preenchidos em ao menos um item.
   - Esperado:
     - `orders.items_json` permanece no formato atual.
     - Registros criados em `order_items` com `modifiers_json`.
     - Ticket/PDF renderiza itens corretamente usando `order_items`.

2. **Criar pedido via WhatsApp com “com/extra/adicional”**
   - Fluxo natural do bot com adicionais reconhecidos.
   - Esperado:
     - `orders.items_json` preenchido.
     - Registros criados em `order_items`.
     - Ticket/PDF renderiza itens corretamente.

3. **Validar endpoint de itens**
   - Endpoint: `GET /api/orders/{order_id}/items`
   - Esperado:
     - Retorna lista de itens com `tenant_id`, `order_id`, `quantity`, `unit_price_cents`, `subtotal_cents` e `modifiers`.

## Admin de adicionais

0. **Rodar migração da coluna active**
   - Execute: `sqlite3 ./super_saas.db < migrations/manual_sqlite.sql`
   - Esperado:
     - Coluna `active` adicionada em `modifiers` antes de testar o admin.

## Modifiers naturais no WhatsApp

0. **Pedido sem gatilho de adicionais**
   - Mensagem: `quero picanha house`
   - Esperado:
     - Adiciona o item sem sugerir adicionais.

1. **Adicionar item com modifiers e outro item na mesma frase**
   - Mensagem: `1 picanha house com bacon e catupiry e 1 coca lata`
   - Esperado:
     - Dois itens adicionados ao carrinho.
     - Picanha House com bacon e catupiry (modifiers preenchidos com nome + preço).
     - Coca lata reconhecida por similaridade.

2. **Modifier inexistente**
   - Mensagem: `picanha house com abacaxi`
   - Esperado:
     - Não adiciona ao carrinho.
     - Resposta sugere os adicionais permitidos do item com preço, sem pedir número.

3. **Quantidade + modifier**
   - Mensagem: `2 x-burger com cheddar`
   - Esperado:
     - Adiciona 2x o item com o modifier cheddar.

4. **Item sem modifiers**
   - Mensagem: `coca lata`
   - Esperado:
     - Match forte com “Coca-cola lata” sem pedir número.

5. **Separar item base do trecho de adicionais**
   - Mensagem: `picanha house com bacon`
   - Esperado:
     - Usa apenas "picanha house" para localizar o item.
     - Bacon validado como adicional permitido.

6. **Item com adicionais inválidos + outro item**
   - Mensagem: `quero picanha house com abacaxi e uma coca lata`
   - Esperado:
     - Identifica Picanha House e detecta adicional inválido.
     - Resposta lista apenas os adicionais válidos do item.
     - Coca-cola lata ainda reconhecida como item separado.

7. **Ambiguidade real**
   - Mensagem: uma frase que gere duas opções muito próximas no cardápio.
   - Esperado:
     - Bot solicita confirmação (número ou nome), mantendo o fluxo atual.

## Fase 3.1 — Financeiro raiz

1. **Pedido via WhatsApp com forma de pagamento**
   - Fluxo normal do bot até finalizar o pedido informando `cartao`, `pix` ou `dinheiro`.
   - Esperado:
     - `POST /api/orders/{order_id}/payments` já tem 1 pagamento criado.
     - `GET /api/finance/cash/summary?tenant_id=1&from=YYYY-MM-DD&to=YYYY-MM-DD` mostra entrada `sale`.

2. **Criar pagamento manual via Swagger**
   - Endpoint: `POST /api/orders/{order_id}/payments`
   - Corpo: `{"method":"pix","amount_cents":1000,"fee_cents":50}`
   - Esperado:
     - `GET /api/orders/{order_id}/payments` lista o pagamento.
     - `GET /api/finance/cash/movements?tenant_id=1&from=...&to=...` lista `sale` e `fee`.

3. **Refund**
   - Endpoint: `POST /api/orders/{order_id}/payments/{payment_id}/status`
   - Corpo: `{"status":"refunded"}`
   - Esperado:
     - Movimento `refund` (saída) criado no caixa.

4. **Fee**
   - Criar pagamento com `fee_cents` > 0.
   - Esperado:
     - Movimento `fee` (saída) criado no caixa.

5. **Observação**
   - Se o payload de criação do pedido não tiver campo de pagamento, nenhum pagamento automático é criado.

## Fase 3.2 — Dashboard Admin

1. **Criar pedidos com itens e pagamentos**
   - Use o fluxo do WhatsApp ou `POST /api/orders/{tenant_id}` com `itens` e `forma_pagamento`.
   - Confirme que existe pelo menos um pedido pago (`POST /api/orders/{order_id}/payments`).

2. **Abrir o dashboard**
   - Acesse: `/admin/1/dashboard`.
   - Esperado: cards com valores, gráfico e tabelas preenchidas.

3. **Trocar período**
   - Clique em "Hoje", "7 dias" e "30 dias".
   - Preencha datas personalizadas e clique em "Aplicar".
   - Esperado: cards, gráfico, top itens e breakdown atualizam.

4. **Ver breakdown por forma de pagamento**
   - Confirme se os métodos (pix/cartão/dinheiro) aparecem com totais.

5. **Ver top itens e pedidos recentes**
   - Top itens deve mostrar nomes + quantidade + total.
   - Pedidos recentes listam status e forma de pagamento.

## Fase 4 — Estoque e margem

1. **Criar insumos**
   - Endpoint: `POST /api/inventory/items?tenant_id=1`
   - Criar dois itens: Bacon (un) e Cheddar (un) com custo e estoque inicial.
   - Esperado: itens aparecem na lista e estoque inicial registrado.

2. **Vincular ingredientes ao cardápio**
   - Endpoint: `POST /api/inventory/menu-items/{menu_item_id}/ingredients?tenant_id=1`
   - Vincular Bacon ao item "Picanha House" com quantidade 2.
   - Esperado: ingrediente listado no endpoint de ingredientes do item.

3. **Vincular ingredientes aos adicionais**
   - Endpoint: `POST /api/inventory/modifiers/{modifier_id}/ingredients?tenant_id=1`
   - Vincular Cheddar ao adicional "Cheddar Extra" com quantidade 1.
   - Esperado: ingrediente listado no endpoint de ingredientes do adicional.

4. **Criar pedido e confirmar pagamento**
   - Criar pedido com "Picanha House" + "Cheddar Extra".
   - Confirmar pagamento (`POST /api/orders/{order_id}/payments/{payment_id}/status` com `{"status":"paid"}`).
   - Esperado:
     - Movimentos `OUT` com `reason="sale"` vinculados ao `order_id`.
     - Estoque reduzido conforme quantidades configuradas.

5. **Validar dashboard**
   - Endpoint: `GET /api/dashboard/overview?tenant_id=1`
   - Esperado:
     - `cogs_cents` calculado.
     - `gross_profit_cents` = receita - COGS.
     - `low_stock_count` atualizado quando estoque fica abaixo do mínimo.

6. **Idempotência da baixa**
   - Repetir confirmação do pagamento.
   - Esperado: não gerar novas baixas de estoque para o mesmo pedido.
