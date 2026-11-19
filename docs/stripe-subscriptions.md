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

Para produção, crie **novos preços no modo live**, configure chaves `pk_live_`/`sk_live_`, `STRIPE_ENVIRONMENT=production`, o segredo do webhook live e troque os IDs no JSON. Faça uma contratação de teste em staging, confirme no webhook e no painel que o acesso só foi liberado após pagamento. Os meios disponíveis no Payment Element dependem da Stripe; Pix não deve ser anunciado como recorrente antes de uma validação específica.

Não desative o webhook da Hotmart enquanto houver assinaturas antigas. A migração dos contratos existentes deve ser tratada individualmente, com cancelamento confirmado na Hotmart antes da primeira cobrança na Stripe. Revise também os textos legais e comerciais da landing antes de anunciar a troca.
