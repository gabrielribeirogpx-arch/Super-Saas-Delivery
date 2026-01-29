# Super SaaS Delivery - Frontend

Frontend administrativo em **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** para consumir a API FastAPI existente.

## Requisitos

- Node.js 18+
- Backend FastAPI rodando (padrão `http://127.0.0.1:8000`)

## Instalação

```bash
cd super_saas_frontend
npm install
```

## Variáveis de ambiente

Crie um arquivo `.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Rodar em desenvolvimento

```bash
npm run dev
```

A aplicação ficará disponível em `http://localhost:3000`.

## Fluxo de login

- A tela de login consome `POST /api/admin/auth/login`.
- Em caso de sucesso, o backend grava o cookie `admin_session` (HTTP-only).
- Todas as requisições do frontend usam `credentials: 'include'` para enviar a sessão.
- Rotas protegidas `/t/[tenantId]/...` redirecionam para `/login` caso o cookie esteja ausente.

## Rotas principais

- `/login`
- `/t/[tenantId]/dashboard`
- `/t/[tenantId]/orders`
- `/t/[tenantId]/kds`
- `/t/[tenantId]/finance`
- `/t/[tenantId]/inventory`
- `/t/[tenantId]/reports`
- `/t/[tenantId]/whatsapp`
- `/t/[tenantId]/ai`
- `/t/[tenantId]/users`
- `/t/[tenantId]/audit`

## Observações

- O frontend não renderiza HTML no backend; toda a UI é Next.js.
- Se algum endpoint não estiver disponível no backend, ajuste o endpoint correspondente no frontend ou documente a necessidade.
