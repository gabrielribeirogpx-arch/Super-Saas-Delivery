# Marca Fomizero

Arquivos oficiais recebidos no pacote Fomizero-SVG.zip. Os oito SVGs originais foram preservados em `super_saas_frontend/public/brand/`, com os mesmos nomes e conteúdo do pacote.

| Versão | Uso |
| --- | --- |
| fomizero-horizontal.svg | Cabeçalhos claros, sidebar, acesso, recuperação, onboarding, página comercial do frontend e notificações da cozinha |
| fomizero-horizontal-branca.svg | Cabeçalhos e superfícies escuras |
| fomizero-vertical.svg | Composições verticais com maior espaço disponível |
| fomizero-simbolo.svg | Marca compacta |
| fomizero-avatar-app.svg | Ícones, favicon e área do entregador |
| fomizero-monograma-branco.svg | Monograma sobre fundos com contraste |
| fomizero-monocromatica-preta.svg | Aplicações monocromáticas claras e impressão |
| fomizero-monocromatica-branca.svg | Aplicações monocromáticas escuras |

## Aplicação no sistema

`/fomizero-logo.svg` passa a ser uma cópia da versão horizontal oficial, atualizando os componentes que já importam o arquivo. Proporção horizontal: 1350 × 375 (3,6:1). Onboarding e página comercial mantêm a altura automática. URLs diretas do login do entregador e do aviso do KDS usam a versão em `/brand/`.

Favicon/atalhos usam o avatar. PNGs de 32, 180, 192 e 512 px foram rasterizados a partir do SVG oficial; os de 180 px atendem o apple-touch-icon. O manifest do entregador mantém `id`, `start_url` e `scope` em `/driver`, com nome Fomizero Entregador e ícones PNG. Os aliases antigos de ícones também recebem o novo avatar.

A versão do service worker e a lista de recursos visuais precacheados foram atualizadas. Estratégias de rede, autenticação, fila offline e regras de negócio permanecem iguais. A exibição de ícones de apps já instalados acompanha o ciclo normal de atualização do navegador/PWA. A metadata geral passa a usar Fomizero; o manifest Driver fica no layout /driver, e manifests/identidades personalizados das lojas seguem seus fluxos existentes.

## E-mails

O backend usa `app/assets/fomizero-email-logo.png`, rasterizado do horizontal oficial em 756 × 210 px, para compatibilidade com leitores de e-mail. O cabeçalho exibe 216 × 60 px, preservando a proporção, e mantém o mesmo CID/anexo. A mudança vale para novos envios; o conteúdo de mensagens já entregues permanece no destinatário. Nenhum e-mail real foi enviado na validação.

## Publicação e limites

Publicar frontend para as telas e ícones, e backend para o novo cabeçalho dos e-mails. Não há migrações, novas variáveis ou alteração nos fluxos de pagamento e pedidos. A página comercial implementada no frontend usa a nova marca. Sites hospedados separadamente e imagens cadastradas em Hotmart/Meta têm publicação própria.

Validar no staging em celular e desktop: login, recuperação, onboarding, cabeçalho, menu, sidebar, entregador e ícones. Conferir também as imagens de e-mail em um envio autorizado posterior. Os SVGs não dependem de fontes externas e contêm apenas formas vetoriais; não houve redesenho da marca.
