# Matriz de compatibilidade de domínio/sessão

Esta matriz define o comportamento esperado de resolução de tenant, CORS e cookie de sessão admin por ambiente.

| Ambiente | Host de entrada | Resolução de tenant | Política de CORS | Política de cookie (`admin_session`) |
|---|---|---|---|---|
| **dev** | `localhost:3000` | Tenant continua disponível por path/header/query; hosts de plataforma também são reconhecidos em testes. | `CORS_ORIGINS` explícito, com fallback para `localhost:3000` e `127.0.0.1:3000`. | `Secure=false`, `SameSite=lax`, cookie host-only por padrão. |
| **stage** | `slug.<PLATFORM_BASE_DOMAINS>` | Backend e frontend extraem o label imediatamente anterior a uma base conhecida. | `allow_origin_regex` restrito às bases configuradas e HTTPS. | Cookie host-only por padrão; `Secure=true` em host público. |
| **prod** | `slug.<PLATFORM_BASE_DOMAINS>` | Mesmo fluxo de stage, sem trocar o domínio principal. | Mesmo fluxo de stage para as bases explícitas. | Cookie host-only por padrão, `Secure=true`, `SameSite=none` por padrão. |
| **stage/prod com domínio customizado** | `admin.tenant.com` / `loja.tenant.com` | Backend resolve tenant por `custom_domain` (`/public/tenant/by-host`). | Requer incluir domínio customizado em `CORS_ORIGINS` (ou regex dedicada). | Cookie host-only (sem `Domain`) para evitar vazamento entre domínios não relacionados. |

## Observações operacionais

- `PLATFORM_BASE_DOMAINS` é uma lista separada por vírgulas. Valores são normalizados e deduplicados; `BASE_DOMAIN` e `PUBLIC_BASE_DOMAIN` continuam sendo incorporados por compatibilidade.
- No frontend, o equivalente é `NEXT_PUBLIC_PLATFORM_BASE_DOMAINS`; `NEXT_PUBLIC_BASE_DOMAIN` e `NEXT_PUBLIC_PUBLIC_BASE_DOMAIN` continuam aceitos.
- `ADMIN_SESSION_COOKIE_DOMAIN` (ou `COOKIE_DOMAIN`) só deve ser usado para um host administrativo específico. Se apontar para uma base da plataforma (`.servicedelivery.com.br` ou `.fomizero.com.br`), a aplicação ignora o escopo amplo e emite cookie host-only.
- Subdomínios reservados: `www`, `app`, `api`, `admin`, `mail`, `status`, `support`, `help`, `docs`, `cdn`, `assets`, `static`, `auth`, `billing`, `webhook` e `m`.
- Tenants existentes que já tenham um desses slugs não são alterados, mas não serão resolvidos por host de plataforma. O conflito deve ser tratado manualmente antes de publicar esse tenant por subdomínio.
- Para fallback previsível no frontend, pode-se definir `NEXT_PUBLIC_DEFAULT_TENANT_SLUG`.
- Domínio customizado deve ter estratégia CORS explícita quando usar painel/admin cross-origin.
