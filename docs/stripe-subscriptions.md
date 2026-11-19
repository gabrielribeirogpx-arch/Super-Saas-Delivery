# Assinaturas do Fomizero com Stripe

O checkout de novas assinaturas é exibido dentro do Fomizero com Stripe Payment Element. O cadastro cria uma assinatura local inativa; somente o webhook autenticado da Stripe libera o acesso. O Fomizero ainda não possui assinantes pela Hotmart, então não há contratos a migrar.

No cadastro público com um plano selecionado, o formulário de pagamento aparece na própria etapa de cadastro, depois de criar a loja, sem exigir login antes da cobrança. Se a Stripe estiver temporariamente indisponível, a loja permanece inativa e o proprietário pode entrar nela para retomar a assinatura; repetir o cadastro não é necessário.

## Preparação na Stripe

1. Crie um produto e um preço **mensal recorrente em BRL** para cada plano (Essencial, Operação e Pro). Copie os três IDs `price_...`. O valor em centavos deve corresponder ao catálogo comercial.
2. Use primeiro o modo de teste. Configure o webhook `https://SEU_BACKEND/api/webhooks/billing/stripe` para `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid` e `invoice.payment_failed`. Copie o segredo `whsec_...`.
3. Configure **somente no backend**, em Railway, `STRIPE_BILLING_ENABLED=true`, `STRIPE_ENVIRONMENT=sandbox`, `STRIPE_ACCOUNT_ID=acct_...`, `STRIPE_PUBLISHABLE_KEY=pk_test_...`, `STRIPE_SECRET_KEY=sk_test_...`, `STRIPE_WEBHOOK_SECRET=whsec_...` e `STRIPE_OFFERS_JSON` conforme abaixo. Nunca coloque `sk_...` ou `whsec_...` em `NEXT_PUBLIC_` ou no chat.

```json
[
  {"plan_code":"essential","price_id":"price_EXEMPLO1","price_cents":9990},
  {"plan_code":"operation","price_id":"price_EXEMPLO2","price_cents":17990},
  {"plan_code":"pro","price_id":"price_EXEMPLO3","price_cents":29990}
]
```

Confira os códigos reais dos planos no banco antes de preencher o JSON. A API valida que o preço na Stripe está ativo, em BRL, recorrente mensal e com o mesmo valor em centavos. Enquanto `STRIPE_BILLING_ENABLED` estiver ausente ou `false`, o checkout atual continua atendendo novos cadastros.

Os três IDs de preços de **produção** já foram criados pelo proprietário da conta Stripe. Após conferir no painel que os valores são R$ 99,90, R$ 179,90 e R$ 299,90, respectivamente, use este valor em `STRIPE_OFFERS_JSON` no **backend de produção**:

```json
[{"plan_code":"essential","price_id":"price_1UdW3XADx7UBzQPiLHGoJ0TO","price_cents":9990},{"plan_code":"operation","price_id":"price_1UdW4QADx7UBzQPiEpw5aeez","price_cents":17990},{"plan_code":"pro","price_id":"price_1UdW51ADx7UBzQPi6aXo7ToV","price_cents":29990}]
```

Esses IDs live não funcionam com chaves de teste. Os IDs equivalentes do **modo de teste** também já foram criados. Após conferir os valores no painel, use este `STRIPE_OFFERS_JSON` no **backend de staging**, junto com `pk_test_`/`sk_test_`:

```json
[{"plan_code":"essential","price_id":"price_1UdX20ADx7UBzQPiUdhaHNZw","price_cents":9990},{"plan_code":"operation","price_id":"price_1UdX2HADx7UBzQPi1yENxQSb","price_cents":17990},{"plan_code":"pro","price_id":"price_1UdX2VADx7UBzQPiu2yWUEs3","price_cents":29990}]
```

Em produção, use `pk_live_` e uma chave `sk_live_` ou restrita `rk_live_` com permissão de leitura em Prices e Payment Intents, e gravação em Customers e Subscriptions. A criação da assinatura expande o segredo de confirmação da fatura e a Stripe exige `payment_intent_read` mesmo no `POST /v1/subscriptions`. Configure também `STRIPE_ENVIRONMENT=production` e o segredo do webhook live. Faça uma contratação de teste em staging e confirme no webhook e no painel que o acesso só foi liberado após pagamento. Os meios disponíveis no Payment Element dependem da Stripe; Pix não deve ser anunciado como recorrente antes de uma validação específica.

Não desative o webhook da Hotmart enquanto houver assinaturas antigas. A migração dos contratos existentes deve ser tratada individualmente, com cancelamento confirmado na Hotmart antes da primeira cobrança na Stripe. Revise também os textos legais e comerciais da landing antes de anunciar a troca.

## Teste em staging sem cadastro público

`/api/onboarding/sales-config` pode retornar `provider: "stripe"` e `ready: false` quando o Turnstile e os termos do cadastro público ainda não foram configurados. Isso não bloqueia o fluxo de convite. No console do **Backend - Staging**, já com `STRIPE_BILLING_ENABLED=true`, execute a partir da raiz do serviço:

```sh
python scripts/create_onboarding_invite.py --origin https://meuburger.staging.fomizero.com.br
```

O link exibido contém um token de cadastro de uso único. Abra-o apenas no navegador do operador, crie uma loja de teste com outro nome/slug e e-mail de teste, entre na loja e escolha um plano em **Minha assinatura**. Nunca publique o link de convite ou a senha. O webhook de teste precisa apontar para o domínio público do **backend de staging** antes de confirmar qualquer pagamento.
