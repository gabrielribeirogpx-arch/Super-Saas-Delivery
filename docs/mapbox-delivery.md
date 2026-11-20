# Mapbox nos mapas de entrega

Os mapas do cliente e do entregador no navegador usam Mapbox GL JS. O aplicativo Flutter usa Mapbox Maps SDK. As rotas e métricas do servidor usam Mapbox Directions. O envio da posição GPS e a transmissão em tempo real continuam na API do Fomizero.

## Configuração

1. No serviço **Frontend** (Railway), configure `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN` com um token público Mapbox (`pk.`) e faça um novo deploy. O token é incluído no JavaScript enviado ao navegador. Restrinja-o aos domínios usados pelo Fomizero, incluindo domínios de lojas, prévia e staging.
2. No serviço **Backend** (Railway), configure `MAPBOX_ACCESS_TOKEN` com um token que permita consultas à Directions API. O mesmo nome já é usado pela geocodificação do backend. Faça um novo deploy.
3. No aplicativo Flutter, execute `flutter run --dart-define=MAPBOX_ACCESS_TOKEN=pk.SUA_CHAVE_PUBLICA_MAPBOX`. Use o mesmo argumento ao gerar o APK. Esse token é incluído no app, então não use `sk.`.

`NEXT_PUBLIC_MAPBOX_TOKEN` continua aceito no frontend para instalações que já usam essa variável. Prefira o novo nome para os mapas de entrega.

Cada restaurante usa as mesmas configurações de mapa da plataforma; não precisa criar um projeto Mapbox por restaurante. A API mantém a separação dos pedidos e posições por loja e pelo token de rastreamento. Revise os limites de uso e defina alertas de cobrança na conta Mapbox antes de ampliar o tráfego.

O mapa mostra posição, rota e instruções escritas. Ele ainda não oferece orientação por voz nem navegação curva a curva com ajuste nativo à via. Teste no celular uma entrega real com GPS, tela bloqueada, mudança de rede e o link público do pedido antes de publicar.
