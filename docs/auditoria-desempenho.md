# Auditoria de desempenho do Fomizero

## Mudanças verificadas

| Fluxo | Trabalho reduzido | Validação |
| --- | --- | --- |
| Histórico de pedidos na web e no Gestão | Índice PostgreSQL por loja, data e ID elimina a ordenação explícita da página cronológica quando o planejador usa o índice. A migração cria o índice de forma concorrente no PostgreSQL. | PostgreSQL 16 local, 160 mil pedidos sintéticos em oito lojas. A consulta de oito registros com `OFFSET 80` passou de 5,672 ms com ordenação para 0,031 ms com varredura do índice em uma execução de cada plano. As linhas retornadas foram iguais. Upgrade, nova execução e downgrade foram verificados. |
| Cardápio público e prévia | Reaproveitamento da configuração de aparência já consultada. | Uma consulta SQL a menos por resposta com configurações cadastradas. Testes de cardápio e criação de pedidos. |
| Rastreamento web | Limite de uma consulta de snapshot em voo por tela. Cancelamento ao sair da tela ou após 12 segundos, mantendo SSE e tentativas periódicas. | Transpilação do componente e testes do backend de rastreamento. |
| Prévia do Cardápio no Gestão | Cards montados conforme se aproximam da tela, com decodificação das imagens proporcional à largura exibida. | O teste Flutter verifica que um produto fora da tela só é montado após a rolagem. O tamanho do download das fotos segue o arquivo publicado. |

A medição acima cobre a consulta paginada isoladamente. A latência HTTP inclui autenticação, contagem filtrada, leitura e serialização dos pedidos. A amostra sintética serve para conferir o plano de execução, sem extrapolação de capacidade para produção.

## Pontos a medir antes de aumentar a capacidade

| Fluxo revisado | Limite observado no código | Medição que orienta a próxima decisão |
| --- | --- | --- |
| Pedidos, filtros e painel | A paginação web e Android limita o resultado. Contagem exata, buscas com substring, páginas profundas e agregados históricos ainda crescem com o volume. O dashboard do app faz cinco leituras por atualização. | p95 de histórico, busca e gráficos por volume e idade da loja. Planos de consulta separados para datas, busca de cliente e status. |
| Cardápio e mídia | Os complementos já são consultados em lote. O cardápio público ainda retorna o catálogo ativo completo e as imagens usam os arquivos publicados. | Bytes do JSON e das imagens, tempo até o cardápio ficar interativo e memória durante rolagem em Android com pouca RAM. |
| KDS, entregas e rastreamento | O KDS web consulta a cada cinco segundos. O SSE mantém verificação periódica de status para detectar revogação e atualizar em caso de falha na publicação. | Consultas por tela ativa, conexões SSE simultâneas, uso do pool do Postgres, reconexões e tempo entre mudança do pedido e atualização da tela. |
| Checkout, pagamentos e push | A criação pública possui idempotência e o worker de outbox processa efeitos assíncronos. A capacidade efetiva depende da concorrência no banco e dos serviços externos. | p95 do checkout, pedidos duplicados, erros por provedor, idade da fila e tempo entre pedido e push. Exercitar timeout de terceiros e reenvio com a mesma chave de idempotência. |

## Validação de capacidade

Executar em ambiente isolado com banco sintético e serviços de pagamento e push de teste. Começar pela carga esperada no horário de pico, aumentar em etapas e repetir com cardápios grandes, lojas com histórico longo e conexões SSE concorrentes. Registrar throughput, p50, p95, p99, erros, conexões do banco e atraso da fila durante cada etapa. Conferir que o mesmo pedido aparece uma vez no checkout, histórico e cozinha e que os totais batem entre web e app.

Esta rodada incluiu revisão estática dos fluxos acima e testes locais. A capacidade ponta a ponta e o pico sustentável ainda precisam de ensaio com concorrência representativa.
