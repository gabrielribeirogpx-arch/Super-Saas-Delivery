# Motor comercial — A1: domínio isolado e simulação

Data: 18/10/2026. Implementação sem conexão com routers, checkout, banco ou PSP.
A ativação do Google Maps continua pausada no checkpoint do roadmap.

## O que esta entrega implementa

app/services/commercial_policy.py:
- Contexto explícito por tenant, plano e canal; não aceita plano ausente como Free.
- Códigos free/essential/operation/pro. Os três códigos pagos existentes são preservados.
- Free requer native_pix/native_card. Marketplace também requer pagamento nativo
  nesta proposta. Planos mensais precisam de assinatura ativa no contexto confiável.
- Canal próprio com assinatura ativa admite meios manuais/externos por política.
- Regras de comissão versionadas e com escopo exato de plano/canal/meio.
- Valores somente em centavos inteiros e percentuais em basis points
  (100 bps = 1%). Sem taxas comerciais pré-definidas.
- Base = subtotal menos desconto; frete só integra a base quando a regra o declara.
  Arredondamento half-up inteiro. Taxa não pode exceder a base.
- Snapshot imutável por pedido. Valor do lojista é antes de custos do PSP,
  impostos, remuneração do entregador e demais itens ainda não modelados.
- Meios manuais não admitem comissão recolhida por esse motor: exigem regra zero.
  A contratação/oferta comercial de comissão zero ainda depende da decisão do negócio.

app/services/fake_native_payments.py:
- Provedor fake em memória, sem rede e sem credenciais. IDs fake_.
- Criar intenção deixa pending; selecionar Pix/cartão não confirma recebimento.
- Um intent por tenant/pedido nesta fatia, com chave de idempotência por tenant.
  Payload alterado na mesma chave e segundo intent do pedido são recusados.
- Eventos simulados conferem tenant, pagamento, moeda, valor e ID.
- Transições: pending -> paid/failed/canceled; paid -> refunded.
  Estorno é total nesta fatia. Estados terminais não são ressuscitados.
- Eventos repetidos não duplicam lançamento; replay de confirmação após refund
  retorna o estado atual, sem recriar o recebimento.
- Ledger simulado registra recebimento e sua reversão. Settlement permanece
  not_settled: pagamento e repasse não são o mesmo estado.
- Snapshot recalculado na criação para rejeitar alteração dos campos de taxa/total.

## Limites de segurança e integração

Os objetos CommercialContext, FeeRule e OrderAmounts devem ser construídos
a partir de fontes confiáveis do servidor. Nenhuma API deve aceitar do cliente
subscription_active, origem de marketplace, taxa ou plano escolhido para evitar
cobrança. Este módulo puro não resolve host/canal nem verifica uma assinatura
persistida: isso é responsabilidade do serviço de integração futuro.

Eventos FakePaymentEvent são comandos de teste, NÃO webhooks autenticados.
Não expor apply_event, criar endpoint que aceite paid/refunded do navegador
nem usar o fake para liberar pedido real. Não existe marca verified=true que
substitua assinatura/consulta de um PSP.

O fake não é persistente nem seguro para concorrência; não serve como ledger
financeiro de produção. Tentativas após falha, reembolso parcial, reserva,
chargeback, webhooks reais, reconciliação, impostos e split/repasse no PSP
não estão implementados. Reordenação conflitante é recusada e exigirá
reconciliação explícita no adaptador persistente.

## O que ainda não está ativado

- Free não foi inserido em plans nem ofertado na interface.
- Catálogo, entitlements, legacy_no_subscription e clientes existentes não mudam.
- Rotas atuais NÃO estão protegidas por evaluate_payment_policy; não anunciar
  prevenção de bypass de Free ainda.
- maybe_create_payment_for_order continua com o comportamento legado. Esta
  primeira entrega não corrige nem reclassifica pagamentos existentes.
- Não há migração, alteração de DB, cobrança real ou mudança em produção.

## Testes e validação

Novas suítes:
- tests/test_commercial_policy.py: matriz de planos/canais/meios, assinatura inativa,
  centavos sem coerção, descontos/frete, rounding, escopo e snapshot congelado.
- tests/test_fake_native_payments.py: pending na criação, idempotência, tentativa
  de alterar snapshot, isolamento, valores/moeda inválidos, replay, refund,
  terminalidade e ausência de repasse.

Executar:
    pytest -q tests/test_commercial_policy.py tests/test_fake_native_payments.py
    pytest -q
    python scripts/check_openapi_contracts.py
    python scripts/check_alembic_single_head.py

O ambiente local está indisponível; a validação executável deve ser feita pelo CI.
O PR deve registrar o resultado real observado, sem tratar revisão de código como
suíte aprovada.

## Próxima entrega A2

Persistência de PaymentIntent/Attempt e snapshot com restrições por tenant/pedido,
idempotência transacional, observação do estado legado e migração controlada das
novas rotas para pending (sem reescrever o passado). Integrar regras por contexto
de servidor e observar antes de enforcement, com flag/configuração e rollout
explícito. Não remover formas de pagamento ou bloquear lojas atuais sem essa
migração. Só depois adaptar um PSP homologado em sandbox e validar evidência
de confirmação, split e reconciliação.

Referência comercial: docs/fomizero-marketplace-roadmap.md no PR #804.
As regras propostas do marketplace e os percentuais ainda precisam de aprovação
comercial antes de oferta pública; os números dos testes são fixtures, não preços.
