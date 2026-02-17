# Security: mapa de dependências de autenticação e autorização

Este documento descreve como as dependências em `app/deps.py` se conectam para autenticação (authn) e autorização (authz) no backend.

## Fluxo para rotas públicas com JWT de usuário

- `get_current_user`
  - Lê o token Bearer via `oauth2_scheme`.
  - Decodifica o JWT com `decode_access_token`.
  - Extrai `user_id` (`sub` ou `user_id`) com `_extract_user_id`.
  - Busca `User` no banco.
- `require_user_tenant_access`
  - Usa `get_current_user`.
  - Permite acesso se usuário for admin/owner global.
  - Caso contrário, exige `user.tenant_id == tenant_id` da rota.

Uso principal atual:
- `app/routers/settings.py` (`/api/settings/{tenant_id}/printers`).

## Fluxo para rotas administrativas com sessão por cookie

- `get_current_admin_user`
  - Lê cookie `ADMIN_SESSION_COOKIE`.
  - Decodifica sessão com `decode_admin_session`.
  - Busca `AdminUser` ativo no banco.
  - Valida consistência de tenant da sessão.
- `require_admin_user`
  - Alias de proteção para exigir sessão admin válida.
- `require_admin_tenant_access`
  - Usa `require_admin_user`.
  - Resolve `tenant_id` por parâmetro explícito, path (`tenant_id`) ou query (`tenant_id`).
  - Exige `user.tenant_id == resolved_tenant_id`.
- `require_role(roles)`
  - Usa `require_admin_user`.
  - Faz check de tenant igual ao `require_admin_tenant_access`.
  - Depois valida o papel (`role`) permitido.
  - Registra negação por `_log_access_denied` com razões:
    - `tenant_mismatch`
    - `role_denied`

## Fluxo para telas administrativas (UI)

- `get_current_admin_user_ui`
  - Envolve `get_current_admin_user`.
  - Em falha, retorna redirect 303 para `/admin/login`.
- `require_role_ui(roles)`
  - Versão de `require_role` para UI com redirect de login.

## Convenções de nomenclatura adotadas

Para evitar ambiguidade de resolução entre funções homônimas:

- `require_user_tenant_access`: controle tenant para JWT de `User`.
- `require_admin_tenant_access`: controle tenant para sessão de `AdminUser`.

Esses nomes tornam explícito o ator autenticado em cada fluxo e reduzem risco de importar a dependência errada em routers.
