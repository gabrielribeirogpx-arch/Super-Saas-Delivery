# Landing pública do Fomizero

Código estático da página publicada em `fomizero.com.br`. Os arquivos servidos estão em `dist/`; não há etapa de build. O arquivo `.openai/hosting.json` identifica o projeto Sites existente.

## Fonte e publicação

Esta cópia corresponde ao commit `6ec34b50eef86855db5dc0fc379545962af2b012` do repositório de origem do Sites, salvo como versão 15 e publicado. O plano Operação é a oferta principal; Essencial é a alternativa para uma operação menor. A tela do KDS é uma captura da interface real com pedidos demonstrativos.

Este diretório serve para revisão do código pelo fluxo de PR do GitHub. **Fazer merge deste PR não publica o domínio.** A versão 15 já foi publicada no projeto Sites `appgprj_6adb83246e748191b52be86ee3c0bf94`. Os arquivos de `dist/` deste PR e dessa versão devem continuar idênticos. Não copiar a landing para o frontend Railway: `www.fomizero.com.br` continua hospedando o sistema e o onboarding.

## Medição

`dist/config.js` usa o Pixel da Meta e o ID público de GA4 `G-HDBVG6L1NT`. Na landing, o Pixel é carregado na primeira visita por padrão, exceto quando há uma preferência anterior de desativação neste navegador. A opção de desativar fica em **Preferências de privacidade**, no rodapé. O Google Analytics também é carregado na primeira visita por padrão, salvo preferência anterior de desativação. `PlanSelected` e `plan_selected` medem cliques em planos; não equivalem a início de checkout ou compra. As páginas de cardápio e checkout dos restaurantes não usam este código.

## Verificações locais

```sh
node --check dist/app.js
```

No navegador, conferir a página em largura de celular e desktop, destino dos três links de planos, imagem do KDS, Termos de Uso e preferências de medição.
