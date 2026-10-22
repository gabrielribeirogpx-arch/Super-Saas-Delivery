# Assinaturas mensais do Fomizero com Hotmart

## Escopo e estado

Integração preparada, desligada por padrão. Não houve contratação de produto,
cobrança, uso de credenciais reais, migração de assinantes Kiwify nem deploy.
A Hotmart cobra a mensalidade do restaurante pelo uso do Fomizero. Pagamentos
por pedidos, split e a proposta Pagar.me são fluxos independentes.

Reutiliza Plan, PlanEntitlement, SubscriptionService, inbox, intenção opaca,
auditoria e isolamento por tenant. Preserva a integração e as revisões Kiwify.
Novas tabelas: onboarding_invites (hash e consumo do convite) e hotmart_subscriptions, com vínculo de conta/ambiente/assinante,
transação do período, ordenação, consulta periódica e solicitação durável de cancelamento.
Migration: 20261019_01_hotmart, após 20261018_01_native_payments.

## Jornada

1. Cadastro da loja e administrador pelo onboarding existente, com convite de uso único
   para produção. Com Hotmart habilitada,
   cria assinatura inativa, sem cobrança, período inventado ou trial automático.
   O login após o cadastro continua para /subscriptions.
2. Assinaturas > Minha assinatura mostra somente ofertas configuradas e mapeadas,
   com preço mensal e recursos reais do catálogo. Admin/owner podem contratar;
   operadores, caixa e entregadores não podem consultar/alterar billing.
3. POST /api/admin/billing/subscription/checkout recebe apenas plan_code. Tenant,
   plano interno e oferta vêm da sessão/configuração. Cria/reutiliza intenção de
   sete dias sob lock da loja; não aceita preço, URL ou tenant fornecido pelo cliente.
4. Redireciona para https://pay.hotmart.com/<checkout>, com sck opaco da intenção.
   Conferir na compra controlada que a Hotmart conserva esse parâmetro sem alteração.
   O token correlaciona a compra; não autentica usuário nem comprova pagamento.
5. Hotmart v2 envia notificação ao backend. Hottok é comparado em tempo constante,
   no header X-HOTMART-HOTTOK, antes de ler JSON. Não é assinatura HMAC do corpo.
   Requer application/json, limita a 64 KiB, rejeita duplicatas JSON e timestamps
   em segundos. Recebimento 202 só confirma persistência, não ativação.
6. Cron processa PURCHASE_APPROVED/COMPLETE com assinatura ACTIVE, produto/plano
   mapeado, assinatura externa e período pago explícito. Ativação, vínculo,
   conclusão da intenção, auditoria e processamento são atômicos. Não há fallback
   por email, telefone, preço, slug ou query de tenant.
7. A tela atualiza a cada 15 segundos. Aprovação não depende de retorno do checkout.
   Renovações usam o vínculo externo já registrado e não precisam repetir o sck.

Intenção expirada, cancelada, produto/plano divergente ou período ausente exigem
revisão; jamais concedem acesso por suposição. Período mensal aceito: início não
futuro, fim futuro e duração até 40 dias, sem derivar fim de '30 dias'. Trial,
antecipação de várias mensalidades e troca de plano não são vendidos neste fluxo.

## Configuração — valores exclusivamente no Railway

Backend e cron precisam da mesma configuração e do mesmo banco:

- HOTMART_BILLING_ENABLED=false por padrão. Habilitar primeiro em staging isolado.
- HOTMART_ENVIRONMENT=sandbox ou production; sandbox não pode rodar com ENV=production.
- HOTMART_ACCOUNT_ID: identificador interno estável para particionar a conta.
- HOTMART_HOTTOK: token real informado pela Hotmart (pelo menos 16 caracteres).
- HOTMART_CLIENT_ID, HOTMART_CLIENT_SECRET, HOTMART_BASIC: credenciais Developers;
  usar o Basic gerado pela Hotmart, sem prefixo 'Basic '. Nunca enviar no chat,
  código, URL de webhook ou frontend. OAuth usa o contrato oficial de query;
  logs httpx/httpcore são desabilitados no comando do cron e erros são sanitizados.
- HOTMART_OFFERS_JSON: array de ofertas mensais. Exemplo SOMENTE ilustrativo:

```json
[{"plan_code":"essential","product_id":"123456","plan_id":"726420","checkout_url":"https://pay.hotmart.com/SEUCHECKOUT?off=SUAOFERTA","price_cents":9990}]
```

Trocar IDs, URL e preço pelos reais. A URL aceita somente pay.hotmart.com HTTPS,
sem credenciais, fragmentos, parâmetros de retorno arbitrários ou sck predefinido.
product_id é o ID numérico de produto; plan_id é subscription.plan.id, não o código
da oferta off. O preço exibido vem dessa configuração, mas a cobrança ocorre no
checkout: conferir igualdade, moeda BRL e recorrência mensal no painel Hotmart.
Nunca anunciar o exemplo como configuração já aplicada ou proposta aceita.

O Essencial atual tem 300 pedidos/mês, 1 usuário administrativo e 1 entregador.
Estoque e outros recursos estão desabilitados no seed Essencial. Este PR não muda
preço, limites nem a matriz comercial. Não anunciar estoque incluído sem ajustar
o plano em tarefa comercial explícita. Integrações WhatsApp/GPS exigem seus serviços
próprios; assinar não fornece credenciais nem ativa serviços externos.

Preparação após deploy backend:

```sh
python -m alembic upgrade head
python scripts/check_alembic_single_head.py
# Se os planos ainda não existirem, revisar e executar o seed já existente.
python scripts/configure_hotmart_billing.py
```

O comando de configuração é idempotente e cria somente mappings ausentes;
recusa divergências. Não altera assinaturas, preços no provedor ou plano existente.
O catálogo não é semeado no startup. Flags e segredos não são gravados em banco
nem expostos pelo endpoint de assinatura.

## Cadastro comercial por convite

Em produção o onboarding existente exige ONBOARDING_API_TOKEN administrativo.
O frontend nunca recebe esse segredo. Para os primeiros restaurantes, emitir um
convite no console backend após configurar a Hotmart e as migrations:

```sh
python scripts/create_onboarding_invite.py --origin https://staging.fomizero.com.br
```

O comando imprime um link /onboarding#invite=TOKEN para compartilhar com o
restaurante convidado. O token fica no fragmento, não na query/URL enviada ao
servidor ou Referer. A página remove o fragmento e envia o token exclusivamente
no header X-Onboarding-Invite ao criar a conta. O token dura sete dias, permite
um cadastro e é armazenado no banco somente como SHA-256. O consumo e a criação
da loja compartilham a transação; falha no cadastro restaura o convite. UPDATE
condicional impede dois cadastros concorrentes. Sem convite, a proteção atual de
produção permanece. Cadastro aberto sem convite não é habilitado.

O restaurante define sua própria senha e segue para login e Minha assinatura.
O frontend deixa de gravar a senha no sessionStorage; o armazenamento legado
onboarding:auto-login não tinha consumidor e é limpo. Convites são credenciais
intencionais de cadastro: compartilhar apenas com o destinatário e não publicar
em logs/chats de suporte. Novos convites são emitidos pelo operador, não por
uma rota pública irrestrita. Não há necessidade de outro serviço de email/SMS.

## Cron e reconciliação

Serviço cron Railway separado, raiz backend, agenda `*/5 * * * *`:

```sh
python scripts/run_hotmart_billing.py
```

Processa até 50 eventos por ciclo; erros de domínio usam backoff 60s até 1h,
com até oito tentativas, depois revisão pelo operador. Falhas inesperadas preservam
recibo e rollback. Workers repetidos serializam a aplicação por evento e tenant.
Verificar logs do cron e configurar alerta de falha/fila; sem cron, notificações
permanecem persistidas e acesso não é ativado.

A cada hora por vínculo já confirmado, consulta /subscriptions e /purchases com
OAuth. Reserva a consulta antes de HTTP, até 25 vínculos por ciclo. Não mantém
transação aberta durante rede. Exige produto/plano/assinante compatíveis e compra
recorrente APPROVED/COMPLETE para recuperar renovação. Próxima cobrança isolada
não concede acesso nem estende período de uma transação antiga. Datas seguem
milissegundos conforme o contrato; exemplos em segundos não são normalizados por
heurística. Confirmar contrato observado em staging antes de produção.
API indisponível preserva acesso pago e reagenda consulta em cinco minutos.
Notificações continuam sendo o caminho rápido; reconciliação não correlaciona
primeira compra sem intenção e não busca assinantes por PII.

Inspeção administrativa sanitizada, no console backend com acesso restrito:

```sh
python scripts/inspect_hotmart_billing.py
python scripts/inspect_hotmart_billing.py --retry-event ID
```

Corrigir mapping/configuração/evidência antes de repetir. Recibos processados não
reabrem. CLI não oferece botão para inventar pagamento, período ou associação.
Eventos com correlação ausente continuam sem tenant; não são expostos a lojas.
Definir rotina de retenção operacional antes de escalar: guarda somente referências,
hash e DTO mínimo, nunca comprador/corpo completo; conservar identidades para
idempotência. Não há limpeza destrutiva automática.

## Cancelamento, atraso, estorno e recontratação

- Cancelar renovação abre confirmação e persiste solicitação com ator. Não diz que
  cancelou antes de confirmação. Cron consulta vínculo pela API e solicita
  POST /subscriptions/{subscriber_code}/cancel com send_mail=true. A API pode
  enviar o email transacional de cancelamento quando o fluxo for usado de verdade.
- Timeout, rede ou erro de API deixam a solicitação pendente. Reexecução confirma
  estado CANCELLED_BY_* já aplicado ou repete a solicitação. Uma resposta INACTIVE
  no GET, sozinha, não prova cancelamento: pode representar outra situação.
- Confirmação agenda fim do período pago; webhook SUBSCRIPTION_CANCELLATION faz
  o mesmo sem conceder tempo adicional. Cancelamento não é reembolso.
- Ao acabar período sem cancelamento, fica past_due, sem carência inventada.
  Renovação paga posterior recupera acesso. Cancelada no período expira no fim.
- Refund/chargeback da transação atual encerra o acesso comercial. Reembolso
  parcial/inconsistente ou histórico não derruba outro período: vai para revisão. Cancelamento das próximas
  cobranças após refund/chargeback usa a fila e aguarda confirmação do provedor. Este código não solicita
  devolução bancária nem altera financeiro de pedidos.
- Nova contratação após estado terminal exige outra intenção e prova paga. Reusa
  a linha interna, preserva auditoria e substitui vínculo externo explicitamente
  via SubscriptionService.restart_subscription. Webhook antigo não reabre contrato.
- Não há mudança de plano ou migração Kiwify automática. Assinatura de outro provider,
  mesmo inativa, exige migração explícita para evitar cobrança duplicada.

## Acesso e compatibilidade

Novos contratos Hotmart inativos/vencidos/estornados não recebem novos pedidos.
A admissão e quota mensal são verificadas em get_next_daily_order_number, caminho
compartilhado pelo cardápio, API administrativa e conversa WhatsApp. A criação de rascunhos pela ferramenta
de IA aplica a mesma admissão antes de criar pedido. Lock da loja
serializa contagem em PostgreSQL. Pedidos existentes continuam operáveis; financeiro,
histórico e tela de assinatura permanecem acessíveis para regularizar a conta.

Tenants legados e assinaturas Kiwify não mudam de política. Contratos Hotmart
aplicam limites de equipe/entregadores e recursos pelas APIs, incluindo caminhos
alternativos, reativação e troca de função. Ver [travas por plano](plan-access.md).
Atualmente não há trial grátis automático de 14 dias nem promoção de três meses.

## Validação para liberar vendas

1. Confirmar com Hotmart aceitação da assinatura de software Fomizero, taxas,
   regras de reembolso, cadastro e conta apta a receber.
2. Criar produto recorrente mensal e oferta/preço reais, em BRL. Conferir recursos
   do plano comercial. Não usar Parcelado/Smart Installment como mensalidade.
3. Separar credenciais/conta/configuração staging e produção. Usar ambiente sandbox
   suportado pela conta; se a Hotmart não disponibilizar compra de checkout em
   sandbox, combinar transação controlada e reembolso autorizado, sem supor venda real.
4. Configurar webhook HTTPS no domínio do BACKEND:
   /api/webhooks/billing/hotmart, v2.0.0; selecionar PURCHASE_APPROVED,
   PURCHASE_COMPLETE, PURCHASE_DELAYED, PURCHASE_CANCELED, PURCHASE_REFUNDED,
   PURCHASE_CHARGEBACK e SUBSCRIPTION_CANCELLATION. Hottok somente no header.
5. Fazer compra controlada a partir de loja nova, validar sck, produto/plano,
   período, uma ativação, acesso e histórico. Retorno do checkout pode ser fechado;
   voltar a Minha assinatura e verificar processamento independente.
6. Testar renovação, cancelamento, timeout/reexecução, fim de acesso, refund e
   duplicação. Verificar cron real, logs sem segredos e proteção compartilhada
   de tráfego no edge (limitador do ingresso é por processo).
7. Revisar Termos/Privacidade, política de cancelamento, suporte e emissão fiscal
   com responsáveis. Somente após esses passos liberar produção e anunciar preço.

## Diagnóstico do simulador e teste sem cobrança

O teste padrão do painel Hotmart pode enviar produto `0`, plano `123`, aprovação
de 2017 e nenhuma `purchase.date_next_charge`. Não é comprovação de mensalidade
paga: os eventos pagos desse exemplo retornam HTTP 422 e não ativam acesso.
Não cadastrar esses IDs como ofertas reais, inventar datas nem responder sucesso
apenas para encerrar as retentativas. O painel pode marcar eventos não pagos como
entregues mesmo quando o worker os separa para revisão por falta de vínculo.

O adapter aceita `purchase.sckPaymentLink` e `purchase.origin.sck` como origem do
mesmo token opaco criado pelo checkout autenticado do Fomizero. Se ambos vierem,
devem coincidir. `COMPLETED`, observado no simulador, é normalizado para o valor
documentado `COMPLETE`; isso não remove a exigência de status ACTIVE, datas,
produto/plano mapeados e vínculo com uma intenção válida da loja correta.

Para diagnosticar um JSON exportado, sem banco, credenciais ou chamadas externas:

```sh
python scripts/validate_hotmart_notification.py < notification.json
```

O comando não exibe o payload ou dados pessoais. Saída `VALID SHAPE ONLY` valida
somente o formato: não autentica o remetente, não verifica pagamento, mapeamento,
validade temporal ou posse da intenção e não ativa assinatura. Um exemplo sem
próxima cobrança retorna `INVALID: hotmart_paid_period_missing` (exit 1).

O teste de ativação controlada usa SQLite temporário, relógio fixo e API simulada:

```sh
python -m pytest -q tests/test_hotmart_billing.py
```

Inclui ingresso autenticado, persistência, worker, COMPLETE/COMPLETED e os dois
campos de correlação, repetição sem dupla ativação e isolamento entre duas lojas.
Ausência de datas, tokens divergentes/desconhecidos e status não pago não liberam
acesso. Isso não substitui autenticação real da API nem o teste ponta a ponta de
checkout/renovação da conta. Não enviar notificações sintéticas ao banco de vendas.

No Railway, usar cron `*/5 * * * *`: o intervalo mínimo é cinco minutos, com
possíveis atrasos. A ativação via esse cron não é imediata. Deixar Healthcheck Path
vazio e confirmar que cada execução encerra; execução sem pendências não comprova
autenticação na API. Ver https://docs.railway.com/cron-jobs.

## Referências oficiais consultadas em 19/10/2026

- https://developers.hotmart.com/docs/en/2.0.0/webhook/purchase-webhook/
- https://developers.hotmart.com/docs/en/2.0.0/webhook/cancel-subscription-webhook/
- https://developers.hotmart.com/docs/pt-BR/v1/subscription/get-subscribers/
- https://developers.hotmart.com/docs/es/v1/subscription/get-subscription-purchases/
- https://developers.hotmart.com/docs/en/v1/subscription/cancel-subscription/
- https://developers.hotmart.com/docs/en/start/app-auth/
- https://developers.hotmart.com/docs/en/changelog
- https://developers.hotmart.com/docs/en/tutorials/checkout-elements/

A documentação pública dá base ao adapter, mas não substitui validação da conta
real e dos payloads de staging. Nenhuma chave real foi usada nos testes locais.
