# A2 — Persistência transacional de pagamentos simulados

Data: 18/10/2026. Continuação do PR #805. Não é integração com PSP nem ativação
do Free no checkout. O Google Maps permanece pausado.

## Entregue

- NativePaymentIntent: snapshot comercial, hash, centavos, status e identificação
  explícita de simulação; dados permanecem entre sessões/processos.
- NativePaymentAttempt: tentativa inicial com idempotência por tenant/chave.
- NativePaymentEvent: eventos simulados com identidade e hash duráveis.
- NativePaymentLedger: recebimento e estorno total balanceados; unicidade impede
  dois lançamentos do mesmo tipo por intenção.
- FKs compostas impedem ligar intenção a pedido de outra loja, ou tentativa,
  evento e lançamento a pais com tenant/identidade divergente.
- Índice único adicional orders(id, tenant_id), sem alterar pedidos existentes.
- SandboxPaymentStore controla transições, consulta com filtro de tenant e locks
  de linha PostgreSQL, recomputa snapshot, confere total do pedido e recusa
  pedido com qualquer OrderPayment legado existente.
- O chamador controla commit/rollback. Savepoints tratam disputas por chave/evento.
  SQLite ganha BEGIN explícito quando necessário para que rollback do chamador
  também desfaça um savepoint que seria a primeira escrita.
- Estorno e replay de evento antigo não ressuscitam recebimento.
- Cada confirmação simulada permanece not_settled; não há repasse bancário.

A tabela obriga environment=sandbox e provider=internal_simulation. O serviço
também exige runtime test/staging e simulation_enabled=True, valores confiáveis
do servidor. Nenhuma configuração/flag de runtime é adicionada às rotas. Não
expor o comando apply_simulated_event em endpoint público ou aceitar status
paid/refunded do consumidor.

## Migração

Novo head: 20261018_01_native_payments, após 20261007_02_billing_review.
Acrescenta quatro tabelas e o índice de identidade composto em orders. Nenhum
histórico de pedido/pagamento é reescrito. Não inserir ou migrar planos Free aqui.

Downgrade exige arquivar histórico nativo: qualquer registro em uma das quatro
tabelas bloqueia a remoção. Não apagar registros financeiros para destravar
downgrade. O guard é validado online e emitido em SQL offline PostgreSQL.

A criação de índice em orders pode obter locks; revisar janela/tamanho da tabela
antes de qualquer produção. A aceitação CI não substitui backup/restauração e
migração controlada no banco staging real. Sem deploy/merge automático pelo agente.

## Validação

- test_sandbox_payment_store.py: persistência após nova sessão, replay, quote
  alterado, escopo por tenant, evento inválido, estorno, rollback e FKs.
- test_native_payment_migrations.py: upgrade/downgrade/re-upgrade, parity ORM,
  preservação de pedido e SQL PostgreSQL offline.
- test_native_payment_postgresql.py: seis casos com PostgreSQL real, incluindo
  criação concorrente, confirmação concorrente, conflito por chave, FKs e histórico.
- Job native-payments-postgresql provisiona PostgreSQL 16 descartável no GitHub
  Actions e executa a nova suíte mais tests/staging, incluindo histórico completo
  de migrations. Não usa banco/credenciais do Railway.
- Cada teste PostgreSQL cria apenas seu próprio schema aleatório e remove apenas
  esse schema ao terminar. A nova suíte recusa host não loopback ou database
  diferente de native_payments_ci. A senha do serviço CI é fictícia e descartável.

O ambiente de execução local está indisponível. Registrar no PR os resultados
efetivamente observados no CI; não considerar testes opt-in pulados como aprovados.

## Continua pendente antes do checkout real

A2 prepara o contrato persistente; não liga confirmação simulada a pedido real,
KDS, caixa, estoque ou OrderPayment antigo. maybe_create_payment_for_order
ainda tem o comportamento legado. Não anunciar recebimento/pagamento nativo
real nem prevenção de bypass Free.

Próximo corte: resolver políticas e canal pelo servidor, criar intenção de forma
atômica com pedido, retirar auto-paid nas novas rotas elegíveis e impedir avanço
operacional antes de confirmação. Definir rollout por tenant/flag e UI de pagamento.
A integração real depende da escolha/homologação do PSP, seu webhook autenticado,
reconciliação e split/repasse. Tentativas adicionais, estorno parcial, chargeback
e produção exigem entregas próprias; esta etapa suporta uma tentativa inicial
por pedido e estorno total apenas.

Antes de aplicar migração no Railway: CI completo verde, revisão da migração,
backup confirmado e aplicação controlada apenas no staging. Produção permanece
com deploy automático desativado.
