# Super SaaS Burger Backend

## WhatsApp Cloud API

### Webhook verification

O endpoint `GET /webhook/whatsapp` valida o handshake da Meta lendo os query params
`hub.mode`, `hub.verify_token` e `hub.challenge`.

**Fonte do token esperado**

1. Primeiro tenta o token salvo em `WhatsAppConfig.verify_token` do tenant resolvido.
2. Se não houver token no tenant, usa a variável de ambiente `WHATSAPP_VERIFY_TOKEN`.

**Como o tenant é resolvido**

- Prioridade: `tenant_id` (query param)
- Fallback: `phone_number_id` ou `waba_id` (query params)
- Em ambiente de desenvolvimento, se nada for enviado, usa o tenant `1` como padrão.

### Teste manual

```bash
curl "http://127.0.0.1:8000/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=super_saas_verify&hub.challenge=123"
```

Deve retornar `123`.
