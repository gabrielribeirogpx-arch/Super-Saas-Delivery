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

## Fase 5 — Relatórios completos + exportação

1. **Resumo financeiro**
   - Endpoint: `GET /api/reports/financial/summary?tenant_id=1&from=YYYY-MM-DD&to=YYYY-MM-DD`
   - Esperado:
     - Valores de receita bruta, taxas, receita líquida, pedidos e ticket médio.
     - `cogs_cents` calculado quando houver baixa de estoque.
     - `cogs_available=false` se não houver vínculos de ingredientes/baixa.

2. **Timeseries de vendas**
   - Endpoint: `GET /api/reports/sales/timeseries?tenant_id=1&from=YYYY-MM-DD&to=YYYY-MM-DD&granularity=day`
   - Repetir com `granularity=week` e `granularity=month`.
   - Esperado: lista de pontos com receita, pedidos, CMV e lucro.

3. **Top itens**
   - Endpoint: `GET /api/reports/sales/top-items?tenant_id=1&from=YYYY-MM-DD&to=YYYY-MM-DD&limit=20`
   - Esperado:
     - Ranking com quantidade, receita bruta, líquida e lucro.
     - Se `order_items` não existir, fallback usando `items_json`.

4. **Baixo estoque**
   - Endpoint: `GET /api/reports/inventory/low-stock?tenant_id=1`
   - Esperado: itens abaixo do mínimo com estoque atual e custo.

5. **Exportação CSV**
   - Endpoint: `GET /api/reports/export/financial.csv?tenant_id=1&from=YYYY-MM-DD&to=YYYY-MM-DD`
   - Endpoint: `GET /api/reports/export/top-items.csv?tenant_id=1&from=YYYY-MM-DD&to=YYYY-MM-DD&limit=50`
   - Esperado: arquivos CSV baixados e abertos corretamente.

## Fase 6 — Auth + RBAC (Admin)

1. **Login com credencial default (DEV)**
   - Acesse: `/admin/login`
   - Use: `admin@local` / `admin123` com `tenant_id=1`.
   - Esperado: login redireciona para `/admin/1/dashboard`.

2. **Bloqueio sem login**
   - Em uma aba anônima, tente abrir `/admin/1/dashboard`.
   - Esperado: redireciona para `/admin/login`.

3. **Permissões por role**
   - Crie usuários admin/operator/cashier na tabela `admin_users`.
   - Valide:
     - **admin**: acesso total (menu, estoque, modifiers, reports, dashboard, finance, payments).
     - **operator**: dashboard, pedidos (leitura), modifiers (ler/criar), reports (ler/export).
     - **cashier**: dashboard, pedidos (leitura), payments/caixa, reports (ler).

4. **Logout**
   - Clique em `Logout` no topo do admin.
   - Esperado: cookie removido e redireciona para `/admin/login`.

5. **Auditoria**
   - Faça login (gera `login_success`).
   - Crie um adicional ou registre um pagamento.
   - Esperado: entradas em `admin_audit_log` para `login_success` e para a ação sensível.

## Fase 7 — Admin User Management + Segurança + Auditoria

1. **Criar usuários admin/operator/cashier**
   - Acesse: `/admin/1/users`.
   - Crie ao menos um usuário por role.
   - Esperado: tabela lista todos, com role e status ativo.

2. **Login com cada role**
   - Faça logout e login com cada usuário criado.
   - Esperado: acesso conforme role (admin acessa usuários/auditoria, demais não).

3. **Reset de senha**
   - Na página de usuários, clique em “Reset senha”.
   - Defina nova senha e faça login com ela.
   - Esperado: senha atualizada e login funciona.

4. **Desativar usuário**
   - Marque usuário como inativo e salve.
   - Esperado: usuário não consegue mais logar.
   - Observação: tentar desativar o próprio usuário deve retornar erro 400.

5. **Rate-limit de login**
   - Faça 8 tentativas de login inválidas em 10 minutos para o mesmo tenant/email.
   - Esperado: bloqueio por 10 minutos e mensagem de lockout.
   - Após o período, tente novamente com credencial correta e valide que funciona.

6. **Auditoria viewer**
   - Acesse `/admin/1/audit`.
   - Filtre por período, usuário e ação.
   - Esperado: registros de login_success/login_failed/login_locked, criação/edição de usuários e resets.

## Fase 8 — KDS (produção operacional)

1. **Preparar cardápio com áreas de produção**
   - Endpoint: `PUT /api/menu/{tenant_id}/{item_id}`
   - Defina `production_area` como `COZINHA`, `BAR` ou `BEBIDAS`.
   - Esperado: resposta do item inclui `production_area`.

2. **Criar pedido com itens de áreas distintas**
   - Endpoint: `POST /api/orders/{tenant_id}`
   - Use pelo menos um item de `COZINHA` e outro de `BEBIDAS`.
   - Esperado: `order_items` criados com `production_area` correto.

3. **Abrir KDS por área**
   - Acesse: `/kds/1?area=COZINHA` (ou `BEBIDAS`).
   - Esperado:
     - Página fullscreen sem menu admin.
     - Apenas pedidos com itens da área aparecem.
     - Auto-refresh a cada 5 segundos.

4. **Iniciar preparo**
   - Clique em **Iniciar** em um pedido `RECEBIDO`.
   - Esperado:
     - Pedido muda para `EM_PREPARO`.
     - Registro criado em auditoria (`/admin/1/audit`).

5. **Marcar pronto por área**
   - Clique em **Pronto** na área `COZINHA`.
   - Esperado:
     - Pedido continua `EM_PREPARO` se outra área ainda não marcou `Pronto`.
     - Quando todas as áreas estiverem prontas, status vira `PRONTO`.
     - Auditoria registrada para cada ação.

## Fase 9 — Comunicação e Experiência do Cliente

1. **Criar pedido e gerar comunicação automática**
   - Use `POST /api/orders/{tenant_id}` ou finalize um pedido via WhatsApp inbound.
   - Esperado:
     - Evento `order.created` dispara envio mock.
     - Registro criado em `whatsapp_outbound_log` com template `order_confirmed`.

2. **Atualizar status do pedido**
   - Use `PATCH /api/orders/{order_id}/status` com `EM_PREPARO`, `PRONTO`, `SAIU_PARA_ENTREGA` e `ENTREGUE`.
   - Esperado:
     - Registros em `whatsapp_outbound_log` para cada transição (templates `order_in_preparation`, `order_ready`, `order_out_for_delivery`, `order_delivered`).
     - Auditoria com ação `whatsapp.outbound.sent`.

3. **Opt-in**
   - Ajuste `customer_stats.opt_in` para `0` no SQLite para o telefone do cliente.
   - Repita a atualização de status.
   - Esperado:
     - Log com status `SKIPPED` e motivo `opt_out`.
     - Auditoria com ação `whatsapp.outbound.skipped`.

4. **Histórico do cliente**
   - Acesse `/admin/{tenant_id}/customers`.
   - Busque pelo telefone do cliente e veja:
     - Total de pedidos, total gasto e último pedido.
     - Lista de pedidos anteriores.
