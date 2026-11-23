# Integração Wazza ↔ Fomizero por MCP

## Decisões de segurança da versão 1

O Fomizero permanece como fonte de verdade de restaurante, cliente, cardápio,
preço, entrega, pagamento e ciclo de vida do pedido. O Wazza interpreta a
conversa e solicita ferramentas; ele não implementa regras comerciais.

### Identidade e isolamento

- O restaurante é derivado da credencial da conexão MCP, nunca de `tenant_id`
  fornecido nos argumentos de uma ferramenta.
- A identidade do cliente vem de contexto de WhatsApp assinado pelo Wazza. Uma
  ferramenta não aceita um telefone escolhido pelo modelo.
- Toda consulta de pedido também valida que o pedido pertence ao restaurante e
  ao cliente autenticados.

### Escritas

- Conversas manipulam um rascunho separado. Rascunhos não entram no KDS, não
  movimentam financeiro, não consomem numeração e não disparam notificações.
- A confirmação recalcula preços e disponibilidade no servidor e reutiliza o
  checkout transacional oficial do Fomizero.
- Toda mutação exige chave de idempotência. Repetir a mesma chamada devolve o
  resultado original e não cria um segundo pedido.
- Editar ou cancelar um pedido recebido exige confirmação explícita do cliente.
  Pedido em preparo exige aprovação humana. Estados posteriores são negados.

### Implantação

`WAZZA_MCP_ENABLED` é desligada por padrão. Cada grupo de ferramentas também é
habilitado separadamente por restaurante. O primeiro rollout terá somente
leitura, em um tenant de homologação, antes de qualquer criação de pedido.

O contrato versionado está em `contracts/wazza_mcp_v1.json`. Alterações de
autoridade, identidade ou classificação de risco devem atualizar o contrato e
seus testes no mesmo pull request.
