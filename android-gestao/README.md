# Fomizero Gestão para Android

O pacote `br.com.fomizero.gestao` abre o painel existente em
`https://www.fomizero.com.br/dashboard` por Trusted Web Activity. O painel continua
validando a sessão, a unidade e as permissões no servidor.

## Build de validação

Use Java 17, Gradle 8.11.1 e a plataforma Android 36. Nesta pasta, execute
`gradle lintDebug assembleDebug bundleRelease`. O APK de depuração serve para
testes internos. O bundle gerado por esse comando ainda precisa de assinatura
para envio à Play Console.

## Validação antes da publicação

- Publicar a associação Digital Asset Links do pacote no domínio do painel,
  usando a impressão SHA-256 do certificado de assinatura do app no Google Play.
- Validar em aparelho Android a abertura sem barra do navegador, o login, a
  seleção de unidade, as permissões e a operação de pedidos.
- Integrar alertas de pedidos com entrega em segundo plano e validar o toque na
  notificação com a tela bloqueada e o app fechado.
- Assinar o AAB, preparar a ficha e as declarações da Play Store e validar a
  versão no canal de testes internos.
