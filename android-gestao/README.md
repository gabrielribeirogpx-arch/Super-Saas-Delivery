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

A próxima entrega precisa validar o login e os pedidos em um Android real,
implementar as ações de gestão e os alertas em segundo plano e testar o AAB
assinado na Play Console.
