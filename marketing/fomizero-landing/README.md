# Landing pública do Fomizero

Código estático da página publicada em `fomizero.com.br`. Os arquivos servidos estão em `dist/`; não há etapa de build. O arquivo `.openai/hosting.json` identifica o projeto Sites existente.

## Revisão da oferta

Esta cópia corresponde ao commit `67180e4f117935e6fd170a81c6c4aa63d458c888` do repositório de origem do Sites, salvo como versão 11 e publicado. O plano Operação é a oferta principal; Essencial é a alternativa para uma operação menor. A tela do KDS é uma captura da interface real com pedidos demonstrativos.

## Publicação

Este diretório serve para revisão do código pelo fluxo de PR do GitHub. **Fazer merge deste PR não publica o domínio.** A versão 11 foi publicada no projeto Sites `appgprj_6adb83246e748191b52be86ee3c0bf94`. Os arquivos de `dist/` deste PR e dessa versão devem continuar idênticos. Não copiar a landing para o frontend Railway: `www.fomizero.com.br` continua hospedando o sistema e o onboarding.

## Verificações locais

```sh
node --check dist/app.js
python3 -m http.server 3182 --directory dist
```

No navegador, conferir a página em largura de celular e desktop, destino dos três links de planos, imagem do KDS, Termos de Uso e preferência de medição. O Pixel da Meta só é carregado no domínio público após consentimento. `PlanSelected` mede cliques em planos; não equivale a início de checkout ou compra.

## Google Analytics 4

`dist/config.js` usa o ID público `G-HDBVG6L1NT` informado pelo proprietário. A página só carrega GA4 após consentimento nos domínios de produção e registra visualização de página e `plan_selected`. A integração fica ativa depois da publicação da versão 11.
