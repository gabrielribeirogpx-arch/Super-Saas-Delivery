# Relatório Técnico — Super SaaS Delivery

## 1) Resumo geral do projeto

### Propósito da aplicação
O projeto implementa uma plataforma SaaS multi-tenant para operação de delivery, com foco em restaurantes/lanchonetes. O núcleo contempla: captação de pedidos (público e WhatsApp), gestão operacional (KDS/cozinha, pedidos, cardápio), controle administrativo (usuários, auditoria, configurações do tenant) e visão gerencial (financeiro, dashboard e relatórios). O backend expõe API HTTP em FastAPI e o frontend administrativo usa Next.js App Router.

### Público-alvo
- **Operação de loja**: equipe de atendimento/cozinha/caixa.
- **Gestores de unidades**: acompanhamento de indicadores e relatórios.
- **Clientes finais**: canais públicos de menu e criação de pedidos.
- **Ambiente multi-tenant**: suporte a múltiplas lojas por `tenant_id` e `slug`.

### Tecnologias principais
- **Backend**: FastAPI, SQLAlchemy, Pydantic, Alembic, Uvicorn, ItsDangerous, python-jose, Passlib/Bcrypt.  
- **Frontend**: Next.js 14, React 18, TypeScript, Tailwind, React Query, React Hook Form, Zod.  
- **Banco de dados**: SQLite em desenvolvimento (fallback) e PostgreSQL em produção (Railway).  
- **Integrações**: WhatsApp Cloud API (com provider mock), Gemini (com provider mock) e webhook HTTP.

---

## 2) Arquitetura do sistema

### Estrutura de pastas (macro)
- `Super_SaaS_ Burger_backend/`
  - `app/main.py` (bootstrap FastAPI e registro de routers)
  - `app/routers/` (camada HTTP/API)
  - `app/services/` (regras de domínio e orquestração)
  - `app/models/` (entidades persistidas SQLAlchemy)
  - `app/core/` (configuração, DB, utilitários de ambiente)
  - `app/ai/`, `app/whatsapp/`, `app/integrations/` (integrações externas)
- `super_saas_frontend/`
  - `app/` (rotas Next.js App Router: admin e páginas públicas)
  - `components/` (layout + UI components)
  - `lib/` (cliente API, auth, helpers)
  - `middleware.ts` (resolução por domínio/host)

### Padrões arquiteturais
- **Backend em camadas**:
  - Routers (entrada HTTP)
  - Services (negócio/aplicação)
  - Models (persistência)
- **Frontend por feature/rota** (App Router): cada área admin em `app/t/[slug]/(admin)/...`.
- **Multi-tenant por contexto**: `tenant_id` em rotas/modelos e `slug` para roteamento público/domínio.
- **Estratégia de provider** para IA e WhatsApp: seleção entre provider real e mock.

### Tecnologias por domínio
- **Frontend**: Next.js + React Query para data fetching e cache.
- **Backend/API**: FastAPI com validação Pydantic.
- **DB**: SQLAlchemy ORM + Alembic; criação automática de schema no startup em SQLite.
- **Interfaces de integração**:
  - API REST JSON
  - Webhooks (`/webhook`, `/webhook/whatsapp`, `/api/whatsapp/{tenant_id}/webhook`)
  - Exportação CSV em relatórios

---

## 3) Funcionalidades já implementadas

### Features concluídas (evidência no código)
1. **Autenticação administrativa** com login/logout/me (`/api/admin/auth/*`) e sessão assinada (`admin_session`) + token bearer retornado.  
2. **Gestão de usuários admin**: listar/criar/editar/reset de senha (`/api/admin/users`).  
3. **Auditoria administrativa**: rota de consulta (`/api/admin/audit`) e registros de ações sensíveis no backend.  
4. **Gestão de tenant**: edição de `slug`, domínio customizado e configurações públicas (`/api/admin/tenant` + `public-settings`).  
5. **Cardápio administrativo**: CRUD de categorias/itens (`/api/admin/menu/*`).  
6. **Pedidos**: criação/listagem, atualização de status, listagem de itens do pedido.  
7. **KDS**: fila por área e transições de preparo (`start`/`ready`).  
8. **Financeiro base**: pagamentos por pedido + resumo/movimentações de caixa.  
9. **Estoque**: itens, movimentações e receitas/ingredientes vinculados a itens/modificadores.  
10. **Relatórios**: resumo financeiro, séries, top itens, low stock e exportações CSV.  
11. **Canal público**: menu público e criação de pedidos (`/public/*` e legado `/api/public/*`).  
12. **WhatsApp**: configuração por tenant, logs, envio de teste e webhook (incluindo fallback/mock).  
13. **IA**: configuração por tenant, logs e execução assistida com ferramenta/fallback.

### Pontos de integração
- **Pedidos ⇄ Pagamentos ⇄ Caixa**: alteração de status de pagamento impacta movimentações financeiras.
- **Pedidos ⇄ Estoque**: baixas e consumo de ingredientes vinculados a menu/modifiers.
- **WhatsApp ⇄ Pedidos**: webhook e envio outbound com logs.
- **IA ⇄ Cardápio**: construção de contexto com menu/modifiers para assistência conversacional.
- **Frontend admin ⇄ Backend**: integração majoritariamente via `lib/api.ts` + React Query.

### Mapa de módulos
- **Admin Core**: auth, users, audit, tenant.
- **Comercial**: menu, categories, modifiers, public menu.
- **Operação**: orders, kds, delivery, tickets/printing.
- **Gestão**: finance, dashboard, reports, inventory.
- **Plataforma**: webhook, simulator, integrações AI/WhatsApp.

---

## 4) Funcionalidades pendentes / backlog

### Não iniciadas / não expostas no fluxo principal
- **Router de tickets não registrado no `main.py`**: existe `app/routers/tickets.py`, porém não está incluído com `app.include_router(...)`; endpoint fica indisponível em runtime.
- **Bootstrap admin via API não exposto**: `admin_bootstrap` é importado, mas também não é incluído no `main.py`.

### Parcialmente implementadas
- **Frontend de estoque e relatórios é predominantemente leitura**: já consome listagens e indicadores, mas não traz fluxo completo de CRUD operacional (cadastro/movimentação detalhada) na interface Next.
- **Proteção de rota híbrida**: documentação cita cookie HTTP-only como sessão principal, porém frontend também depende de `localStorage` token no `AuthGuard`; há acoplamento duplo de sessão.
- **Convivência de admin antigo em HTML server-side e novo frontend Next**: há telas HTML grandes em `routers/admin.py` e, em paralelo, SPA/admin em Next.js.

### Bugs/limitações técnicas observáveis
- **Conflito de nomes em `deps.py`**: `require_tenant_access` aparece duas vezes com semânticas diferentes (usuário comum/admin), a segunda definição sobrescreve a primeira.
- **Ausência de suíte automatizada de testes** no repositório de aplicação (além de scripts/documentação manual).
- **Dependência de criação automática de schema em SQLite** pode mascarar drift de migrations.

---

## 5) Banco de dados

### Modelos existentes (principais)
- **Tenant e identidade**: `tenants`, `users`, `admin_users`, `admin_login_attempts`, `admin_audit_log`, `tenant_public_settings`.
- **Catálogo**: `menu_categories`, `menu_items`, `modifier_groups`, `modifiers`, `menu_item_modifier_groups`.
- **Pedidos**: `orders`, `order_items`, `processed_messages`, `conversations`, `customer_stats`.
- **Financeiro**: `order_payments`, `cash_movements`.
- **Estoque**: `inventory_items`, `inventory_movements`, `menu_item_ingredients`, `modifier_ingredients`.
- **Integrações**: `whatsapp_config`, `whatsapp_message_log`, `whatsapp_outbound_log`, `ai_configs`, `ai_message_logs`.

### Entidades e relacionamentos relevantes
- `orders` 1:N `order_items`.
- `orders` 1:N `order_payments`.
- `order_payments.order_id -> orders.id`.
- `inventory_movements.inventory_item_id -> inventory_items.id`.
- `inventory_movements.order_id -> orders.id` (opcional).
- `menu_items.category_id -> menu_categories.id`.
- `modifiers.group_id -> modifier_groups.id`.
- `menu_item_modifier_groups` vincula N:N entre `menu_items` e `modifier_groups`.
- `menu_item_ingredients` e `modifier_ingredients` conectam catálogo ao estoque.
- `tenant_public_settings.tenant_id -> tenants.id` (1:1 por unique).

---

## 6) Endpoints de API

A OpenAPI do app registra **89 paths**. Abaixo, lista consolidada por domínio (método + rota):

### Saúde e autenticação
- `GET /`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/login_json`
- `POST /auth/token`
- `POST /api/admin/auth/login`
- `POST /api/admin/auth/logout`
- `GET /api/admin/auth/me`

### Admin UI legado (HTML)
- `GET|POST /admin/login`
- `GET /admin/logout`
- `GET /admin/{tenant_id}/menu`
- `GET /admin/{tenant_id}/ai`
- `GET /admin/{tenant_id}/ai/logs`
- `GET /admin/{tenant_id}/customers`
- `GET /admin/{tenant_id}/dashboard`
- `GET /admin/{tenant_id}/reports`
- `GET /admin/{tenant_id}/modifiers`
- `GET /admin/{tenant_id}/inventory/items`
- `GET /admin/{tenant_id}/inventory/movements`
- `GET /admin/{tenant_id}/inventory/recipes`
- `GET /admin/{tenant_id}/users`
- `GET /admin/{tenant_id}/audit`
- `GET /admin/{tenant_id}/whatsapp`

### Admin API (tenant, usuários, auditoria)
- `GET /api/admin/audit`
- `GET|PATCH /api/admin/tenant`
- `GET|PATCH /api/admin/tenant/public-settings`
- `GET|POST /api/admin/users`
- `PUT /api/admin/users/{user_id}`
- `POST /api/admin/users/{user_id}/reset_password`

### Cardápio e adicionais
- `GET|POST /api/admin/menu/categories`
- `PUT|DELETE /api/admin/menu/categories/{category_id}`
- `GET|POST /api/admin/menu/items`
- `PUT|DELETE /api/admin/menu/items/{item_id}`
- `GET /api/menu`
- `GET|POST /api/menu/categories`
- `PUT|DELETE /api/menu/categories/{category_id}`
- `GET|POST /api/menu/{tenant_id}`
- `PUT /api/menu/{tenant_id}/{item_id}`
- `PATCH /api/menu/{tenant_id}/{item_id}/active`
- `POST /api/menu/{tenant_id}/seed`
- `GET|POST /api/modifiers/groups/{tenant_id}`
- `GET|POST /api/modifiers/groups/{tenant_id}/{group_id}/modifiers`
- `GET|POST /api/modifiers/menu/{tenant_id}/{item_id}/groups`

### Pedidos, KDS e delivery
- `GET|POST /api/orders/{tenant_id}`
- `GET /api/orders/{tenant_id}/delivery`
- `GET /api/orders/{order_id}/items`
- `PATCH /api/orders/{order_id}/status`
- `GET /api/kds/orders`
- `POST /api/kds/orders/{order_id}/start`
- `POST /api/kds/orders/{order_id}/ready`
- `GET /kds/{tenant_id}`
- `GET /painel/{tenant_id}`
- `GET /entregador/{tenant_id}`

### Financeiro, dashboard e relatórios
- `POST|GET /api/orders/{order_id}/payments`
- `POST /api/orders/{order_id}/payments/{payment_id}/status`
- `GET /api/finance/cash/summary`
- `GET /api/finance/cash/movements`
- `GET /api/dashboard/overview`
- `GET /api/dashboard/timeseries`
- `GET /api/dashboard/top-items`
- `GET /api/dashboard/recent-orders`
- `GET /api/reports/financial/summary`
- `GET /api/reports/sales/timeseries`
- `GET /api/reports/sales/top-items`
- `GET /api/reports/inventory/low-stock`
- `GET /api/reports/export/financial.csv`
- `GET /api/reports/export/top-items.csv`

### Estoque
- `GET|POST /api/inventory/items`
- `PATCH /api/inventory/items/{item_id}`
- `GET|POST /api/inventory/movements`
- `GET|POST|DELETE /api/inventory/menu-items/{menu_item_id}/ingredients`
- `GET|POST|DELETE /api/inventory/modifiers/{modifier_id}/ingredients`

### IA e WhatsApp
- `GET|PUT /api/admin/{tenant_id}/ai/config`
- `GET /api/admin/{tenant_id}/ai/logs`
- `GET|PUT /api/admin/{tenant_id}/whatsapp/config`
- `GET /api/admin/{tenant_id}/whatsapp/logs`
- `POST /api/admin/{tenant_id}/whatsapp/test-message`
- `GET|POST /webhook`
- `GET|POST /webhook/whatsapp`
- `GET|POST /api/whatsapp/{tenant_id}/webhook`

### Público e simulação
- `GET /public/tenant/by-host`
- `GET /public/menu`
- `POST /public/orders`
- `GET /api/public/{slug}/menu`
- `POST /api/public/{slug}/orders`
- `POST /simulator/mensagem`

### Parâmetros e respostas esperadas (padrão)
- **Parâmetros**: combinação de `path` (`tenant_id`, `order_id`, `slug`) + `query` (filtros de período, limites, tenant) + `body` JSON.
- **Respostas**: predominantemente JSON com schemas Pydantic; alguns endpoints retornam HTML (`/admin/*`, `/kds/*`, `/entregador/*`) e CSV em relatórios de exportação.

---

## 7) Estado atual do frontend

### Páginas configuradas
- **Admin autenticado** (`/t/[slug]/...`): dashboard, pedidos, kds, financeiro, estoque, relatórios, cardápio, WhatsApp, IA, usuários, auditoria, settings/minha loja e prévia de storefront.
- **Público**: `/t/[slug]`, `/p/[slug]`, `/loja/[slug]`, `/[slug]/mobile/home`.
- **Login**: `/login`.

### Proteção de rotas
- O layout admin usa `AuthGuard` no client e redireciona para `/login` se não houver token no `localStorage`.
- Há middleware para reescrita de host/domínio em `/t/{slug}`.
- Backend também valida sessão por cookie/Authorization em rotas admin.

### Integração frontend-backend
- Camada centralizada em `lib/api.ts`, com `credentials: 'include'`, suporte a bearer token e tratamento de erros via `ApiError`.
- Uso consistente de React Query para carregar dados por módulo.

---

## 8) Integrações externas

### WhatsApp
- Provider real via **WhatsApp Cloud API** (`graph.facebook.com/{version}/{phone_number_id}/messages`).
- Configuração por tenant (`whatsapp_config`) e logs de inbound/outbound.
- Fallback para provider mock em desenvolvimento/erro de envio.

### Serviços de IA
- Provider configurável por tenant (`ai_configs`): `gemini` ou `mock`.
- Contexto alimentado por cardápio/modifiers e execução com schema estruturado (`AssistantResponse`) + fallback de parsing.
- Persistência de logs de entrada/saída/erro em `ai_message_logs`.

### Outras integrações
- Webhooks externos (Meta/WhatsApp).
- Exportação CSV para consumo externo (BI/planilhas).

---

## 9) Pontos técnicos críticos

### Segurança e autenticação
1. **Sessão duplicada (cookie + token em localStorage)** amplia superfície de ataque (XSS impacta token localStorage).
2. **`COOKIE_DOMAIN` default em produção fixado para `.up.railway.app`** pode ser inadequado para domínio customizado e provocar falhas de autenticação cross-domain.
3. **Tokens/segredos dependentes de env** sem mecanismo explícito de rotação/secret manager no código.

### Qualidade e confiabilidade
1. **Sem testes automatizados** (unitários/integrados/E2E) no repositório da aplicação.
2. **Routers existentes não expostos** (`tickets`, `admin_bootstrap`) indicam risco de funcionalidade “morta”.
3. **Mistura de duas interfaces admin** (HTML server-side + Next.js) aumenta custo de manutenção e regressões.
4. **Sobrescrita de função em `deps.py`** (`require_tenant_access`) pode gerar comportamento inesperado e confusão de autorização.

### Documentação e operação
1. Documentação está mais orientada a testes manuais; falta contrato operacional consolidado (runbook de incidentes, SLO, observabilidade).
2. Dependência de `create_all` em cenários locais pode divergir de migrations formais.

---

## 10) Recomendações e próximos passos

### Prioridade imediata (P0)
1. **Corrigir exposição de rotas**: incluir (ou remover de forma consciente) `tickets` e `admin_bootstrap` no `main.py`.
2. **Resolver conflito de autorização** em `deps.py` (renomear e separar dependências por domínio de auth).
3. **Padronizar sessão admin**: priorizar cookie HTTP-only como fonte única (evitar depender de token em `localStorage`).
4. **Cobrir autenticação e autorização com testes automatizados** mínimos (login, tenant mismatch, role denial).

### Curto prazo (P1)
1. **Unificar a estratégia de frontend admin**: escolher Next.js como padrão e descontinuar gradualmente telas HTML legadas.
2. **Adicionar suíte de testes**:
   - Backend: pytest + testes de contrato para endpoints críticos.
   - Frontend: testes de integração de páginas-chave e fluxo de login.
3. **Observabilidade**: logs estruturados, correlação de request-id e métricas básicas (latência, erro por endpoint).

### Médio prazo (P2)
1. **Fortalecer governança de dados**: políticas de retenção para logs de IA/WhatsApp e mascaramento de dados sensíveis.
2. **Pipeline CI/CD**:
   - lint + typecheck + tests obrigatórios em PR,
   - validação de migrations,
   - build de artefatos frontend/backend,
   - smoke test pós-deploy.
3. **Documentação operacional**:
   - ADRs de arquitetura,
   - diagrama de contexto e componentes,
   - playbook de rollback e recuperação.

### Documentos e pipelines recomendados
- `docs/architecture.md` (camadas, fluxos, multi-tenant).
- `docs/api-contract.md` (rotas, payloads, códigos de erro).
- `docs/security.md` (modelo de ameaça, sessão, cookies, CORS, RBAC).
- Workflow CI com etapas: `backend lint/test`, `frontend lint/build`, `migration check`, `openapi diff`.

---

## Metodologia de análise
Este relatório foi produzido a partir da leitura direta do código-fonte backend/frontend, da inspeção de modelos/rotas e da geração local da OpenAPI da aplicação para inventário de endpoints.
