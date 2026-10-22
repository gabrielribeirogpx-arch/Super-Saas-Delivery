# Vendas diretas Fomizero — Meta Ads

Implementação preparada para `https://fomizero.com.br`. Nada neste documento habilita contratação, publica DNS ou movimenta dinheiro. O objetivo da campanha é **Vendas / site / Purchase**; cadastro e início de checkout são etapas do funil, não vendas. Não é necessário fazer uma compra paga para executar os testes automatizados, abrir o checkout e verificar a configuração. Sem uma transação real, a validação completa da cobrança, aprovação e vínculo da primeira assinatura permanece pendente e precisa ser acompanhada na primeira venda.

## Fluxo

`/` (quando habilitado) ou `/assine` → plano → `/onboarding?plan=…` → CAPTCHA e aceite dos termos → loja com assinatura Hotmart **inativa** → login no subdomínio da loja → `/subscriptions?plan=…` → clique explícito para contratar → checkout Hotmart com `sck` opaco gerado no servidor → webhook autenticado → fila durável → cron → período pago e recursos do plano.

Quando o cadastro público está habilitado, `/auth/register` é encerrado para evitar contornar CAPTCHA e aceite por uma rota antiga.

Criar conta, abrir o checkout, voltar ao site, parâmetros de URL e clicar em “Atualizar assinatura” não ativam o plano. A escolha na landing apenas destaca a oferta no painel; o comprador pode escolher outra antes de abrir o checkout. O link `/entrar` pede o identificador da loja e abre seu login, sem listar clientes ou procurar por e-mail. Guarde o endereço da loja após criar o cadastro.

As ofertas públicas vêm do mesmo catálogo e mapeamentos usados pelo checkout autenticado. Configuração incompleta impede o cadastro público e oculta os botões de contratação da landing. O cadastro por convite e o token de operador continuam disponíveis; não colocar token de operador em variável `NEXT_PUBLIC_*`.

## Configuração do backend e worker

Manter o projeto de staging separado do projeto real de produção. O ambiente do painel Railway chamado “production” não comprova que o aplicativo esteja com `ENV=production`.

Backend de produção:

- `ENV=production`
- `HOTMART_BILLING_ENABLED=true`
- `HOTMART_ENVIRONMENT=production`
- `HOTMART_ACCOUNT_ID`: partição interna exclusiva da integração de produção, diferente da sandbox; não usar o nome da loja.
- `HOTMART_CLIENT_ID`, `HOTMART_CLIENT_SECRET`, `HOTMART_BASIC`, `HOTMART_HOTTOK`: valores reais privados, somente backend/worker.
- `HOTMART_OFFERS_JSON`: conferir produto, **ID numérico de plano**, checkout e preço mensal de cada oferta na conta real. Código `off` não é ID de plano.
- `PUBLIC_SIGNUP_ENABLED=true` somente após configurar os itens seguintes.
- `PUBLIC_SIGNUP_ORIGINS=https://fomizero.com.br,https://www.fomizero.com.br` (apenas origens realmente usadas; sem caminhos).
- `TURNSTILE_SITE_KEY` e `TURNSTILE_SECRET_KEY`: criar widget Cloudflare Turnstile e autorizar os hosts de vendas. Não utilizar chaves de teste na campanha real.
- `SALES_TERMS_URL` e `SALES_PRIVACY_URL`: URLs HTTPS de documentos reais já publicados, com identificação correta do fornecedor e condições de assinatura, cancelamento, reembolso, dados pessoais e publicidade. O código não inventa documentos legais nem um nome empresarial.
- `SALES_TERMS_VERSION`: identificador de versão (até 64 letras, números, ponto, sublinhado ou hífen). O aceite fica registrado na auditoria junto do usuário e URLs; não registrar senha nem CAPTCHA.
- `SALES_SUPPORT_EMAIL`: endereço de suporte real e monitorado.
- Revisar as origens CORS existentes para aceitar os hosts usados pelo frontend e lojas.

No novo escopo de produção, executar migrações e `python scripts/configure_hotmart_billing.py`. Não reaproveitar contratos ou bindings da sandbox. O script de catálogo configura mapeamentos, não comprova preço comercial, aprovação do produto ou credenciais. A API sandbox **não transforma** links `pay.hotmart.com` em checkout sem cobrança: esses links podem cobrar valores reais.

O worker deve compartilhar banco e configuração Hotmart de produção com o backend, iniciar com `python scripts/run_hotmart_billing.py`, cron `*/5 * * * *`. Conferir execuções e fila sem eventos presos em revisão. Não expor um domínio público para o worker. Configurar webhook v2 no backend de produção em `/api/webhooks/billing/hotmart`, com o Hottok correspondente e os eventos documentados em `hotmart-subscriptions.md`.

A [verificação oficial Turnstile](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/) exige validação no servidor. O cadastro verifica CAPTCHA no servidor, valida origem exata, hostname e action `signup`; falha de provedor não cria a loja. Há um freio global de dez tentativas por minuto **por processo**, sem armazenar IPs. Ele não substitui uma regra de rate limit compartilhada no proxy/WAF; configurar proteção para `/api/onboarding/tenant` antes de tráfego pago, principalmente com múltiplas réplicas. O token de CAPTCHA expira e não pode ser reutilizado segundo o provedor. Aceite dos termos e consentimento de publicidade são separados.

## Frontend, domínio e atendimento

- `NEXT_PUBLIC_SALES_SITE_ENABLED=true`: mostra a landing na raiz da plataforma; raiz das lojas continua abrindo o cardápio por middleware.
- `NEXT_PUBLIC_PUBLIC_BASE_DOMAIN=fomizero.com.br`; revisar também `NEXT_PUBLIC_BASE_DOMAIN` e `NEXT_PUBLIC_PLATFORM_BASE_DOMAINS` para o ambiente correto.
- Configurar backend/proxy atual do frontend (`STOREFRONT_BACKEND_URL` e/ou `NEXT_PUBLIC_API_URL`) para o backend de produção, sem misturar staging.
- Configurar DNS/TLS **raiz**, `www` se usado, e wildcard das lojas. Um wildcard não cria automaticamente DNS para a raiz.
- `NEXT_PUBLIC_META_PIXEL_ID`: apenas o ID público numérico do conjunto de dados Meta. Exige novo build. Não usar um ID de exemplo. Nenhum token da API de Conversões deve entrar no frontend.
- Confirmar suporte e recuperação de acesso. Este PR não adiciona recuperação automática de senha por e-mail; é necessário um processo operacional seguro para recuperar acesso antes de vender. Nunca pedir senha atual ao cliente nem expor uma rota pública de troca de senha.

## Meta e Hotmart — configuração na conta

1. Criar uma fonte de dados Web no [Gerenciador de Eventos Meta](https://business.facebook.com/events_manager2/), vinculada ao portfólio e à conta de anúncios que serão usados. Facebook e Instagram usam o mesmo conjunto de dados.
2. Verificar `fomizero.com.br` nas configurações empresariais por um método disponível na conta, e conferir permissões de domínio, conjunto de dados, página, Instagram e anúncios.
3. Usar o mesmo ID no frontend e em Hotmart → Ferramentas → Pixel de rastreamento → produto Fomizero Delivery → Facebook + Instagram. A [documentação oficial Hotmart](https://suportehotmart.zendesk.com/hc/en-us/articles/115004826368-How-do-I-configure-the-Meta-Pixel-on-Hotmart) descreve esse fluxo e as opções avançadas.
4. Revisar no painel Hotmart os eventos e as condições de confirmação: enviar **Purchase apenas para pagamento aprovado**, não para boleto/Pix simplesmente gerado. Enviar o valor correto da oferta e BRL. Ativar a integração de servidor/API de Conversões se oferecida pela conta; token somente no campo privado da Hotmart. Se usar web e servidor, verificar deduplicação no Gerenciador de Eventos. Não adicionar outro emissor de Purchase no Fomizero ou num GTM paralelo.
5. Por padrão, o site envia `PageView` e `CompleteRegistration` após cadastro bem-sucedido; início de checkout e compra ficam na integração nativa da Hotmart. Opcionalmente, `NEXT_PUBLIC_META_CHECKOUT_SOURCE=fomizero` envia `InitiateCheckout` após o servidor fornecer uma URL válida, somente se o evento nativo equivalente for desativado na Hotmart. Não envia nome, e-mail, CPF, senha, endereço ou token de convite como propriedades. Desabilita configuração automática de eventos do Pixel. Não habilitar `NEXT_PUBLIC_META_CHECKOUT_SOURCE=fomizero` se a conta Hotmart não permitir desativar o evento nativo equivalente. Não somar duas fontes sem deduplicação.
6. O script Meta só é carregado após aceitar publicidade. A escolha é guardada por origem; ao passar para o subdomínio da loja pode haver uma nova solicitação. Sem consentimento, cadastro e contratação continuam funcionando. O cliente pode revogar pelo botão “Privacidade dos anúncios”. A Hotmart controla os cookies/consentimento no próprio checkout: revisar sua configuração e políticas separadamente.
7. Atribuição entre domínios e sob bloqueadores não é garantida. Testar no navegador móvel usado pelos anúncios. **Nunca substituir `sck` por UTM, campanha ou fbclid**: ele vincula o pagamento à loja correta. Não acrescentar scripts que leiam tokens de convite ou sobregravem esse parâmetro. A integração nativa será responsável pelo Purchase e pela atribuição disponível no checkout.
8. Criar a campanha de Vendas no site com o conjunto correto e o evento `Purchase`. URL de destino `https://fomizero.com.br/`; UTMs podem identificar campanha/anúncio sem conter dados pessoais. Usar criativos e valores coerentes com os planos publicados. Não otimizar para cadastro ou marcar eventos simulados como vendas reais.

## Validação sem transacionar assinatura

Após deploy e configuração, no terminal do **backend real**:

```sh
python scripts/check_sales_readiness.py
python scripts/check_sales_readiness.py --verify-auth
```

São verificações de leitura. A opção adicional só obtém autenticação OAuth, sem checkout, assinatura ou cobrança. A saída não imprime segredos. O resultado não comprova que DNS/Meta/cron estejam configurados, que o checkout cobre o preço correto ou que uma compra real funcione.

Conferir no navegador desktop e celular: landing; documentos e suporte; cadastro sem convite; CAPTCHA inválido recusado; aceite obrigatório; criação de loja inativa; login no host correto; plano destacado; checkout com preço/recorrência corretos e `sck` preservado; abandonar e retomar sem nova contratação; cancelamento/revisões com a bateria automatizada. Usar “Testar eventos” da Meta para conferir visita/cadastro/início de contratação e consentimento, sem enviar um Purchase fictício à campanha real. Um teste da Hotmart com produto sandbox genérico não comprova liberação de assinatura: produto, plano, correlação e período precisam ser válidos.

Acompanhar a **primeira venda real originada da campanha**: pagamento aprovado Hotmart → webhook 202 → evento processado → contrato vinculado ao tenant correto → plano e período corretos → recursos liberados → uma conversão Purchase atribuída na Meta com valor/moeda corretos. Até essa venda existir, essa última etapa deve ser declarada não comprovada, mesmo com testes automatizados passando.

Não usar saldo da loja nem pagamentos de pedidos para essa validação: a assinatura SaaS Hotmart é independente dos pagamentos dos clientes do restaurante.
