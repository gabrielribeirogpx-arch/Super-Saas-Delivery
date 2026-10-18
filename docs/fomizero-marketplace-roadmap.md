# Fomizero — direção do produto e plano até marketplace

Registro de 18/10/2026. Base inspecionada: main, commit 2d02c96bb30b14a99107d4aaed4de3a07749cedb. Documento de planejamento; não altera planos, contratos, preços, permissões, produção ou cobrança.

## 1. Objetivo e decisões

O Fomizero terá dois produtos conectados:
- Canal próprio e gestão do lojista: cardápio/loja online, pedidos, operação e recursos contratados por assinatura.
- Marketplace: descoberta de estabelecimentos, compra dentro do Fomizero, pagamento nativo, acompanhamento e, progressivamente, rede de entregas.

Decisões expressas pelo fundador:
- Não limitar a proposta a um cardápio digital.
- Permitir assinatura mensal para quem quer operar seu canal e ferramentas.
- Oferecer plano Free sem mensalidade, obrigatoriamente com pagamento nativo e remuneração por pedido.
- Buscar uma das estruturas de custo mais competitivas do mercado.
- Pausar a ativação paga do Google Maps até haver orçamento disponível, continuando outras frentes.

“Menor taxa de todos os aplicativos” é objetivo de posicionamento, não resultado comprovado nem promessa publicável. Não há percentual aprovado. Comparação deve considerar mesma modalidade, serviços incluídos, método de pagamento, prazo de repasse, mensalidade e frete.

## 2. Onde estamos: evidência e limites

| Área | Evidência atual | Limite |
| --- | --- | --- |
| Multiempresa e acesso | Tenants, funções; teste manual de Operador bloqueado em revisões e owner bloqueado ao alterar tenant_id | Não constitui auditoria completa de todas as rotas/lojas |
| Loja e operação | Cardápio público, imagens, carrinho, criação de pedidos, KDS e início de entrega observados em staging | Conclusão ponta a ponta, cancelamento e consistência financeira ainda precisam de validação |
| Acompanhamento | Atualização de status e recuperação após reload foram trabalhadas nos PRs 800–802; screenshots mostram progresso | Recuperação tem cache de sessão de 30 min; histórico durável e teste final não certificados |
| Mapas/GPS | Código de cliente e entregador existe; PR 803 foi mesclado | Ativação Google, chave válida, build e teste de GPS em celular pendentes; etapa pausada |
| Planos | Catálogo essential/operation/pro, assinaturas e entitlements | Free não faz parte do catálogo atual; documento da fase 1 define observação, não enforcement comercial |
| Assinaturas | Revisão sintética, auditoria e vínculo aprovado com assinatura inativa e sem período confiável | Cobrança recorrente real e vigência confiável ainda não homologadas |
| Pagamentos de pedidos | OrderPayment, caixa e rotas de registro/alteração | Não equivalem a adquirência, confirmação bancária, split ou repasse real |
| Marketplace | Não localizado na busca/inventário inspecionado | Descoberta multiestabelecimento, checkout de marketplace, comissão, recebedores e operação comercial ainda precisam ser construídos/homologados |

Não há base para anunciar “pronto para concorrer nacionalmente” ou atribuir percentual de conclusão. Existe um MVP operacional de canal próprio; ainda faltam o motor financeiro e o produto de marketplace.

### Achado prioritário: recebimento financeiro

Em app/services/finance.py, maybe_create_payment_for_order chama create_order_payment com status="paid" a partir da forma de pagamento. Existem chamadas na criação de pedidos, inclusive app/routers/public_menu.py. Registro contábil interno não é comprovação externa.

Antes de integrar pagamentos nativos:
- Criar o pedido como awaiting_payment/pending quando exigir pagamento online.
- Só confirmar pagamento por evidência autenticada e conciliada do PSP.
- Dinheiro/POS/external payment do canal próprio exige confirmação explícita e auditável; nunca confirmar automaticamente por seleção do cliente.
- Separar status de preparo, pagamento, liquidação e repasse.
- Não migrar ou reclassificar pagamentos históricos automaticamente.

## 3. Modelo comercial proposto

Free = mensalidade zero, não custo zero por venda. Pagamento nativo deve ser uma experiência Fomizero operada por PSP apto a marketplace/split, não uma carteira ou custódia própria construída sem contrato adequado.

| Modalidade | Canal próprio | Pagamentos | Monetização |
| --- | --- | --- | --- |
| Free | Loja/cardápio e operação essencial | Somente online nativo; sem Pix manual, dinheiro, POS ou checkout externo como bypass | Comissão/taxa por transação confirmada |
| Assinatura mensal | Ferramentas e limites por plano | Política permite nativo e, se contratado, meios externos/manuais auditados | Mensalidade; proposta de comissão de plataforma zero no canal próprio, mantendo custos de processamento aplicáveis |
| Marketplace | Origem central de descoberta do Fomizero | Nativo no MVP, independentemente do plano da loja | Taxa de aquisição/marketplace por pedido, com eventual logística cobrada separadamente |

A comissão de marketplace para assinantes é uma proposta a validar, não decisão já aprovada pelo fundador. Assinatura não deve ser confundida automaticamente com aquisição gratuita de clientes no marketplace. Se houver benefício, representá-lo explicitamente na política.

Separar:
- commercial_plan: pacote de ferramentas e contrato.
- sales_channel: canal próprio ou marketplace.
- payment_policy: formas permitidas e necessidade de pagamento nativo.
- fee_policy: comissão, base, responsável por frete/desconto/estorno e versão.
- fulfillment_mode: frota da loja, retirada, mesa ou logística intermediada.

Preservar os codes existentes. Não renomear essential para free nem alterar permissões dos lojistas existentes. Criar Free e migração apenas em entrega separada, com política explícita para legacy_no_subscription.

### Regras técnicas obrigatórias para Free

- Autorizar pagamento e plano no backend, em toda entrada de pedidos, não só na interface.
- Resolver canal pelo contexto confiável; cliente não pode trocar marketplace por canal próprio para evitar taxa.
- Total, desconto, frete e comissão calculados no servidor em centavos.
- Guardar snapshot das condições comerciais por pedido; mudança de plano não altera retroativamente a taxa.
- Não enviar pedido Free à cozinha como pago antes da confirmação válida.
- Distinguir compra de assinatura (Kiwify ou outro provedor) de pagamento do consumidor pela refeição. Evento de assinatura não paga pedido.
- Idempotência para pedido, cobrança, webhook, estorno e repasse.
- Tratar expiração do Pix, cartão recusado, duplicidade, webhook atrasado/fora de ordem, estorno parcial/total, chargeback, falha de split e indisponibilidade do PSP.
- Subconta/recebedor aprovado pelo PSP antes de liberar venda nativa da loja.

## 4. Política de taxa e viabilidade

Não definir uma taxa final antes de cotações e unit economics por método/ticket.

Margem de contribuição por pedido =
receita da plataforma
- processamento/PSP
- impostos e custos variáveis aplicáveis
- perdas e estornos assumidos
- infraestrutura/comunicação/mapas variáveis
- suporte variável
- subsídio de entrega/promoção.

Se o preço for p% + valor fixo, comparar custo efetivo = (p% × ticket + valor fixo + cobranças pertinentes) / ticket. Incluir mensalidade rateada ao comparar contratos. Frete e comissão de marketplace devem aparecer separados.

Comparar Pix e cartão por ticket, prazo de repasse e número de pedidos; diferenciar entrega própria de logística oferecida pela plataforma. Sem percentuais inventados nem subsídio permanente escondido. Meta: menor custo total sustentável dentro de uma comparação documentada, não menor número isolado.

Escolher PSP com base em proposta contratual: Pix/cartão, split, aprovação de recebedores, liquidação, devoluções, chargebacks, reservas, sandbox, assinatura de webhooks, conciliação e suporte. Documentação de split não significa habilitação comercial automática. Não há PSP escolhido neste plano.

## 5. Sequência de desenvolvimento e critérios de saída

### Etapa A — regras comerciais e financeiro confiável (próxima)

Entregas:
1. Especificação versionada de Free, assinaturas, canais e políticas, preservando códigos existentes.
2. Estados de pedido/pagamento/repasse separados; retirar confirmação automática de recebimento nas novas operações apropriadas.
3. Contratos internos de PaymentIntent/Attempt, recebedor, FeePolicy e snapshot comercial; adaptador de PSP inicialmente fake/sandbox, sem dinheiro real.
4. Plano de migração para lojas legadas; observação antes de bloquear funcionalidades.
5. Casos de aceite para Free sem bypass e para assinante com meios permitidos.

Gate: revisão das políticas + testes de isolamento, valores e transições; nenhum pedido é pago só porque o cliente selecionou Pix/cartão. Nenhum bloqueio ou mudança de cobrança em produção nesta etapa.

### Etapa B — pagamento nativo em sandbox

Entregas:
- Homologar um PSP contratado/compatível.
- Cadastro/validação de recebedores e contas de destino.
- Pix e cartão tokenizado pelo provedor, sem armazenar dados sensíveis de cartão no Fomizero.
- Webhook autenticado, idempotência, tentativas/retries, reconciliação e trilha de auditoria.
- Split ou mecanismo contratual de repasse, ledger e painel de líquido/taxas.

Gate: cobrança, falha, expiração, confirmação, cancelamento, reembolso e recebimento repetido de eventos reconciliam sem cobrar/repassar duas vezes. Sandbox não prova liquidação de dinheiro real.

### Etapa C — piloto do canal próprio e SaaS

Entregas:
- Fechar pedido → KDS → saída → entregue; testar retorno, cancelamento e ausência de conexão.
- Histórico/retomada de pedidos consistente; não depender só do modal ou cache de 30 minutos.
- Separar avisos de pagamento e preparo; exibir custos e formas em português.
- Homologar assinatura real e vigência confiável antes de vendê-la como ativação automática.
- Onboarding, suporte, backup/restauração e reversão testados.
- Mapas continuam pausados; canal próprio pode ser pilotado com status e entrega própria, sem anunciar rastreio no mapa.

Gate: piloto controlado com lojistas conhecidos e operações reconciliadas. Esse é lançamento do canal próprio, não da rede nacional de marketplace.

### Etapa D — marketplace local

Entregas:
- Página/app central com endereço/região, lojas elegíveis, horário, taxa/prazo, categorias, busca e disponibilidade.
- Um restaurante por carrinho no MVP; múltiplas lojas por compra fica para depois.
- Origem do pedido registrada no servidor, pagamento nativo, política de comissão e histórico do consumidor.
- Cadastro e aprovação de lojas, suporte/cancelamento, termos e comunicação de dados/preços.
- Avaliação pós-compra e moderação básica.

Gate: um território piloto definido, oferta suficiente de lojas abertas, clientes recorrentes, pedidos entregues e margem acompanhada. Não lançar nacionalmente antes da validação local.

### Etapa E — logística e mapa (retomada da fase pausada)

Entregas:
- Retomar docs/staging-live-delivery-tracking.md.
- Entregador atribuído, autenticação, GPS autorizado, posição recente, rota/ETA comprovados e parada após entrega/logout.
- Testes com dois dispositivos, perda de sinal, recarga, permissões e eventos fora de ordem.
- Se continuidade com tela bloqueada for requisito comercial, especificar e implementar solução mobile com suporte a localização em segundo plano; PWA não comprova esse requisito.
- Regras de despacho, aceite, disponibilidade, preço do frete, responsabilidade e remuneração.

Gate: teste real da logística e custos por entrega; sem “tempo real” quando há apenas posição antiga. Pode rodar em paralelo ao marketplace quando houver orçamento, mas é dependência para anunciar logística integrada com mapa.

### Etapa F — expansão competitiva

Entregas:
- Métricas e capacidade por região: pagamento confirmado, aceite, preparo, coleta, entrega, cancelamento, recompra, suporte e margem.
- Antifraude operacional, conciliação diária, repasses, reembolsos e atendimento com responsáveis.
- Aquisição de restaurantes e consumidores, retenção, campanhas e processo de expansão.
- Testes de carga baseados no volume-alvo, monitoramento, alertas e plano de incidentes.

Gate: operação local repetível e sustentável antes de abrir novas regiões. Competir com iFood exige distribuição, oferta, logística e confiança, além de taxa e software.

## 6. Frentes que podem avançar sem os R$150 do Google

Priorizar A e o desenho/integração sandbox de B. Depois C e a descoberta local de D. Mapas não impedem desenvolver planos, políticas, pagamento simulado, checkout, taxas, conciliação, catálogo multiestabelecimento e operação.

Não são automaticamente gratuitos: PSP, verificação cadastral, adquirência, lojas mobile, suporte e logística podem ter requisitos/custos próprios. Construção com fake/sandbox não autoriza anúncio de recebimento real.

## 7. Checkpoint de mapas — PAUSADO

- Motivo: usuário decidiu aguardar disponibilidade financeira para o pré-pagamento exibido pelo Google.
- Valor exibido em 18/10/2026: R$150,00, pagamento único antecipado; confirmar condições no retorno.
- Projeto: Fomizero Staging Maps.
- PR 803 foi mesclado; não tratá-lo como rascunho pendente.
- Não há comprovação de faturamento ativo, API/chave configuradas, build aprovado ou GPS validado em celular.
- Não recriar projeto, não gerar novas contas de faturamento e não pagar automaticamente.
- Não reverter o código ou alterar produção apenas por esta pausa.
- Retomar no guia específico: confirmar faturamento/avaliação, APIs disponíveis, chave com restrições de sites/API, variável do frontend, build staging e QA com entregador atribuído.
- Produção continua sem deploy automático conforme confirmação do usuário; verificar o estado real antes de qualquer promoção.

## 8. Fontes e evidência

Inventário do projeto: briefing-pagina-vendas.md; docs/plans-subscriptions-phase1.md; app/services/plan_seed.py; app/services/finance.py; app/routers/payments.py; app/routers/public_menu.py. Código presente não substitui validação em produção.

- https://docs.pagar.me/docs/overview-marketplace — descrição de recebedores/divisão e responsabilidades; referência de arquitetura, não escolha do provedor.
- https://docs.pagar.me/reference/recebedores-1 — confirmar habilitação/condições do split com o provedor.
- https://parceiros.ifood.com.br/restaurante/como-funciona/entregas — modalidades e serviços devem ser comparáveis; taxas públicas variam conforme oferta/contrato.
- https://docs.cloud.google.com/support/docs/troubleshoot-signup?hl=pt-br — pendências do cadastro/faturamento Google.

Próxima entrega recomendada: especificação e implementação isolada das políticas comerciais/estados financeiros em staging, com provedor fake e sem mudar planos ativos, cobrança real ou produção.
