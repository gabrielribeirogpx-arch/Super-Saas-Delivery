# Briefing para página de vendas — Fomizero

Análise do repositório `gabrielribeirogpx-arch/Super-Saas-Delivery`, branch `main`, commit `974b63d3e8fddcaf75f154876988a1f1a1e2699d`, em 05/10/2026.

**Critério:** inventário do repositório e análise estática de documentação, rotas registradas, serviços, modelos, migrações, telas, componentes, configurações e testes. Código presente não comprova disponibilidade em produção. Não foram realizados pedidos reais, chamadas às integrações, testes de pagamento nem medições de desempenho. Benefícios e perfil comercial deduzidos estão marcados como **(inferido)**. Dados de exemplo não são prova social.

Para tornar os caminhos legíveis, **B/** significa `Super_SaaS_ Burger_backend/` e **F/** significa `super_saas_frontend/`. Todos os caminhos abaixo são relativos à raiz do projeto.

## 1. Produto

- **Nome do SaaS:** Fomizero, conforme o título “Bem-vindo ao Fomizero” e a logo usada no login, cadastro e menu lateral: `F/app/login/page.tsx`, `F/app/onboarding/page.tsx`, `F/components/sidebar.tsx`, `F/public/fomizero-logo.svg`. A grafia comercial definitiva é **NÃO ENCONTRADO**: README, relatórios, manifesto e metadados ainda usam “Super SaaS Delivery” e “Service Delivery Driver”.
- **O que faz, em 1 frase:** reúne cardápio digital, recebimento e acompanhamento de pedidos, organização da cozinha, entregas e controles de gestão para restaurantes e lanchonetes. Evidência: `F/components/sidebar.tsx`, `B/app/main.py`, `B/app/routers/`.
- **Problema principal que resolve:** administrar o caminho do pedido, da escolha no cardápio até a entrega, com informações reunidas para a equipe **(inferido)**. Redução de desorganização e retrabalho é um benefício possível, sem resultado medido no repositório.
- **Para quem é:** donos e gestores de restaurantes, hamburguerias e lanchonetes com delivery próprio **(inferido)**, apoiado pelo cadastro “Nome do restaurante”, pelo exemplo de hambúrguer, pelas telas de cozinha e entregadores. Fontes: `F/app/onboarding/page.tsx`, `B/app/routers/onboarding.py`, `F/app/(admin)/kds/page.tsx`, `F/app/driver/`.
- **Usuários envolvidos:** gestor, atendimento/caixa, cozinha, entregadores e clientes finais. Existem permissões por função; isso não significa que todas as telas estejam liberadas para todos. Fontes: `B/app/deps.py`, `B/app/services/authorization_service.py`, `F/lib/authorization.ts`.
- **Foco recomendado da mensagem (inferido):** mostrar o percurso real de um pedido e como cada pessoa acompanha sua etapa. Evitar promessas de aumento percentual de vendas, eliminação de erros ou economia garantida.

## 2. Funcionalidades

As cinco funcionalidades em negrito são as prioridades recomendadas para venda **(inferido)**. Todos os benefícios nesta tabela são interpretações comerciais **(inferido)**, não resultados comprovados.

| Funcionalidade | O que faz (técnico) | Benefício para o cliente (em linguagem de negócio) | Onde está no código |
|---|---|---|---|
| **1. Cardápio digital com pedido online** | Exibe categorias, produtos, imagens e preços; mantém carrinho e cria pedidos com dados do cliente, entrega ou retirada. | Permite ao cliente escolher e enviar seu pedido pelo link da loja. | `F/components/PublicMenu/PublicMenuPage.tsx`, `F/components/storefront/`, `F/components/CheckoutModal/index.tsx`, `F/app/checkout/page.tsx`, `B/app/routers/public_menu.py` |
| **2. Gestão central de pedidos** | Lista pedidos, itens e estados; permite mudanças de etapa e apresenta numeração diária e paginação. | Dá à equipe uma visão do que chegou e do que precisa avançar. | `F/app/(admin)/orders/page.tsx`, `F/components/OrderCard.tsx`, `B/app/routers/orders.py`, `B/app/models/order.py` |
| **3. Painel da cozinha** | Organiza fila de preparo por área e ações para iniciar e concluir; há modo de exibição em tela grande. | Ajuda a cozinha a acompanhar pedidos e estágio de preparo. | `F/app/(admin)/kds/page.tsx`, `B/app/routers/kds.py`, `F/app/globals.css` |
| **4. Entregas e acompanhamento no mapa** | Associa entregadores, recebe coordenadas e transmite atualizações; oferece link público por token e estimativas de chegada. | Permite acompanhar a saída e o progresso da entrega. Depende de GPS, permissões, conexão e configuração dos mapas. | `F/app/(admin)/admin/[tenant_id]/delivery/page.tsx`, `F/app/driver/`, `F/components/CustomerTracking.tsx`, `F/components/tracking/TrackingMap.tsx`, `B/app/routers/driver_api.py`, `B/app/routers/public_tracking.py`, `B/app/services/delivery_service.py` |
| **5. Fidelidade, cupons e recompensas** | Configura pontos, registra movimentações, permite descontos e administra cupons e recompensas. | Oferece motivos para incentivar novas compras dos clientes. | `F/app/(admin)/marketing/`, `B/app/routers/admin_marketing.py`, `B/app/services/loyalty.py`, `B/app/routers/public_menu.py`, `B/app/models/customer_points.py`, `B/app/models/coupon.py` |
| Produtos e categorias | Cria, edita, organiza e ativa/desativa itens e categorias. | Mantém o cardápio alinhado ao que a loja vende. | `F/app/(admin)/menu/page.tsx`, `B/app/routers/admin_menu.py`, `B/app/routers/menu_categories.py`, `B/app/models/menu_item.py` |
| Adicionais e escolhas do produto | Modela grupos de opções, adicionais e limites de escolha; valida configurações no servidor. | Deixa o cliente personalizar o pedido conforme as opções da loja. | `F/components/ItemDetailSheet/index.tsx`, `B/app/routers/admin_product_config.py`, `B/app/services/product_configuration.py`, `B/app/schemas/product_configuration.py`, `B/app/models/modifier_group.py` |
| Identidade própria do cardápio | Edita cores, fontes, imagens e aparência; oferece prévia e upload de mídia. | Apresenta o cardápio com a identidade do estabelecimento. | `F/components/admin/AppearancePanel.tsx`, `F/app/(admin)/admin/appearance/page.tsx`, `F/app/(admin)/storefront-preview/page.tsx`, `B/app/api/routes/appearance.py`, `B/app/routers/storefront_upload.py` |
| Link por loja e domínio personalizado | Resolve estabelecimento pelo endereço, slug ou domínio configurado. | Permite divulgar um endereço próprio para o cardápio. Exige configuração de hospedagem e DNS. | `F/lib/platformDomains.ts`, `F/middleware.ts`, `B/app/services/tenant_resolver.py`, `B/app/routers/admin_tenant.py`, `docs/domain-session-compatibility.md` |
| Abrir/fechar loja e taxa de entrega | Persiste estado aberto/fechado, tempo informado de preparo e taxa da loja. | Comunica disponibilidade e condições do pedido. | `F/app/(admin)/minha-loja/page.tsx`, `B/app/routers/admin_store.py`, `B/app/models/tenant.py`, `B/app/routers/public_menu.py` |
| Aplicativo web do entregador | Login dedicado, disponibilidade online/offline, aceite e conclusão de entrega, localização e atalhos de navegação. | Dá ao entregador uma interface no celular para trabalhar. | `F/app/driver/`, `F/services/driverApi.ts`, `F/services/driverLocationService.ts`, `B/app/routers/driver_api.py`, `B/app/services/delivery_service.py` |
| Instalação no celular | Manifestos, service workers, avisos de instalação e página offline para experiências de cliente e entregador. | Facilita abrir pelo ícone no celular. Instalação depende do navegador; não comprova funcionamento integral sem internet. | `F/components/pwa/`, `F/public/sw.js`, `F/public/customer-sw.js`, `F/public/manifest.webmanifest`, `B/app/routers/public_pwa.py` |
| Navegação para a entrega | Abre destino no Google Maps ou Waze. | Ajuda o entregador a seguir até o endereço. | `F/services/driverNavigation.ts` |
| Cadastro e visão de clientes | Consulta histórico, valor gasto, quantidade de pedidos, recorrência, clientes VIP e inativos; inclui exportação. | Ajuda a conhecer compradores e identificar oportunidades de relacionamento. | `F/app/(admin)/customers/`, `B/app/routers/admin_customers.py`, `B/app/models/customer.py`, `B/app/services/customer_stats.py` |
| Área do cliente | Telas de perfil, endereços, histórico, descontos e pedidos; há fluxo de autenticação por código. O envio real do código está incompleto. | Pode facilitar consulta e recompra, mas a experiência com código precisa ser concluída antes de ser prometida. | `F/app/account/`, `F/app/loja/[slug]/`, `B/app/routers/store.py`, `B/app/routers/customer_auth.py` |
| WhatsApp por ação do operador | Monta mensagem por etapa e abre `wa.me` em nova janela. | Agiliza escrever uma atualização para o cliente; o operador ainda precisa enviar a mensagem. | `F/lib/orderWhatsApp.ts`, `F/tests/orderWhatsApp.test.ts`, `F/app/(admin)/orders/page.tsx` |
| WhatsApp Cloud e mensagens de pedido | Configuração por loja, webhook, envio de teste, logs e eventos que solicitam mensagens de confirmação e etapas. Há provedor simulado. | Pode manter o cliente informado sem redigitar cada atualização, condicionado à integração e ao fluxo efetivamente validado. | `F/app/(admin)/whatsapp/page.tsx`, `B/app/routers/admin_whatsapp.py`, `B/app/routers/webhook.py`, `B/app/whatsapp/`, `B/app/services/event_handlers.py`, `B/app/services/whatsapp_outbound.py` |
| Assistente de pedidos por regras; área de IA parcial | Contexto do cardápio, ferramentas para abrir pedido, adicionar item, finalizar e consultar estado; fallback por regras. `GeminiProvider.generate` retorna mensagem fixa, sem chamada real ao Gemini. | Há base para atendimento guiado. “IA generativa funcionando” não é comprovado por este código. | `F/app/(admin)/ai/page.tsx`, `B/app/ai/service.py`, `B/app/ai/tools.py`, `B/app/ai/mock_provider.py`, `B/app/ai/gemini_provider.py`, `B/app/fsm/` |
| Registro de pagamento por pedido | Registra método, valor, taxas e estados; gera movimentos de caixa para recebimento, reembolso e cancelamento. | Ajuda a acompanhar recebimentos registrados pela operação. Não equivale a receber cartão/PIX por gateway. | `B/app/routers/payments.py`, `B/app/services/finance.py`, `B/app/models/finance.py` |
| Financeiro e caixa | Mostra resumo e movimentações com filtro por período. | Permite consultar entradas e saídas registradas. Não comprova contabilidade completa. | `F/app/(admin)/finance/page.tsx`, `B/app/routers/finance.py` |
| Indicadores e relatórios | Dashboard, séries, itens mais vendidos, estoque baixo e exportações CSV. | Ajuda a acompanhar o movimento da loja e analisar dados fora do sistema. | `F/app/(admin)/dashboard/page.tsx`, `F/app/(admin)/reports/page.tsx`, `B/app/routers/dashboard.py`, `B/app/routers/reports.py` |
| Estoque, ingredientes e receitas | API para itens, movimentos e vínculo de ingredientes a produtos/adicionais; consumo vinculado ao pedido/pagamento. A tela Next analisada privilegia consulta de saldos e movimentos. | Ajuda a identificar baixo estoque e acompanhar consumo configurado. | `F/app/(admin)/inventory/page.tsx`, `B/app/routers/inventory.py`, `B/app/services/inventory.py`, `B/app/models/inventory.py` |
| Comanda em PDF e impressão configurável | Gera ticket PDF, mantém configurações por loja e contém integração de impressão Windows. | Permite disponibilizar os detalhes do pedido em comanda. Impressão física depende do ambiente e não está comprovada para qualquer impressora na nuvem. | `B/app/services/printing.py`, `B/app/routers/tickets.py`, `B/app/routers/settings.py`, `B/tests/test_webhook_print_settings.py` |
| Equipe com permissões | Gerencia usuários e entregadores, funções, estado ativo e redefinição administrativa de senha; verifica acesso no backend. | Distribui o trabalho conforme a função de cada pessoa. | `F/app/(admin)/users/page.tsx`, `F/app/(admin)/admin/[tenant_id]/delivery-users/page.tsx`, `B/app/routers/admin_users.py`, `B/app/routers/admin_delivery_users.py`, `B/app/services/authorization_service.py` |
| Histórico de ações | Registra e consulta eventos administrativos. | Ajuda a identificar quem realizou ações registradas. Não é prova de registro de absolutamente toda ação. | `F/app/(admin)/audit/page.tsx`, `B/app/routers/admin_audit.py`, `B/app/services/admin_audit.py`, `B/app/models/admin_audit_log.py` |
| Criação de nova loja | Cria estabelecimento, dono, categoria e produto de exemplo. Em produção exige token de autorização. | Reduz o trabalho inicial de cadastrar a estrutura básica. | `F/app/onboarding/page.tsx`, `B/app/routers/onboarding.py`, `docs/onboarding.md` |
| APIs e eventos | Rotas HTTP, webhook WhatsApp e canais de atualização ao vivo. Otimização de múltiplas entregas aparece em rota interna de teste. | Oferece bases técnicas para integração; não prova conector pronto para qualquer sistema nem roteirização comercial completa. | `B/app/main.py`, `B/app/routers/`, `B/app/realtime/`, `B/app/routers/internal_test_route.py`, `B/app/services/route_optimizer.py` |

## 3. Diferenciais

- **Operação conectada (inferido):** pedidos, cozinha, entregadores, caixa, estoque e clientes compartilham dados. A demonstração mais forte é acompanhar um pedido pelas etapas. Fontes: `B/app/routers/orders.py`, `B/app/routers/kds.py`, `B/app/services/delivery_service.py`, `B/app/services/finance.py`.
- **Canal próprio com identidade da loja:** cardápio personalizável e resolução por domínio, com cadastro e pedidos públicos. Fontes: `F/components/admin/AppearancePanel.tsx`, `B/app/routers/public_menu.py`, `B/app/services/tenant_resolver.py`. White-label contratual completo e remoção de todas as marcas: **NÃO ENCONTRADO**.
- **Visibilidade da entrega:** aplicativo web para entregador e acompanhamento público no mapa. Fontes: `F/app/driver/`, `B/app/routers/public_tracking.py`. Não afirmar localização contínua com aplicativo fechado ou GPS desligado.
- **Relacionamento:** histórico de clientes, pontos, cupons e recompensas. Fontes: `B/app/routers/admin_customers.py`, `B/app/routers/admin_marketing.py`. Aumento comprovado de recompra: **NÃO ENCONTRADO**.
- **Equipe e separação por estabelecimento:** regras de acesso e testes de isolamento entre lojas. Fontes: `B/app/deps.py`, `B/tests/test_rbac_tenant_enforcement.py`, `B/tests/test_authorization_deps.py`.
- Exclusividade frente a concorrentes, velocidade superior, escala máxima, disponibilidade contratada e facilidade medida: **NÃO ENCONTRADO**. Não tratar a existência de uma função como prova de que seja única no mercado.

| Integração | Evidência e condição |
|---|---|
| WhatsApp Cloud API / Meta | Código de envio e recebimento em `B/app/whatsapp/cloud_provider.py`, `B/app/routers/webhook.py` e configuração por loja. Requer credenciais; há modo simulado. `send_template` monta payload como texto com campos adicionais, não comprova envio de template oficial aprovado nem entrega em produção. |
| Link para WhatsApp | `F/lib/orderWhatsApp.ts`: mensagem pré-preenchida por `wa.me`; exige envio pelo usuário. |
| Google Maps Directions | `B/app/services/directions_service.py`: cálculo de percurso com chave e fallback estimado. |
| Google Maps e Waze | `F/services/driverNavigation.ts`: abertura externa de navegação, não sincronização de contas. |
| Mapbox | `B/app/services/geocoding_service.py`, `F/lib/mapbox.ts`: endereços/mapas, dependentes de token. |
| ViaCEP | `B/app/services/geocoding_service.py`: consulta de CEP. |
| Cloudflare R2 | `B/app/services/r2_storage.py`, `B/app/routers/storefront_upload.py`: upload de imagens mediante configuração. |
| OpenRouteService | `B/app/services/route_optimizer.py`, `B/app/routers/internal_test_route.py`: rota e otimização em endpoint interno de teste; não apresentar como módulo comercial concluído. |
| Redis | `B/app/integrations/redis_client.py`, `B/app/realtime/`: infraestrutura de atualização ao vivo, dependente de configuração. |
| Gemini | **Parcial:** provedor com resposta fixa em `B/app/ai/gemini_provider.py`; integração real ao modelo **NÃO ENCONTRADO**. |
| Stripe, Mercado Pago, Asaas, Zapier, iFood, Anota AI, Shopify, MCP | Conectores operacionais **NÃO ENCONTRADO**. Webhook WhatsApp e API HTTP não comprovam integração com esses serviços. |

## 4. Planos e preços

| Informação | Resultado |
|---|---|
| Nomes dos planos | **NÃO ENCONTRADO** |
| Preços, moeda e taxa de implantação do SaaS | **NÃO ENCONTRADO**. Valores em centavos/R$ do cardápio pertencem aos pedidos. |
| Ciclos mensal/anual e desconto anual | **NÃO ENCONTRADO** |
| Limites por plano: usuários, lojas, pedidos, armazenamento, mensagens e créditos | **NÃO ENCONTRADO** |
| Recursos bloqueados por plano | **NÃO ENCONTRADO**. Permissões por função são controle da equipe, não planos comerciais. |
| Teste grátis, plano gratuito e cartão obrigatório | **NÃO ENCONTRADO**. Cadastro de loja não define gratuidade nem prazo de teste. |
| Cupom de assinatura, garantia e reembolso da assinatura | **NÃO ENCONTRADO**. Os cupons existentes descontam compras no restaurante. |
| Gateway e checkout de assinatura | **NÃO ENCONTRADO** |
| Renovação, inadimplência, upgrade/downgrade, cancelamento e portal do assinante | **NÃO ENCONTRADO** |
| Comissão por pedido e custos das integrações | Política comercial **NÃO ENCONTRADO** |

**O que existe no pagamento:** `B/app/routers/payments.py` registra pagamentos de pedidos e mudanças de estado; `B/app/models/finance.py` guarda pagamentos e movimentos de caixa. A loja informa formas de pagamento no pedido. Isso não demonstra captura automática de cartão, confirmação bancária de PIX ou contratação do SaaS. Cancelamento de pagamento de pedido não é cancelamento de assinatura.

## 5. Experiência do usuário

**Caminho de cadastro até o primeiro valor percebido:**

1. Acessar `/onboarding`; informar nome do restaurante.
2. Informar nome, e-mail e senha do administrador. A tela tem duas etapas e senha mínima de oito caracteres.
3. O backend cria a loja, usuário dono, categoria “Mais pedidos” e item “Hambúrguer da Casa”. São exemplos para configurar, não um cardápio real do cliente.
4. A tela redireciona para `https://{slug}.servicedelivery.com.br/login` e grava uma intenção de login automático no `sessionStorage`. O login atual analisado não demonstra consumir essa intenção; armazenamento não é compartilhado entre origens. Portanto, entrada automática bem-sucedida **NÃO ENCONTRADO**.
5. Entrar no painel; configurar produtos, adicionais, informações da loja, imagens, taxa e aparência.
6. Abrir a prévia do cardápio e divulgar o link quando estiver configurado.
7. Receber um pedido, avançar na cozinha e acompanhar a entrega. **Primeiro valor sugerido (inferido):** ver um pedido feito no cardápio aparecer na operação e chegar à etapa seguinte.

Fontes: `F/app/onboarding/page.tsx`, `F/app/login/page.tsx`, `F/lib/onboarding.ts`, `B/app/routers/onboarding.py`, `F/app/(admin)/menu/page.tsx`, `F/app/(admin)/storefront-preview/page.tsx`, `F/app/(admin)/orders/page.tsx`.

**Limitação do cadastro em produção:** `B/app/routers/onboarding.py` exige `x-onboarding-token`; a chamada em `F/lib/onboarding.ts` não o adiciona e o proxy `F/app/api/[...path]/route.ts` não o injeta. O caminho mostrado não comprova cadastro público autônomo em produção. Depende de outro provisionamento/configuração não demonstrado no projeto.

**Telas principais:**

| Tela | Explicação simples |
|---|---|
| Dashboard | Visão dos indicadores da loja. |
| Pedidos | Lista de pedidos e mudança de etapa. |
| KDS | Fila e andamento dos pedidos na cozinha. |
| Entregas / Entregadores | Distribuição, disponibilidade e acompanhamento de entregas. |
| Financeiro / Relatórios | Recebimentos e movimentos registrados, análises e exportação. |
| Estoque | Consulta de quantidade, itens baixos e movimentos. |
| Cardápio / Prévia | Edição dos produtos e visualização do que o cliente verá. |
| Marketing | Configurações de pontos, cupons e recompensas. |
| Minha Loja / Aparência | Dados, disponibilidade e identidade visual. |
| Clientes | Compradores, histórico e indicadores de relacionamento. |
| Usuários / Auditoria | Equipe, permissões e ações registradas. |
| WhatsApp / IA | Configuração e logs; área de IA possui implementação parcial. |
| Cardápio, carrinho, checkout e acompanhamento | Jornada de compra e consulta do cliente final. |

Fontes das telas administrativas: `F/components/sidebar.tsx` e páginas correspondentes em `F/app/(admin)/`. Jornada pública: `F/app/storefront/`, `F/app/checkout/`, `F/app/pedido/[token]/`, `F/app/my-orders/`, `F/components/PublicMenu/`.

**Tempo/esforço:** a interface diz “Configure sua loja em poucos minutos.” Tempo medido para operar de verdade: **NÃO ENCONTRADO**. O esforço depende do tamanho do cardápio, imagens, adicionais, equipe, domínios e integrações **(inferido)**. Treinamento, implantação assistida e prazo de atendimento: **NÃO ENCONTRADO**.

## 6. Textos já existentes

Excertos literais do próprio repositório, com variáveis preservadas:

| Texto literal | Arquivo |
|---|---|
| “Bem-vindo ao Fomizero” | `F/app/login/page.tsx` |
| “Faça login para acessar sua loja.” | `F/app/login/page.tsx` |
| “Ainda não tem loja?” / “Criar loja” | `F/app/login/page.tsx` |
| “Crie sua loja” | `F/app/onboarding/page.tsx` |
| “Configure sua loja em poucos minutos.” | `F/app/onboarding/page.tsx` |
| “Nome do restaurante” / “Nome do administrador” | `F/app/onboarding/page.tsx` |
| “Já possui conta?” / “Entrar” | `F/app/onboarding/page.tsx` |
| “Entrar na minha conta” | `F/app/account/login/page.tsx` |
| “Use somente seu telefone. Enviaremos um código para confirmar que o número é seu.” | `F/app/account/login/page.tsx` — envio real ainda incompleto |
| “Aceito os termos e a política de privacidade e entendo o uso do telefone para autenticação.” | `F/app/account/login/page.tsx` — não substitui os documentos legais |
| “Olá, {cliente}! Recebemos o seu pedido #{pedido}. Em breve iniciaremos o atendimento.” | `F/lib/orderWhatsApp.ts` |
| “Olá, {cliente}! Seu pedido #{pedido} já está sendo preparado.” | `F/lib/orderWhatsApp.ts` |
| “Olá, {cliente}! Seu pedido #{pedido} saiu para entrega.” | `F/lib/orderWhatsApp.ts` |
| “Olá, {cliente}! Seu pedido #{pedido} foi entregue. Obrigado pela preferência!” | `F/lib/orderWhatsApp.ts` |
| “Olá {customer_name}! ✅ Seu pedido #{order_number} foi confirmado. Total: {order_total}. Tempo estimado: {estimated_time}.” | `B/app/services/whatsapp_templates.py` — string formada pela concatenação dos trechos |
| “O provedor Gemini ainda não está configurado. Posso ajudar com o cardápio ou pedidos.” | `B/app/ai/gemini_provider.py` |
| “Estoque atual” / “Carregando estoque...” / “Erro ao carregar estoque.” | `F/app/(admin)/inventory/page.tsx` |

**Onde estão os demais textos:** páginas em `F/app/`, componentes em `F/components/`, mensagens de atendimento em `B/app/fsm/`, `B/app/ai/mock_provider.py` e `B/app/services/whatsapp_templates.py`; textos de idiomas em `F/src/i18n/{pt,en,es,fr}.json`. Arquivos de tradução não comprovam tradução integral do produto.

**Slogan comercial aprovado, landing page de venda do SaaS, FAQ comercial, e-mails transacionais de assinatura/boas-vindas, termos completos e política de privacidade completa: NÃO ENCONTRADO.** A raiz `F/app/page.tsx` redireciona para `/storefront`; o cardápio é uma vitrine do restaurante, não uma landing page de contratação do SaaS.

## 7. Identidade visual

| Elemento | Evidência |
|---|---|
| Vermelho principal | `#dc2626` |
| Vermelho de hover | `#b91c1c` |
| Fundo suave principal | `#fff1f2` |
| Amarelo de destaque | `#facc15` |
| Amarelo de hover | `#eab308` |
| Foco | `#fda4af` |
| Cor secundária | `#111827` |
| Fundo do cardápio atual | `#f0f2f7`; superfícies `#ffffff`; texto `#0c1422` |
| Arquivos da paleta | `F/app/globals.css`, `F/tailwind.config.ts`, `F/styles/menu-tokens.css` |
| Logo atual | `F/public/fomizero-logo.svg`, aplicada no login, onboarding e sidebar |
| Outras logos/ícones | `F/public/service-delivery-logo.svg`, `F/public/icon.svg`, `F/public/icons/driver-icon.svg`, `F/public/icons/maskable-icon.svg` |
| Fontes | Google Fonts carrega Cormorant Garamond e DM Sans em `F/app/layout.tsx`; CSS carrega Fraunces e DM Sans e declara variável Inter em `F/app/globals.css`. Uso varia por tela; manual tipográfico único **NÃO ENCONTRADO**. |
| Ícones | Biblioteca Lucide React, conforme `F/package.json` e `F/components/sidebar.tsx`; SVGs próprios em `F/public/icons/`. |

**Estilo geral:** painel claro, fundos neutros, cartões, bordas arredondadas, destaque vermelho e amarelo; cardápio com imagens, abas de categorias e componentes adaptados ao celular. Fontes: `F/app/globals.css`, `F/components/ui/`, `F/components/storefront/`, `F/components/driver/`.

**Inconsistências relevantes:** a configuração inicial de onboarding ainda usa `theme="dark"` e `primary_color="#2563eb"`; identidade do entregador ainda menciona Service Delivery. Não assumir que todas as novas lojas iniciam com a paleta Fomizero. Fontes: `B/app/routers/onboarding.py`, `F/app/layout.tsx`, `F/public/manifest.webmanifest`.

**Materiais disponíveis:** logos e ícones acima. Prints comerciais, fotos de clientes usando o produto, vídeos de demonstração e kit de marca aprovado: **NÃO ENCONTRADO**. Imagens enviadas pelas lojas são obtidas por upload/configuração e não constituem acervo comercial versionado. Sugestão de captura **(inferido)**: cardápio no celular, pedido na cozinha, rastreamento e painel de fidelidade, usando ambiente de demonstração identificado.

## 8. Prova social e números

- Depoimentos reais com autorização: **NÃO ENCONTRADO**.
- Logos de clientes contratantes autorizados: **NÃO ENCONTRADO**.
- Quantidade de lojas pagantes, usuários ativos, pedidos processados e faturamento dos clientes: **NÃO ENCONTRADO**.
- Cases com antes/depois e aumento de vendas ou recompra: **NÃO ENCONTRADO**.
- Selos, certificações e parcerias comerciais comprovadas: **NÃO ENCONTRADO**.
- Avaliações públicas verificadas, disponibilidade medida e tempo de resposta de suporte: **NÃO ENCONTRADO**.

Existem produtos e nomes de exemplo em `B/app/routers/onboarding.py`, dados de teste em `B/tests/fixtures_data.py` e `F/tests/smoke/fixtures/admin-smoke-fixtures.json`. Não publicar esses dados como clientes ou resultados reais. Gráficos do dashboard são recursos de análise da loja; não comprovam resultados da plataforma.

## 9. Informações técnicas e legais úteis para a página

**Tecnologia que pode ser traduzida para o cliente:** uso pelo navegador, interface para celular, aplicativo web instalável e dados armazenados em banco. Backend FastAPI/SQLAlchemy e frontend Next.js/React; PostgreSQL previsto para produção e SQLite para desenvolvimento. Evidência: `B/README.md`, `B/requirements.txt`, `B/app/core/database.py`, `F/package.json`, `F/components/pwa/`. Há instruções de deploy Railway; isso não comprova localidade dos dados, redundância, uptime ou backups contratados.

**Medidas implementadas identificadas:**

- Hash de senha com bcrypt e alternativa PBKDF2: `B/app/services/passwords.py`.
- Sessão administrativa assinada e opções de cookie HTTP-only, Secure e SameSite dependentes do ambiente: `B/app/services/admin_auth.py`, `B/app/middleware/admin_session.py`, `B/app/core/config.py`.
- Bloqueio após tentativas de login e registro de eventos: `B/app/routers/admin_auth.py`, `B/app/services/admin_login_attempts.py`.
- Verificação de função e vínculo com a loja no backend: `B/app/deps.py`, `B/app/services/authorization_service.py`.
- Auditoria de ações administrativas: `B/app/services/admin_audit.py`, `B/app/models/admin_audit_log.py`.
- Limitação de requisições: `B/app/core/rate_limiter.py`, `B/app/middleware/tenant_rate_limit.py`.
- Links de acompanhamento com token, validade e revogação: `B/app/services/public_tracking.py`, `B/app/routers/public_tracking.py`.
- Código de cliente com hash, expiração e limite de tentativas, mas sem envio real implementado: `B/app/routers/customer_auth.py`.
- Controle de autorização para envio e registros de mensagens: `B/app/services/whatsapp_outbound.py`, `B/app/services/customer_stats.py`.

Essas medidas não comprovam segurança absoluta ou conformidade integral com LGPD. Política de retenção, anonimização/exclusão pelo titular, encarregado/canal LGPD, contratos de tratamento, residência dos dados, backup diário e teste de recuperação: **NÃO ENCONTRADO** como políticas completas e comprovadas para oferta comercial.

**Testes e documentação:** existem testes de autorização, sessões, isolamento, pedidos/pagamentos, onboarding, mapas, rastreamento e aparência em `B/tests/`; testes de frontend em `F/tests/`; CI em `.github/workflows/ci-tests.yml`. Resultados desta revisão: os testes foram inspecionados como evidência, não executados. O script `test:smoke` de `F/package.json` apenas imprime uma mensagem, então não prova validação do frontend. `RELATORIO_TECNICO.md` está parcialmente desatualizado: afirma ausência de testes e routers de tickets/bootstrap não registrados, mas o commit analisado tem testes e registra esses routers em `B/app/main.py`. Para a página, priorizar o código atual.

**URLs e caminhos encontrados — não verificados como páginas publicadas:**

| Destino | Caminho/endereço e condição |
|---|---|
| Cadastro da loja | `/onboarding`; autorização de produção pendente de confirmação |
| Login administrativo | `/login`; redirecionamento do onboarding para `https://{slug}.servicedelivery.com.br/login` |
| Domínios de plataforma no código | `servicedelivery.com.br` e `fomizero.com.br`, em `F/lib/platformDomains.ts`; README antigo também menciona `mandarpedido.com` |
| Cardápio | `/storefront`, `/loja/[slug]` e `/p/[slug]`, conforme páginas presentes; contexto de loja varia por domínio/rota |
| Checkout do pedido | `/checkout`; não é checkout da assinatura |
| Consulta de pedido | `/pedido/[token]`, `/my-orders/[trackingToken]` |
| Login do cliente | `/account/login` e `/account/verify`; envio real do código incompleto |
| Login do entregador | `/driver/login` |
| Checkout de assinatura | **NÃO ENCONTRADO** |
| Suporte comercial/oficial | **NÃO ENCONTRADO** |
| Termos e política de privacidade publicados | **NÃO ENCONTRADO** |
| URL canônica da página de vendas | **NÃO ENCONTRADO** |

**Pixels e analytics:** Meta Pixel, Google Analytics, Google Tag Manager, eventos de conversão e IDs de acompanhamento de marketing **NÃO ENCONTRADO**. Mapas Google/Mapbox, Google Fonts e métricas internas de backend não são analytics de marketing. Observabilidade interna aparece em `B/app/core/metrics.py`, `B/app/middleware/observability.py`, `B/app/routers/internal_metrics.py`.

## 10. Lacunas e perguntas

### Oferta e contratação

1. Nome/grafia comercial definitiva **NÃO ENCONTRADO**: usar Fomizero, FOMIZERO ou F0MIZER0? Qual domínio será oficial?
2. Planos, preços, moeda, ciclos e taxa de implantação **NÃO ENCONTRADO**: quais valores e condições serão publicados?
3. Limites e divisão de recursos por plano **NÃO ENCONTRADO**: quantas lojas, pessoas, pedidos, mensagens e imagens cada assinatura inclui?
4. Comissão por pedido e custos adicionais **NÃO ENCONTRADO**: existe comissão? Quem paga Meta, mapas, armazenamento e eventual provedor de IA?
5. Teste grátis, plano gratuito e exigência de cartão **NÃO ENCONTRADO**: há teste? Qual duração e quais restrições?
6. Cupons de assinatura, garantia e reembolso **NÃO ENCONTRADO**: existe política aprovada? Não confundir com descontos dos pedidos.
7. Gateway, renovação e gestão da assinatura **NÃO ENCONTRADO**: como contratar, pagar, trocar de plano e cancelar? Há fidelização ou multa?
8. Ação principal da página **NÃO ENCONTRADO**: cadastro, teste, demonstração ou conversa comercial?
9. Urgência real da oferta **NÃO ENCONTRADO**: existe prazo ou limite verdadeiro? Evitar escassez artificial.

### Jornada e disponibilidade

10. Cadastro público funcional em produção e login automático concluído **NÃO ENCONTRADO**: como será atendida a autorização exigida pelo backend e qual será o percurso entre domínios?
11. Prazo medido de implantação, treinamento e assistência **NÃO ENCONTRADO**: quem configura o cardápio? Quanto tempo leva com uma loja real?
12. Canal, horário e prazo de suporte **NÃO ENCONTRADO**: qual contato divulgar?
13. Integração real ao Gemini **NÃO ENCONTRADO**: a área de IA deve ficar fora da oferta até concluir o provedor? Que atendimento foi validado ponta a ponta?
14. Envio real de código ao cliente **NÃO ENCONTRADO**: qual provedor enviará o código e quando será validado?
15. Garantia de entrega das mensagens e templates Meta aprovados **NÃO ENCONTRADO**: quais fluxos e formatos realmente funcionam com a conta de produção? Os estados em português/inglês acionam todas as mensagens esperadas?
16. White-label completo, roteirização comercial de múltiplas paradas e integrações externas citadas na seção 3 **NÃO ENCONTRADO**: o que já está liberado para venda e o que permanece interno?
17. Impressão física universal, funcionamento integral offline e GPS contínuo em segundo plano **NÃO ENCONTRADO**: quais dispositivos e cenários foram testados?

### Posicionamento e prova

18. Dores e objeções observadas em clientes reais **NÃO ENCONTRADO**: onde perdem tempo, quais ferramentas usam e por que comprariam ou recusariam?
19. Exclusividade/superioridade frente a concorrentes **NÃO ENCONTRADO**: quais comparações podem ser sustentadas com demonstração e evidências?
20. Depoimentos, logos autorizados, cases e avaliações verificadas **NÃO ENCONTRADO**: quais clientes podem aparecer na página?
21. Números reais de lojas, usuários, pedidos e resultados **NÃO ENCONTRADO**: quais dados podem ser auditados e publicados com período e fonte?
22. Slogan aprovado, FAQ comercial e e-mails de contratação **NÃO ENCONTRADO**: que promessa central e dúvidas precisam ser abordadas?
23. Prints, vídeos e kit de marca aprovado **NÃO ENCONTRADO**: quais demonstrações podem ser gravadas sem expor dados pessoais?
24. Manual tipográfico único **NÃO ENCONTRADO**: quais fontes e padrões serão adotados na página?

### Confiança, legal e mensuração

25. Termos completos e política de privacidade publicada **NÃO ENCONTRADO**: quem é o fornecedor responsável e quais URLs oficiais serão usadas?
26. LGPD completa, retenção, exclusão/anonimização, encarregado, tratamento de dados e residência dos dados **NÃO ENCONTRADO**: quais políticas e operações estão documentadas e aprovadas?
27. Backup diário, recuperação testada, disponibilidade contratual, escala e benchmarks **NÃO ENCONTRADO**: quais garantias operacionais possuem evidência?
28. Certificações, selos e parcerias comerciais **NÃO ENCONTRADO**: existe documentação e autorização para exibir?
29. Checkout de assinatura, suporte e URL canônica da página **NÃO ENCONTRADO**: quais destinos finais devem receber os botões?
30. Pixels/analytics e eventos de conversão de marketing **NÃO ENCONTRADO**: quais ferramentas serão usadas e qual política de consentimento se aplica?

**Direção para a criação da página (inferido):** demonstrar cardápio → pedido → cozinha → entrega, seguido de fidelidade e controles da loja. Usar provas visuais do que já funciona e preencher oferta, suporte e documentos legais antes de publicar. A promessa de IA generativa, pagamento online e cadastro imediato não é sustentada pelo estado analisado.
