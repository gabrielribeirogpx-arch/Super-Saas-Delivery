# Fomizero Gestão para Android

Aplicativo Flutter com pacote `br.com.fomizero.gestao`, telas próprias e acesso
às APIs administrativas oficiais do Fomizero. A primeira versão inclui login
por loja, saída e consulta de pedidos. A sessão fica em memória e o servidor
valida o acesso à loja.

Use Flutter 3.41.9 e Java 17. Execute `flutter pub get`, `flutter analyze` e
`flutter build apk --debug`. Use `--dart-define=API_BASE_URL=<origem-https>`
para testar contra outro ambiente autorizado.

O projeto exige uma chave própria para compilar a versão release. Configure
a assinatura no ambiente autorizado, usando `android/key.properties.example`
como referência, e gere o AAB com `flutter build appbundle --release`.

## Avisos de novos pedidos

O sino no cabeçalho ativa os avisos para a conta autenticada neste aparelho.
O Android pode pedir permissão. O aviso é exibido também em segundo plano e
abre a lista de Pedidos, exigindo login se a sessão do app estiver encerrada.
Sair da conta ou desligar o sino remove o vínculo local e os avisos exibidos.

Para validar em homologação:

1. No Firebase, cadastre o app Android com o pacote `br.com.fomizero.gestao`.
   Forneça ao processo de build `GESTAO_FIREBASE_APP_ID`,
   `GESTAO_FIREBASE_API_KEY`, `GESTAO_FIREBASE_SENDER_ID` e
   `GESTAO_FIREBASE_PROJECT_ID` a partir da configuração do app Android no
   Firebase. Um build sem essa configuração oculta o sino.
2. No backend, aplique a migration e configure credenciais do mesmo projeto
   Firebase com permissão de envio FCM. Use Application Default Credentials ou
   injete `MANAGEMENT_PUSH_SERVICE_ACCOUNT_JSON` pelo gerenciador de segredos.
   Ative `MANAGEMENT_PUSH_ENABLED=true` e mantenha um consumidor do outbox ativo.
3. Instale o APK de homologação em um Android com Google Play Services. Entre
   na loja, ative o sino, bloqueie a tela e crie um pedido nessa loja. Toque no
   aviso e confirme que a lista de Pedidos é carregada. Repita com o app em
   primeiro plano, outra loja e após sair da conta.

A fila tenta a entrega por até cinco minutos. Pedidos são registrados
normalmente durante indisponibilidade do Firebase.
