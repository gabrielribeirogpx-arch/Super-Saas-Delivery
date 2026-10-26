# Painel do restaurante no celular

Esta atualização repagina o painel administrativo, principalmente início, pedidos e cozinha. Cardápio público e área do entregador mantêm seus próprios fluxos. Não altera pedidos, pagamentos, planos, autenticação ou banco.

## Navegação

- Abaixo de 1024 px, cabeçalho fixo com a marca e barra inferior com Início, Pedidos, Cozinha, Cardápio e Mais. Acima disso, permanece a sidebar.
- Mais reúne todas as áreas em Operação, Gestão, Crescimento e Minha loja; mantém indicação de recursos pagos e restrição do perfil de entregador.
- O menu usa dialog nativo: foco contido, Escape, restauração de foco, rolagem interna e bloqueio do fundo. Fecha após navegação e ao alcançar o breakpoint desktop.
- Espaço inferior e safe areas impedem que o final das páginas fique coberto. Campos têm fonte de 16 px no mobile e controles de toque têm pelo menos 44 px. O viewport raiz volta a permitir zoom.
- O aviso sem conexão reflete o navegador; não declara disponibilidade da API nem promete operação offline.

## Telas

- Início: atalhos operacionais, indicadores em duas colunas, valores em pt-BR e listas mobile para itens e pedidos recentes. O período padrão continua sendo os últimos sete dias; não é apresentado como faturamento de hoje.
- Pedidos: resumo horizontal, filtros recolhidos no mobile e abertos no desktop. Os filtros e paginação continuam no servidor. Detalhes abrem em um dialog com apresentação de folha inferior; acima de 1680 px, permanece o painel lateral.
- Cozinha: etapas selecionáveis até 1280 px para evitar três colunas longas empilhadas. Contagens continuam visíveis; ações e polling existentes permanecem. Desktop amplo e modo TV mantêm as colunas.

## Identidade e PWA

O painel tem título e ícones Fomizero. Componentes de instalação, diagnóstico e fila offline do entregador ficam na área /driver. O painel não monta manifest ou service worker do cliente. Não foi adicionado cache offline de dados administrativos nem prometida instalação do painel como PWA.

Remove o manifest automático duplicado `app/manifest.ts`, que competia pelo endereço `/manifest.webmanifest` com o arquivo estático público. O manifest estático e o layout do entregador continuam fornecendo a identidade Driver em /driver.

## Conferência

```text
npm test
npm run test:mobile-admin:browser
npm run test:order-history:browser
```

Os scripts de navegador usam fixtures, nunca a API real. O primeiro usa `MOBILE_ADMIN_TEST_BASE_URL` (padrão http://127.0.0.1:3046) e o segundo `ORDER_HISTORY_TEST_BASE_URL`. Capturas ficam em `MOBILE_ADMIN_ARTIFACT_DIR` ou no diretório temporário do sistema. É necessário Chromium (`CHROMIUM_PATH`) e o frontend local em execução.

Verificar em staging: navegação inferior, Mais, busca/paginação de pedidos, detalhes/fechamento, mudança de status na cozinha, teclado virtual e orientação em um celular real. A suíte local Chromium cobre 320, 390, 768, 1366 e 1720 px, isolamento do perfil de entregador, foco, Escape, conectividade simulada, ausência de overflow horizontal e ausência de gravações involuntárias. Testes de viewport não substituem conferência em Safari/iOS e aparelhos reais.

Publicar somente frontend, inicialmente em staging. Não há migrações ou novas variáveis. Reverter o frontend reverte a apresentação; não exige rollback do backend.
