# Assinaturas do Fomizero com Stripe

O checkout de novas assinaturas é exibido dentro do Fomizero com Stripe Payment Element. O cadastro cria uma assinatura local inativa; somente o webhook autenticado da Stripe libera o acesso. As assinaturas existentes na Hotmart continuam com sua cobrança e processamento atuais. Não migre uma assinatura ativa automaticamente para evitar cobrança em duplicidade.

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

Em produção, use chaves `pk_live_`/`sk_live_`, `STRIPE_ENVIRONMENT=production` e o segredo do webhook live. Faça uma contratação de teste em staging e confirme no webhook e no painel que o acesso só foi liberado após pagamento. Os meios disponíveis no Payment Element dependem da Stripe; Pix não deve ser anunciado como recorrente antes de uma validação específica.

Não desative o webhook da Hotmart enquanto houver assinaturas antigas. A migração dos contratos existentes deve ser tratada individualmente, com cancelamento confirmado na Hotmart antes da primeira cobrança na Stripe. Revise também os textos legais e comerciais da landing antes de anunciar a troca.
