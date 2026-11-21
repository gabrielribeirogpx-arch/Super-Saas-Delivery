# Download do app Fomizero Entregador

O app Android nativo é distribuído na página pública `/baixar-entregador`. O link também aparece em `/driver/login`. Essa distribuição é separada da instalação PWA do painel de gestão.

Antes de habilitar o botão:

1. Gere o APK **release assinado** seguindo o `README.md` do repositório `driver_app`. Use a mesma chave de assinatura em todas as versões.
2. Teste o APK em um celular real: login, entrega ativa, mapa Mapbox, GPS em segundo plano, rastreio do cliente e conclusão.
3. Envie o APK para o bucket Cloudflare R2 usado para arquivos públicos, por exemplo em `downloads/fomizero-entregador-v1.0.0.apk`. Sirva o arquivo por HTTPS com tipo `application/vnd.android.package-archive`.
4. No serviço **Frontend** do Railway, configure `DRIVER_APK_URL` com o endereço público completo do APK e, opcionalmente, `DRIVER_APK_VERSION` com a versão exibida na página. Faça o redeploy do frontend.
5. Abra `/baixar-entregador` em uma janela anônima no Android e confirme que o arquivo baixa sem login.

Enquanto `DRIVER_APK_URL` não estiver configurada com um URL HTTPS válido, a página informa que o download está sendo preparado e não exibe um botão que leva a um arquivo inexistente.

Para atualizações, publique um novo APK com `versionCode` maior e a **mesma** chave, atualize `DRIVER_APK_URL` e teste a instalação sobre a versão anterior. Um APK assinado com outra chave não atualiza o app instalado.
