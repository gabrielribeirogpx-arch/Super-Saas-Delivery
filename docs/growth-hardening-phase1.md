# Crescimento operacional — primeira etapa

Objetivo: reduzir gargalos concretos de restaurantes operando simultaneamente. Esta entrega não certifica capacidade de 1.000 lojas e não altera limites comerciais dos planos.

## Mudanças

- Criação de pedido público: geocodificação termina antes da seção de persistência; gravação síncrona roda em worker thread, sem bloquear o loop ASGI enquanto aguarda o PostgreSQL. A cota da loja é bloqueada antes de inserir clientes/endereços, evitando upgrade concorrente de locks de chave estrangeira. A sessão é usada sequencialmente, sem compartilhamento concorrente.
- Histórico administrativo: o frontend usa `/api/orders/{tenant_id}/search` com paginação limitada a 100 registros por resposta (8 na interface), filtros no servidor e desempate por ID. Indicadores e opções de pagamento/entrega vêm de `/overview`, por agregações SQL, independentes da página e filtros. `Pedidos hoje` considera o dia e offset do navegador; o filtro de data mantém a interpretação UTC anterior. Busca de clientes ignora acentos; curingas de busca são tratados como texto.
- O endpoint legado de lista continua disponível para compatibilidade com outros consumidores. A tela principal deixa de utilizá-lo. Deve ser inventariado antes de descontinuar; ele ainda não tem limite obrigatório.
- Reconciliação Hotmart: vínculos nunca revisados e mais atrasados são selecionados antes dos recentes. O lote continua em 25 por ciclo: justiça não aumenta a capacidade nominal de 300 revisões/hora no cron atual de 5 minutos. Frequência/orçamento e latência da API precisam ser dimensionados separadamente.
- Métricas: rotas usam template, sem IDs/token por série; URLs não reconhecidas entram em `<unmatched>`. Dicionários locais têm limite e agregam excedentes em `<overflow>`. Permanecem locais, sem percentis e sem substituir um serviço externo de monitoramento. Logs de requisição também passam a usar o template.

## Implantação

1. Aguardar CI e fazer merge do PR.
2. Implantar o backend primeiro. Não há migration nova nem variáveis obrigatórias novas. Conferir healthcheck, logs e abertura das rotas de histórico com uma sessão administrativa válida.
3. Implantar o frontend após o backend: a versão nova depende dos endpoints `/search` e `/overview`. Conferir página seguinte, busca por cliente antigo, filtros, resumo e alteração de status. O retorno máximo da página não pode alterar os totais dos indicadores.
4. Implantar também o serviço Hotmart Billing a partir do mesmo código para receber a correção de justiça. Manter seu Custom Start Command e cron; não iniciar o servidor web nesse serviço. Nenhuma credencial precisa ser trocada.
5. Acompanhar erros, espera por bloqueios, latência de criação de pedido, tamanho de respostas e ciclos da cobrança. Esta entrega não aumenta automaticamente CPU/RAM, workers ou réplicas.

Rollback: reverter o código e reimplantar. Não há migração de dados a desfazer; os endpoints antigos foram preservados. Evitar frontend novo com backend antigo; em rollback, restaurar primeiro o frontend.

## Validação

- Testes de histórico cobrem paginação estável, limites, isolamento de tenant, autenticação, filtros em páginas antigas, acentos, curingas literais, dia local e indicadores fora da página atual.
- Teste de concorrência assíncrona mantém o loop responsivo enquanto o trabalho de persistência está bloqueado.
- Testes PostgreSQL em schema descartável cobrem dois pedidos simultâneos da mesma loja, geocodificação antes dos locks, espera controlada, numeração diária e cota com uma ou duas vagas disponíveis. Mensagens externas são desativadas; nenhum pagamento é efetuado.
- Testes de reconciliação demonstram progresso dos IDs mais altos mesmo quando os primeiros vínculos já voltam a ficar vencidos.
- Métricas são verificadas com vários IDs/404 e limite de armazenamento, preservando contagens em overflow.
- Chromium com dados sintéticos verifica páginas, filtros em todo o histórico, foco de digitação e ausência de overflow em 320, 390 e 1366 px. Não usa backend real.

Comandos: `pytest -q`; CI PostgreSQL existente inclui automaticamente `tests/staging/test_growth_postgres.py`; `npm run test:order-history`; `npm run test:order-history:browser` contra frontend local. O contrato OpenAPI inclui os dois novos endpoints.

## Trabalho ainda necessário antes de afirmar escala

- Idempotência persistente para tentativas do checkout e outbox/fila durável dos efeitos operacionais. O pedido confirmado e a notificação ainda não fazem parte de uma única entrega garantida.
- Reduzir consultas periódicas de cozinha/rastreamento, com eventos, backoff e ressincronização. Não aumentar o intervalo cegamente e atrasar o funcionamento da cozinha.
- Orçamento explícito de conexões/processos/réplicas; mover os demais acessos SQL síncronos de rotas assíncronas conforme perfil. O primeiro lookup de loja/autenticação pode manter uma transação de leitura durante a geocodificação: ainda precisa medição do pool.
- Índices validados com planos de execução e volume representativo. Não aplicar índices de produção sem confirmar o catálogo atual e planejar criação concorrente quando necessária.
- Rate limit distribuído por identidade canônica, recuperação supervisionada dos subscribers, readiness de dependências, métricas externas/alertas e teste de restauração de backup.
- Dimensionar reconciliação para a base, monitorar idade do backlog e limites da Hotmart; sucesso do processo não comprova fila vazia.
- Teste progressivo de carga isolado, com navegação, pedidos, cozinha, painel, entregadores e acompanhamento simultâneos, dados históricos e falhas controladas. Medir p95/p99, erros, conexões, locks, filas e custo. Não executar carga em produção.

Nenhuma estimativa numérica de capacidade foi derivada dos testes de correção desta etapa.
