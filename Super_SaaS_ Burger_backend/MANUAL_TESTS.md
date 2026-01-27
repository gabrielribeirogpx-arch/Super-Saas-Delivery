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
