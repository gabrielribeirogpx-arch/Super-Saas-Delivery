# Roteiro de teste manual (WhatsApp)

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
