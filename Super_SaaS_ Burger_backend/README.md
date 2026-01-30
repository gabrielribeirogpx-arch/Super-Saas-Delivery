# Super SaaS Burger Backend

## Deploy no Railway

### Variáveis de ambiente (Railway)

Obrigatórias:

- `DATABASE_URL` (Postgres do Railway)
- `JWT_SECRET_KEY`
- `ADMIN_SESSION_SECRET`

WhatsApp (produção):

- `WHATSAPP_VERIFY_TOKEN` (fallback quando o tenant não tiver `verify_token`)
- `META_WA_ACCESS_TOKEN` (se for usar envio via WhatsApp Cloud)
- `META_WA_PHONE_NUMBER_ID` (WhatsApp Cloud)
- `META_API_VERSION` (opcional, padrão `v19.0`)

Configuração adicional:

- `CORS_ORIGINS` (lista separada por vírgula, ex: `https://meu-front.vercel.app`)
- `ENV=production`
- `ADMIN_SESSION_COOKIE_SECURE=1`

Desenvolvimento local:

- Se `DATABASE_URL` não estiver configurada, usa SQLite `sqlite:///./super_saas.db`.
- Para criar admin em DEV, defina `DEV_ADMIN_EMAIL` e `DEV_ADMIN_PASSWORD`.

### Start command (Railway)

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Migrations / init do schema

O backend cria as tabelas automaticamente ao iniciar (`Base.metadata.create_all`).
Se preferir inicializar antes do boot (por exemplo, em um Deploy Hook):

```bash
python -c "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

Para mudanças manuais no SQLite (apenas DEV), veja `MIGRATIONS.md`.

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
