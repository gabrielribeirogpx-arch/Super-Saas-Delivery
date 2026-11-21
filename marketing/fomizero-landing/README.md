# Landing pública do Fomizero

Código estático da página publicada em `fomizero.com.br`. Os arquivos servidos estão em `dist/`; não há etapa de build. O arquivo `.openai/hosting.json` identifica o projeto Sites existente.

## Fonte e publicação

A versão 15 publicada originalmente correspondia ao commit `6ec34b50eef86855db5dc0fc379545962af2b012` do repositório de origem do Sites. A revisão de conversão parte do conteúdo disponível no domínio público em 21/11/2026 e acrescenta o cardápio instalável, o app Android e o rastreio no mapa. Operação continua como oferta principal. A tela do KDS continua sendo uma captura da interface real com pedidos demonstrativos.

Este diretório serve para revisão do código pelo fluxo de PR do GitHub. **Fazer merge no GitHub não publica o domínio.** Para publicar, use o projeto Sites identificado em `.openai/hosting.json`. A landing fica separada do frontend Railway, que atende o sistema e o onboarding em `www.fomizero.com.br`.

## Medição

`dist/config.js` usa o Pixel da Meta e o ID público de GA4 `G-HDBVG6L1NT`. Na landing, o Pixel é carregado na primeira visita por padrão, exceto quando há uma preferência anterior de desativação neste navegador. A opção de desativar fica em **Preferências de privacidade**, no rodapé. O Google Analytics também é carregado na primeira visita por padrão, salvo preferência anterior de desativação. `PlanSelected` e `plan_selected` medem cliques em planos; não equivalem a início de checkout ou compra. As páginas de cardápio e checkout dos restaurantes não usam este código.

## Verificações locais

```sh
node --check dist/app.js
```

No navegador, conferir a página em largura de celular e desktop, destino dos três planos e do download Android, seção de entrega, abas da demonstração, imagem do KDS, Termos de Uso e preferências de medição.
