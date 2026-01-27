# Roteiro de teste manual (WhatsApp)

## Modifiers naturais no WhatsApp

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
     - Resposta sugere os adicionais permitidos do item, sem pedir número.

3. **Quantidade + modifier**
   - Mensagem: `2 x-burger com cheddar`
   - Esperado:
     - Adiciona 2x o item com o modifier cheddar.

4. **Item sem modifiers**
   - Mensagem: `coca lata`
   - Esperado:
     - Match forte com “Coca-cola lata” sem pedir número.

5. **Ambiguidade real**
   - Mensagem: uma frase que gere duas opções muito próximas no cardápio.
   - Esperado:
     - Bot solicita confirmação (número ou nome), mantendo o fluxo atual.
