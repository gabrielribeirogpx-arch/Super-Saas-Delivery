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

O modo lote suporta 1..30 lojas, até 100 pedidos e até 30 fluxos por execução. Os limites
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

## Carga sustentada (10 minutos)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "& .\Start-OrdersKitchen.ps1 -Lojas carga-01,carga-02,carga-03,carga-04,carga-05 -Sustentado -CredencialUnica"
```

-CredencialUnica só deve ser usada quando todos os administradores de teste usam o
mesmo email e senha, como nas fixtures carga-01..05. O launcher pede apenas uma vez;
a autenticação no k6 continua separada para cada tenant. Sem essa opção mantém os
prompts individuais. Credenciais não são escritas no relatório.

-Sustentado agenda 1 novo fluxo de pedido por segundo NO TOTAL durante 10 minutos,
até 600 pedidos (120 por loja ao usar 5 lojas). Usa constant-arrival-rate: a lentidão
não reduz silenciosamente a taxa desejada. Prealoca 10 VUs e permite até 30; esses
números representam capacidade do gerador, não lojas ou fluxos sempre ativos.
Cada fluxo mantém os mesmos oito requests e duas pausas de 1s do teste de lote.
Há até 2 minutos extras para terminar fluxos iniciados, além de setup/teardown.

Exige 5..30 lojas; parâmetros Pedidos/Fluxos são substituídos pela configuração
fixa do modo sustentado. Verifique cota e acesso das lojas antes da execução. O
limite de segurança do código impede iniciar iterações acima de 600.

No final, confira: 600 pedidos prontos e replays válidos, zero etapas inválidas e
zero dropped_iterations. Iterações descartadas são falha de atingimento da carga,
não sucesso. O histórico é paginado, verificando quantidade e unicidade de IDs,
marcadores e tokens mesmo quando cada loja ultrapassa 100 pedidos.

O resumo contém p95 global da carga e p95 por minuto (minute:0..9). Requisições
iniciadas após 10 minutos durante a drenagem ficam em minute:10 e entram no p95
global. Compare os minutos iniciais e finais, CPU/memória/conexões do banco e fila.
A outbox precisa ser consultada separadamente no SSH, inclusive durante a carga
em outro terminal: --stats antes/depois sozinho não mede atraso máximo da fila.

Esta é uma rodada moderada de estabilidade, não demonstra capacidade máxima nem
1.000 restaurantes. Não aumente limites apenas para transformar o relatório em verde.

### Limite no fim da janela

Uma chegada adicional pode ser agendada na fronteira dos 10 minutos. Iterações com
índice >=600 retornam antes de fazer qualquer requisição, incrementando apenas
chegadas_alem_do_limite. Não abortam o teste nem cancelam pedidos em andamento.
Por isso, o total de iterações pode superar o total de pedidos. Os critérios de
aceitação continuam exigindo exatamente 600 pedidos PRONTO, 600 replays válidos,
zero dropped_iterations e reconciliação final; chegada extra não conta como pedido.

## Trinta lojas

Após preparar carga-01..30 com o script do PR #842 e a mesma senha de teste:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-OrdersKitchen.ps1 -LojasDeCarga 30 -Pedidos 60 -Fluxos 30 -CredencialUnica
```

-LojasDeCarga aceita 1..30 e gera os slugs automaticamente, substituindo -Lojas.
São 60 pedidos totais, 2 por loja, com 30 VUs. Cada loja é autenticada separadamente.
O setup tem limite de 5 minutos para comportar os 30 logins sequenciais; sua latência
não entra no p95 de carga. Teardown tem 3 minutos para reconciliar todas as lojas.
O modo sustentado continua limitado a 600 pedidos/10min e 1 chegada/s no total;
aceitar mais lojas não aumenta automaticamente a taxa de chegada.

### Diagnóstico do pico de 30 fluxos

O resumo também separa p95 de cardápio, criação, repetição idempotente, histórico,
início do preparo e conclusão. Os filtros incluem `phase:load`, excluindo login e
reconciliação. Cada operação deve atender ao mesmo objetivo de p95 < 2 s; isso é
mais rigoroso que apenas o percentil agregado. Não altera volume nem payloads.

Repetir o lote de 60 pedidos / 30 fluxos nas 30 lojas permite localizar a etapa
lenta. O teste sustentado de 1 pedido/s teve até 5 VUs ativos e não reproduz esse
pico. Tempo HTTP não separa espera por conexão, lock, execução SQL ou thread;
atribuir a causa exige medição do servidor durante o mesmo intervalo.
