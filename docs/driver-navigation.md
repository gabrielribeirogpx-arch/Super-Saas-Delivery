# Navegação do entregador

`GET /api/driver/orders/{order_id}/navigation?origin_lat=...&origin_lng=...` retorna o traçado viário e a próxima orientação para uma entrega ativa. Exige token de entregador, plano com rastreamento e pedido atribuído ao mesmo entregador e restaurante.

Resposta: `distance_meters`, `duration_seconds`, `encoded_polyline`, `next_instruction`, `next_maneuver`, `next_step_distance_meters`, coordenadas do destino e ID do pedido. O app recalcula a rota após movimento ou tempo decorrido, enquanto envia a localização ao cliente pelo endpoint já existente.

O backend usa `MAPBOX_ACCESS_TOKEN` para consultar a **Directions API** do Mapbox. Configure um token com acesso à API nas variáveis do serviço Backend. Sem token ou em falha do provedor, o endpoint responde 503; o envio de localização e o acompanhamento do cliente continuam funcionando. O aplicativo recebe apenas a geometria, as instruções e os indicadores, sem o token do backend.

Antes de colocar em produção, configure cotas e alertas de gastos no Mapbox e teste com uma entrega de teste em aparelho físico. O trajeto usa o perfil `driving` do Mapbox; confirme se o percurso é adequado para a modalidade de entrega.
