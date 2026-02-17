# Inventário de endpoints v1

## Decisão de escopo (alinhamento de produto)

- `app/routers/tickets.py`: **entra no v1**, pois já é referenciado no fluxo operacional de delivery (`/api/orders/{id}/ticket`) para emissão de etiqueta PDF.
- `app/routers/admin_bootstrap.py`: **entra no v1 (somente DEV)**, como endpoint de bootstrap controlado por `ENV=dev` + `DEV_BOOTSTRAP_ALLOW=1`.

## Endpoints adicionados/confirmados no `app.main`

- `GET /api/orders/{order_id}/ticket` (tag: `tickets`, exige sessão admin e valida tenant).
- `POST /api/admin/bootstrap` (tag: `admin-bootstrap`, restrito a ambiente DEV e flag explícita).

## Observações de segurança

- Ticket agora exige autenticação administrativa (`admin_session`) e impede acesso cross-tenant.
- Bootstrap administrativo mantém bloqueio por ambiente/flag e não deve ser exposto em produção.
