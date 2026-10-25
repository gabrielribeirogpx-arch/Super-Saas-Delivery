# Pedidos e cozinha no staging

O roteiro executa checkout público -> repetição idempotente -> busca administrativa
-> EM_PREPARO -> PRONTO -> reconciliação final. Cada iteração cria no máximo um
pedido, com chave exclusiva por execução. Só modifica pedidos cujo nome, tenant e
token correspondem ao lote. Não faz retries cegos após timeouts.

O destino é fixo: super-saas-delivery-production.up.railway.app (backend de staging,
apesar do nome). Requer lojas exclusivas para testes, sem integrações externas.
A Meu Burger foi indicada pelo operador como loja de teste sem integrações.

## Windows PowerShell

Instale k6 com `winget install --id Grafana.k6 --exact --source winget`.
Salve Start-OrdersKitchen.ps1 e orders-kitchen.js na mesma pasta. Execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-OrdersKitchen.ps1
```

A opção ExecutionPolicy vale apenas para esse processo. Inspecione os arquivos
antes de executar. O padrão usa meuburger, 10 pedidos e 2 fluxos simultâneos.
Informe e-mail e senha do administrador da loja no terminal. A senha não é escrita
em arquivo nem em argumento da linha de comando: é passada em variável de ambiente
para o processo k6 e removida no finally do launcher.

Para uma rodada posterior, após analisar o primeiro relatório:

```powershell
.\Start-OrdersKitchen.ps1 -Lojas meuburger,outra-loja-teste -Pedidos 20 -Fluxos 4
```

O script suporta 1..10 lojas, até 100 pedidos e até 20 fluxos por execução. Os limites
são deliberadamente pequenos. Cada loja precisa de produto ativo sem adicionais
obrigatórios, acesso ativo e cota de pedidos suficiente. Falhas de plano/cota são
reportadas, não contornadas. O primeiro produto compatível é usado.

## Efeitos e validação

- Pedidos reais são gravados **no staging**, com marcador LT-... e nota NAO PRODUZIR.
- Retirada, dinheiro, sem telefone, email ou endereço: não chama geocodificação nem
  informa destinatário. Ainda assim, mantenha integrações externas desativadas.
- Os registros e eventuais lançamentos financeiros seguem a lógica normal da aplicação,
  consomem a cota e ficam PRONTO no painel. Não há limpeza automática ou cobranças por PSP.
- Public checkout não recebe cookie administrativo. A sessão correta é enviada nas
  leituras e mudanças administrativas; isolamento de cookies é verificado nos testes.
- Valida duplicação por resposta idempotente e quantidade no histórico. Verifica
  novamente o estado persistido após cada atualização, sem confiar só no HTTP 200.
- Relatório JSON e resumo do k6: pedidos_prontos e repeticoes_sem_duplicacao devem
  corresponder ao total, etapas_invalidas deve ser zero. O p95 de carga exclui setup.
- O log final informa o marcador do lote e quantos pedidos foram reconciliados por loja.
- Não mede GPS, entregador, SSE/WebSocket, renderização do KDS nem envio de WhatsApp.
  Dois fluxos em uma loja não equivalem a duas lojas ou a capacidade para 1.000 lojas.

Antes e depois, no SSH do **backend de staging**, use:

```sh
/app/.venv/bin/python /app/scripts/run_order_outbox.py --stats
```

Capture pendências/erros e oldest_unfinished_at. Done acumulado não mede sozinho o
atraso de entrega de eventos. O roteiro HTTP não verifica conclusão dos jobs da outbox.
Acompanhe Metrics do backend e Postgres no mesmo período; aumente carga só após revisão.

## Validação do roteiro

`node --test scripts/load/orders-kitchen.test.cjs` usa transporte simulado e cobre
fluxo completo em duas lojas, cookies, chave repetida, resposta divergente, timeout,
tenant incorreto e duplicação na reconciliação. Não substitui execução contra staging.
