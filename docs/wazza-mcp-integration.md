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

## Fase 2 — rascunho e orçamento

Com identidade assinada e escopo `order:draft`, o Wazza pode criar um rascunho,
adicionar, alterar e remover itens, escolher entrega/retirada, registrar uma
preferência de pagamento e solicitar um orçamento. O rascunho fica em tabela
isolada e expira após duas horas de inatividade; ele nunca aparece em pedidos,
KDS, estoque, financeiro ou relatórios.

IDs, disponibilidade, adicionais e preços são sempre consultados novamente no
catálogo do tenant autenticado. Preços fornecidos pelo modelo são proibidos.
Cada rascunho usa identificador opaco e só é acessível pelo mesmo tenant e pelo
telefone do contexto assinado; telefone e tenant não são argumentos das
ferramentas. Toda escrita exige chave de idempotência: repetir a mesma operação
não duplica efeitos e reutilizar a chave com dados diferentes é bloqueado. A
escolha de pagamento não cobra e não marca nada como pago. O
orçamento é somente leitura, recalcula os valores atuais e declara
`creates_order: false`.

## Fase 3 — confirmação e criação do pedido

`order_draft_confirm` exige identidade assinada e escopo `order:create`. A
ferramenta é classificada como `destructive` e só aparece quando
`WAZZA_MCP_ENABLED` e `WAZZA_MCP_ORDER_CONFIRM_ENABLED` estão habilitadas e o
servidor tem a chave de assinatura configurada. As duas flags têm valor padrão
desligado.

Quando a confirmação está disponível, um orçamento completo inclui
`confirmation_token` e `confirmation_expires_at`. O token assinado pelo
Fomizero expira em até cinco minutos e vincula tenant, cliente, conversa,
rascunho, versão, itens, adicionais, entrega, pagamento e totais. O fluxo do
Wazza deve apresentar o orçamento e aguardar uma resposta afirmativa inequívoca
do cliente antes de chamar a ferramenta com `draft_id`, `confirmation_token` e
`idempotency_key`. A assinatura da identidade autentica a conversa. Cabe
ao fluxo do Wazza determinar se o cliente respondeu afirmativamente àquele
orçamento.

O checkout oficial revalida a disponibilidade, as regras comerciais e os
valores. Qualquer mudança no conteúdo do orçamento, inclusive de preço ou taxa,
exige um novo orçamento e uma nova confirmação. A resposta contém apenas
`draft_id` e `order_id`. Em caso de timeout ou perda da resposta, o Wazza
reenvia os mesmos argumentos com um novo contexto WhatsApp assinado, ligado à
nova requisição. O vínculo persistido no rascunho permite devolver o mesmo pedido
após a expiração do token ou do recibo de checkout.

O pedido tem origem `wazza_mcp`. Pix, dinheiro, crédito e débito são preferências
de cobrança e geram um pagamento `pending` na mesma transação do pedido,
rascunho, recibo, outbox e auditoria. A entrada em caixa depende da confirmação
posterior do recebimento pelo fluxo financeiro oficial. A auditoria da
confirmação guarda metadados e nomes de campos do esquema, sem registrar seus
valores.

## Fase 4 — edição, cancelamento e análise do restaurante

As ferramentas `order_request_edit` e `order_request_cancel` exigem identidade
WhatsApp assinada, os escopos `order:edit` e `order:cancel`, respectivamente,
e a flag `WAZZA_MCP_ORDER_MUTATION_ENABLED`, desligada por padrão. A chamada
inicial devolve um resumo assinado, válido por até cinco minutos. O Wazza
apresenta o resumo e, depois da confirmação explícita do cliente, repete os
argumentos com o token. A edição substitui os itens, preserva o endereço e a
preferência de pagamento e recalcula a taxa da entrega existente.

A confirmação aplica a alteração automaticamente apenas para pedidos próprios
de origem `wazza_mcp` recebidos, com um pagamento manual pendente e sem
efeitos que precisem de compensação. Cancelamento fecha pedido e pagamento na
mesma transação. Edição atualiza itens, totais e valor a receber.

A área de Pedidos mostra a fila de solicitações do WhatsApp. O operador pode
autorizar, rejeitar ou pedir a verificação de uma resolução manual. A intenção
autorizada aguarda os fluxos oficiais quando o Fomizero não pode aplicá-la
atomicamente. Para verificar um cancelamento, o sistema confere o estado do
pedido, os pagamentos originais e os efeitos vinculados de caixa, estoque e
benefícios. Para verificar uma edição, confere os itens e adicionais, o total,
a entrega preservada e o pagamento manual que corresponde ao novo total.
Sem evidência suficiente, a solicitação termina em `Falha na aplicação`.
A solicitação e os efeitos de notificação têm chaves persistentes para replay.
