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

## Credenciais e auditoria

Cada conexão recebe uma credencial no formato `fmz_mcp_<key_id>.<secret>`. O
segredo é mostrado apenas na emissão; o banco persiste somente SHA-256 do token
completo. A chave pertence a exatamente um tenant, possui escopos explícitos,
pode expirar e pode ser revogada imediatamente. Não existe escopo curinga.

A auditoria registra restaurante, credencial, identificadores opacos de
requisição e conversa, ferramenta, risco, resultado, duração e apenas os nomes
dos argumentos. Valores de argumentos, mensagens, telefone, endereço,
credenciais e respostas da ferramenta não são persistidos nesse log.

## Primeiro rollout de ferramentas

O endpoint JSON-RPC é `/api/integrations/wazza/mcp` e implementa
`initialize`, `tools/list` e `tools/call`. A primeira versão publica somente:

- `restaurant_get_status`
- `menu_list_categories`
- `menu_search_items`
- `menu_get_item`

Todas exigem `menu:read`, são limitadas por credencial e consultam o tenant
derivado da própria credencial. Ferramentas de cliente, pontos, pedidos e
rastreamento permanecem ocultas até a fase seguinte validar o uso da identidade
assinada ponta a ponta. Elas não devem aceitar telefone como argumento
alternativo.

## Identidade assinada do cliente

Chamadas originadas de uma conversa WhatsApp podem enviar
`X-Wazza-Customer-Context` e `X-Wazza-Customer-Signature`. O contexto contém
somente telefone canônico, conversa opaca, emissão, expiração e o identificador
da requisição JSON-RPC. A assinatura HMAC usa uma chave derivada da credencial
Bearer vinculada ao restaurante; não existe segredo adicional em texto puro.

O Fomizero valida assinatura, audiência, emissor, prazo máximo de 90 segundos e
o vínculo com o `request_id`. Contexto incompleto, adulterado, expirado ou
reutilizado em outra requisição é rejeitado. O cabeçalho legado de conversa sem
assinatura não é usado para identificar cliente nem para preencher auditoria.

## Leituras pessoais

Com contexto assinado e escopos mínimos, o servidor também publica:

- `customer_get_profile` e `customer_get_points` com `customer:read`;
- `order_list_recent`, `order_get_status` e `order_get_tracking` com
  `order:read`.

As consultas resolvem o cliente pelo telefone verificado do contexto e pelo
tenant da credencial. Nenhuma delas aceita telefone, cliente ou tenant nos
argumentos. Pedidos de outra pessoa ou loja aparecem como não encontrados. O
rastreamento só fornece link e ETA quando uma entrega própria está efetivamente
em rota, atribuída a um entregador, com recurso contratado e token válido;
pedidos entregues, cancelados, retiradas e pedidos ainda em preparo não expõem
rastreamento.
