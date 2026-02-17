# Onboarding Multi-Tenant V1

Este fluxo permite criar um novo tenant com admin owner e dados iniciais para começar a operar rapidamente.

## Backend

### 1) Criar tenant seguro em produção

`POST /api/onboarding/tenant`

Payload:

```json
{
  "business_name": "Restaurante Exemplo",
  "slug": "restaurante-exemplo",
  "custom_domain": "loja.exemplo.com",
  "admin_name": "Dono",
  "admin_email": "owner@exemplo.com",
  "admin_password": "senha-segura-123"
}
```

Comportamento:
- Gera slug automaticamente quando `slug` não é enviado.
- Garante unicidade de slug (com sufixo automático `-2`, `-3`...).
- Valida unicidade de domínio personalizado.
- Cria usuário admin com role `owner`.
- Em `ENV=production`, exige header `x-onboarding-token` igual ao `ONBOARDING_API_TOKEN`.

Resposta:

```json
{
  "tenant_id": 12,
  "slug": "restaurante-exemplo",
  "custom_domain": "loja.exemplo.com",
  "business_name": "Restaurante Exemplo",
  "admin_email": "owner@exemplo.com"
}
```

### 2) Seed inicial automática

Após criação do tenant, a API também cria:
- Categoria padrão: `Mais pedidos`
- Item exemplo: `Hambúrguer da Casa`
- Configuração inicial de negócio em `tenant_public_settings`:
  - `theme = dark`
  - `primary_color = #2563eb`

### 3) Disponibilidade de slug/domínio

`GET /api/onboarding/availability?slug=restaurante-exemplo&custom_domain=loja.exemplo.com`

Retorna se os identificadores estão disponíveis.

## Frontend

### 4) Fluxo simples de criação

Página: `GET /onboarding`

Fluxo:
1. Usuário informa dados da loja e admin.
2. Opcionalmente consulta disponibilidade de slug/domínio.
3. Frontend chama `POST /api/onboarding/tenant`.
4. Em sucesso, autentica automaticamente usando `/api/admin/auth/login`.
5. Redireciona para dashboard em `/t/{slug}/dashboard`.

A página de login (`/login`) agora também possui link para criação de loja.

## Resultado esperado

Novo restaurante cria conta com owner, menu inicial e configurações básicas em minutos, já entrando direto no dashboard administrativo.
