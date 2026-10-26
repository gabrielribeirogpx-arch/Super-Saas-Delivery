# Pedidos repetidos e tarefas duráveis

Esta etapa protege o checkout público contra repetição da mesma tentativa e grava as tarefas operacionais na transação do pedido. Não altera preços, meios de pagamento, cotas comerciais ou ativação Hotmart. Não certifica capacidade para 1.000 restaurantes.

## Garantias e limites

- O cardápio envia `Idempotency-Key`, aleatória e gerada com Web Crypto. O backend guarda somente seu SHA-256, vinculado à loja, e o hash do payload normalizado/identidade verificada/modificadores. A chave bruta não vai para o banco nem para logs.
- Pedido, recibo da tentativa e tarefas confirmam juntos. Falha antes do commit desfaz todos. Repetição com a mesma chave e dados devolve a confirmação armazenada, sem consumir outra cota, criar outro pedido ou enfileirar novamente. Dados diferentes retornam conflito.
- A serialização por loja usa `FOR NO KEY UPDATE` antes das inserções: mantém exclusividade de cota/numeração sem conflitar com os locks de chave estrangeira de atualizações operacionais. Geocodificação ocorre antes dessa seção e persistência síncrona fica fora do loop ASGI.
- O recibo guarda a resposta do checkout, incluindo seu token opaco e campos de confirmação, por sete dias. A janela de idempotência é de sete dias; não existe garantia de repetição indefinida. O frontend bloqueia a renovação automática de uma tentativa antiga/ambígua.
- A identidade é por **tentativa**, não por semelhança de itens/telefone. Dois pedidos intencionais iguais podem existir com chaves diferentes. Não há deduplicação global entre dois dispositivos ou abas que iniciem intenções independentes.
- Clientes antigos sem header continuam aceitos para compatibilidade; não recebem essa garantia. Para obter a proteção, integrações devem enviar uma chave nova por intenção e reutilizá-la em retries, nunca gerar outra automaticamente após timeout.
- As tarefas são processadas com entrega **pelo menos uma vez**. Recibos de efeitos evitam repetir estatísticas e efeitos já reconhecidos. Notificação externa não tem garantia absoluta de envio único: o provedor pode aceitar e perder a resposta antes de o sucesso ser registrado localmente. Esse caso pode gerar repetição na recuperação.

## Comportamento do checkout

O navegador persiste apenas chave, digest e data da tentativa, separados por loja. Nome, telefone, endereço e carrinho não são copiados para esse registro. A chave permanece enquanto o resultado for incerto, inclusive após recarregar quando localStorage estiver disponível. Com armazenamento bloqueado, o fallback em memória cobre somente a página atual.

A chave só é retirada após salvar a confirmação na interface e limpar o carrinho. A próxima compra intencional recebe outra chave. Uma rejeição definitiva de validação na primeira chamada permite corrigir os dados; erros de rede, respostas incompletas, conflitos e falhas de uma tentativa já reutilizada preservam a identidade.

Se os dados mudarem enquanto houver uma tentativa sem confirmação, a aplicação não cria outra silenciosamente. Pede para conferir com a loja e oferece **“Já conferi: iniciar outro pedido”**. A ação é explícita e não consulta ou cancela o pedido anterior; deve ser usada somente após a conferência. Alterar a chave de propósito deixa de ser uma repetição protegida.

## O que entra na fila

Produtores cobertos: checkout público e alias de loja, criação administrativa/WhatsApp, mudanças de status do painel, KDS, motorista e entregas. Todos enfileiram antes do commit que cria/altera o pedido.

Efeitos: confirmação e mudanças de status por WhatsApp, estatísticas de pedido entregue e publicação de mudança de entrega no Redis. O payload da fila contém somente status anterior/atual e identificador de entregador; nome, telefone e token são lidos do pedido no processamento. A validade do token é reavaliada antes de montar o link.

Estatísticas e recibo do efeito confirmam na mesma transação. No PostgreSQL um advisory lock por loja serializa a criação/atualização das estatísticas sem bloquear chaves estrangeiras da operação. Recibos permanecem vinculados ao pedido, mesmo após remover tarefas concluídas. Não há backfill/reconciliação de estatísticas históricas nesta entrega.

Mensagens da mesma entrega seguem a ordem da fila por pedido/stream. Um problema no WhatsApp de um pedido não bloqueia estatísticas nem pedidos de outras lojas. Uma mensagem em revisão bloqueia as posteriores desse mesmo stream até o operador resolver. Não há promessa de ordem global entre todos os pedidos.

GPS, streams de localização e impressão local continuam nos seus caminhos existentes. Redis Pub/Sub continua sem replay do lado do consumidor: publicar com zero assinantes é sucesso; clientes recuperam o estado no banco. Falha real ao publicar mantém a tarefa para nova tentativa.

## Consumidores e recuperação

Por padrão, em `ENV=production`/staging, o backend inicia um consumidor fora do loop ASGI. Assim a primeira implantação não exige um serviço adicional. Em dev/test o consumidor embutido fica desativado por padrão para impedir efeitos externos em testes. `ORDER_OUTBOX_EMBEDDED=true|false` permite escolher explicitamente.

O mesmo worker pode rodar separado:

```text
/app/.venv/bin/python /app/scripts/run_order_outbox.py
```

É um serviço contínuo, **sem cron**, sem domínio público e sem healthcheck HTTP. Root Directory igual ao backend; usar o mesmo banco, Redis, `ENV` e `PUBLIC_BASE_DOMAIN` do backend. As configurações WhatsApp são lidas do banco, como no backend. Não substituir o serviço Hotmart Billing por este worker.

Para separar: criar o serviço, verificar consumo e então definir `ORDER_OUTBOX_EMBEDDED=false` na API. A sobreposição temporária é suportada: `SKIP LOCKED`, atualização condicional e token de posse impedem confirmar o trabalho de outro consumidor. Cada tarefa é reservada pouco antes de executar, evitando que o lote inteiro perca o prazo enquanto espera.

Uma reserva dura cinco minutos. Ao reiniciar, tarefas abandonadas tornam-se elegíveis após o prazo. Falhas recebem espera progressiva, até oito tentativas; depois ficam em `review`. Um crash na última tentativa também termina em revisão quando a reserva expira. Finalização de processo para de buscar tarefas novas; o trabalho interrompido permanece no banco.

## Diagnóstico operacional

Dentro do container correto, nunca no PowerShell local:

```text
/app/.venv/bin/python /app/scripts/run_order_outbox.py --stats
/app/.venv/bin/python /app/scripts/run_order_outbox.py --once
```

`--stats` é somente leitura e mostra contagens e data do trabalho pendente mais antigo. `--once` processa um lote e pode enviar notificações reais: não usar para simular testes em produção. `done` inclui trabalho concluído, duplicado já reconhecido e efeitos sem envio permitido pela configuração/consentimento/plano; não é contagem de mensagens recebidas pelo cliente.

Após corrigir a causa de uma falha e conferir um possível sucesso externo ambíguo, o operador com acesso ao banco pode devolver **um job em revisão**:

```text
/app/.venv/bin/python /app/scripts/run_order_outbox.py --retry JOB_ID
```

Esse comando não altera pedidos ou pagamentos e não toma uma tarefa que já esteja sendo processada. Recolocar uma notificação ambígua pode repeti-la. Não reenfileirar tudo sem diagnóstico. Logs do worker usam IDs/códigos fixos, sem texto de exceção de provedor; parâmetros SQL ficam ocultos no engine da aplicação.

Monitorar idade do pendente mais antigo, contagens em review, tentativas, duração dos ciclos, conexões e latência externa. Consumidores dedicados adicionais podem aumentar vazão entre pedidos/lojas; a ordem por stream continua preservada. Não foi medido um número de workers suficiente para 1.000 restaurantes.

## Retenção e volume

A limpeza remove em lotes limitados recibos de checkout expirados e tarefas concluídas há mais de sete dias. Pendências, reservas ativas e revisões não são descartadas por idade. Recibos de efeitos ficam com o histórico do pedido para não permitir reaplicação após limpar o job. IDs de job usam BIGINT no PostgreSQL.

O ciclo de limpeza roda aproximadamente a cada minuto entre lotes. O volume de jobs pode ser várias vezes maior que o de pedidos; medir seu crescimento e duração da limpeza. A retenção de pedidos, logs WhatsApp e recibos de efeitos exige uma política de arquivamento própria. Não fazer remoção automática desse histórico financeiro/operacional nesta etapa.

## Implantação

1. Aguardar CI, conferir backup e implantar backend primeiro. A migration `20261023_02_order_durability` cria três tabelas e índices; não altera pedidos existentes. O start atual aplica o Alembic e o startup confere o head.
2. Confirmar startup e consumidor embutido habilitado no ambiente de produção; consultar `--stats`. Sem consumidor, pedidos continuam entrando, mas tarefas acumulam.
3. Esperar instâncias antigas do backend saírem antes de implantar o frontend. Instâncias antigas ignoram o header e não registram o recibo.
4. Implantar frontend e conferir cadastro do pedido, repetição de tentativa e atualizações. Não efetuar pagamentos ou disparar mensagens de teste reais por este procedimento.
5. Quando separar o worker, manter API/worker na mesma versão e no mesmo banco. Desligar o consumidor embutido apenas após verificar o dedicado.

## Rollback

O frontend pode voltar à versão anterior, com perda da proteção de tentativas nos clientes antigos. Para backend, preferir correção que preserve o novo head da migração: o startup antigo não reconhece a revisão nova. Não fazer rollback cego de código com migration desconhecida.

Não apagar as tabelas da fila ou dos recibos: isso perde trabalho e identidade de tentativas. O downgrade recusa execução com histórico em qualquer uma das três tabelas; também exige inspeção online. Um rollback de backend precisa de versão compatível que mantenha esta migration/modelos, além de um plano para drenar/manter os consumidores e preservar recibos. Não usar downgrade destrutivo como rotina de deploy.

## Validação

Testes cobrem HTTP simultâneo com a mesma chave no PostgreSQL, chaves distintas sem deadlock, conflito de payload, isolamento de loja, cota consumida uma única vez, rollback, perda de resposta e recriação de sessão. A fila é testada com múltiplos consumidores, posse expirada, reconhecimento por worker obsoleto, falha entre estatísticas e ack, falhas de provedor, revisão, limpeza e recuperação após sucesso externo já registrado. Migração é testada por histórico completo PostgreSQL e roundtrip/paridade/recusa de perda de dados.

No cliente, testes verificam reload, concorrência, armazenamento bloqueado, mudança de dados em tentativa incerta, expiração, rejeição inicial, conflito e confirmação antes de aposentar a chave. Chromium percorre o checkout com resposta perdida, edição bloqueada e repetição correta, em desktop e celular. APIs externas são substituídas por fixtures; nenhum pagamento ou mensagem real é criado nesses testes.
