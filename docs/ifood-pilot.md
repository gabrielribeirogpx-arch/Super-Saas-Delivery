# Piloto iFood no Fomizero

O coletor registra eventos do iFood no banco do Fomizero para uma única loja de
homologação. Ele grava o identificador do pedido e o status recebido. A
confirmação de recebimento ao iFood só ocorre depois da gravação. Reenvios do
mesmo evento reutilizam o registro existente.

## Configuração em homologação

1. Crie um aplicativo de teste no iFood Developer com Order e Events e
   autorize uma loja de teste pelo fluxo de aplicativos distribuídos.
2. Aplique a migração Alembic e configure no processo do piloto:

   - `IFOOD_PILOT_ENABLED=true`
   - `IFOOD_PILOT_TENANT_ID` com o ID interno da loja Fomizero de homologação.
   - `IFOOD_PILOT_MERCHANT_ID` com o UUID da mesma loja no iFood.
   - `IFOOD_PILOT_ACCESS_TOKEN` com o token de teste, via gerenciador de segredos.

3. Na raiz do backend, rode `python -m scripts.run_ifood_pilot` para coletar um
   lote ou adicione `--watch` para consultar a API a cada 30 segundos.
4. Gere um pedido de teste e verifique o ID externo e o evento `PLACED` na
   tabela `ifood_events`.

O piloto usa um token temporário fornecido pelo operador. A conexão pelo painel,
renovação de tokens, importação no KDS e envio de ações operacionais fazem parte
das fases seguintes. Use exclusivamente a loja de teste, pois o coletor confirma
recebimento de eventos na fila do iFood.

- [Criar um aplicativo de teste](https://developer.ifood.com.br/en-US/docs/getting-started/first-steps/create-app)
- [Autorização da loja](https://developer.ifood.com.br/en-US/docs/food/guides/modules/authentication/distributed)
- [Polling e confirmação de eventos](https://developer.ifood.com.br/es-CO/docs/food/guides/modules/events/polling-overview)

## Importar e confirmar pedidos de teste

Após o backend aplicar a migração `20261127_05_ifood_orders`, adicione
`--import-orders` ao comando do coletor:

```bash
python -m scripts.run_ifood_pilot --watch --import-orders
```

Para habilitar a confirmação no painel, configure os mesmos quatro valores
`IFOOD_PILOT_*` no backend da API. Use o mesmo token de teste e a mesma
unidade no backend e no coletor. Gere um novo pedido FOOD. A seção **Pedidos
iFood · Teste** na aba **Pedidos** mostra os detalhes importados da unidade
piloto. O coletor busca os detalhes de eventos `PLACED` dos últimos dez
minutos e repete a consulta se os detalhes ainda retornarem 404.

O botão **Confirmar pedido iFood** fica disponível durante os oito minutos
após a criação. Quando o iFood aceita a solicitação, o painel indica
confirmação enviada. O pedido aparece como confirmado quando chega o
evento `CONFIRMED`. Esses pedidos de teste ficam em uma seção própria da
aba **Pedidos**, sem acionar os fluxos de pedidos próprios.

## Conexão do primeiro restaurante em produção

Após a homologação, configure no backend e no worker de produção as variáveis
`IFOOD_CLIENT_ID`, `IFOOD_CLIENT_SECRET` e `IFOOD_CONNECTION_KEY` (uma chave
Fernet estável). Defina `IFOOD_PRODUCTION_TENANT_IDS` com os IDs dos restaurantes
autorizados, separados por vírgula. O tenant do piloto continua reservado ao
aplicativo de teste. O backend precisa aplicar a migração
`20261128_01_ifood_connections` antes de iniciar o novo worker.

Use `python -m scripts.run_ifood_production` em um serviço separado, com uma
réplica e o mesmo banco do backend. O dono abre **Minha Loja → Integrações**,
autoriza no Portal do Parceiro, retorna com o código e informa o UUID da loja
autorizada. Verifique os pedidos no KDS e as entregas parceiras na aba Entregas.
A posição é disponibilizada depois da atribuição do entregador, com Redis
configurado no backend para compartilhar o limite de consultas ao iFood.
