# Matriz de compatibilidade de domínio/sessão

Esta matriz define o comportamento esperado de resolução de tenant, CORS e cookie de sessão admin por ambiente.

| Ambiente | Host de entrada | Resolução de tenant | Política de CORS | Política de cookie (`admin_session`) |
|---|---|---|---|---|
| **dev** | `slug.localhost:3000` | Frontend extrai `slug` direto do host e reescreve para `/t/{slug}`. | `CORS_ORIGINS` explícito, com fallback para `localhost:3000` e `127.0.0.1:3000`. | `Secure=false`, `SameSite=lax`, cookie host-only por padrão (`COOKIE_DOMAIN` vazio). |
| **stage** | `slug.<PUBLIC_BASE_DOMAIN>` | Frontend extrai `slug` do subdomínio; backend resolve via host quando necessário. | `allow_origin_regex` habilitado para `https://*.PUBLIC_BASE_DOMAIN` e credenciais. | `COOKIE_DOMAIN=.PUBLIC_BASE_DOMAIN` (auto) para compartilhar sessão entre subdomínios da plataforma. |
| **prod** | `slug.<PUBLIC_BASE_DOMAIN>` | Mesmo fluxo de stage para subdomínio da plataforma. | Mesmo fluxo de stage para subdomínios HTTPS da plataforma. | `COOKIE_DOMAIN=.PUBLIC_BASE_DOMAIN` (auto), `Secure=true`, `SameSite=none` por padrão. |
| **stage/prod com domínio customizado** | `admin.tenant.com` / `loja.tenant.com` | Backend resolve tenant por `custom_domain` (`/public/tenant/by-host`). | Requer incluir domínio customizado em `CORS_ORIGINS` (ou regex dedicada). | Cookie host-only (sem `Domain`) para evitar vazamento entre domínios não relacionados. |

## Observações operacionais

- `ADMIN_SESSION_COOKIE_DOMAIN` (ou `COOKIE_DOMAIN`) explícito via ambiente tem prioridade sobre política automática.
- Para fallback previsível no frontend, pode-se definir `NEXT_PUBLIC_DEFAULT_TENANT_SLUG`.
- Domínio customizado deve ter estratégia CORS explícita quando usar painel/admin cross-origin.
