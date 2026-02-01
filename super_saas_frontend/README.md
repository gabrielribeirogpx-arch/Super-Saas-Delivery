# Super SaaS Delivery - Frontend

Frontend administrativo em **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** para consumir a API FastAPI existente.

## Requisitos

- Node.js 18+
- Backend FastAPI rodando (padrão `http://localhost:8000`)

## Instalação

```bash
cd super_saas_frontend
npm install
```

## Variáveis de ambiente

Crie um arquivo `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
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
- Rotas protegidas `/t/[slug]/...` redirecionam para `/login` caso o cookie esteja ausente.

## Como testar login local

1. No backend, garanta que o FastAPI esteja rodando em `http://localhost:8000` (CORS liberado para `http://localhost:3000`).
2. No frontend, configure `.env.local` com `NEXT_PUBLIC_API_URL=http://localhost:8000`.
3. Suba o frontend (`npm run dev`) e acesse `http://localhost:3000/login`.
4. Use o admin de desenvolvimento (ex: `admin@local` / `admin123` se o bootstrap dev estiver ativo).
5. Confirme o cookie `admin_session` em **Application → Cookies** e o redirecionamento para `/t/[slug]/dashboard`.

## Rotas principais

- `/login`
- `/t/[slug]/dashboard`
- `/t/[slug]/orders`
- `/t/[slug]/kds`
- `/t/[slug]/finance`
- `/t/[slug]/inventory`
- `/t/[slug]/reports`
- `/t/[slug]/whatsapp`
- `/t/[slug]/ai`
- `/t/[slug]/users`
- `/t/[slug]/audit`

## Observações

- O frontend não renderiza HTML no backend; toda a UI é Next.js.
- Se algum endpoint não estiver disponível no backend, ajuste o endpoint correspondente no frontend ou documente a necessidade.

## Testes manuais

- Acesse `http://localhost:3000/t/1/dashboard` e confirme que o dashboard carrega sem erros.
- Acesse `http://localhost:3000/t/login/dashboard` e confirme que há redirecionamento para `/login` (sem chamadas para a API).

## Domínios públicos (Railway)

Para habilitar o modo `https://{tenant_slug}.mandarpedido.com` no frontend:

1. No serviço do frontend no Railway, adicione o domínio wildcard `*.mandarpedido.com`.
2. Adicione também o domínio raiz `mandarpedido.com` para evitar erro quando o usuário acessar o domínio sem subdomínio.
3. Garanta que o DNS do domínio aponte para o Railway conforme as instruções do painel.

O middleware irá reescrever automaticamente os acessos para `/t/{slug}` com base no host recebido.
