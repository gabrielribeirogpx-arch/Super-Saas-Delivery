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
