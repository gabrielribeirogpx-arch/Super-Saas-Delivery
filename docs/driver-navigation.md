# Navegação do entregador

`GET /api/driver/orders/{order_id}/navigation?origin_lat=...&origin_lng=...` retorna o traçado viário e a próxima orientação para uma entrega ativa. Exige token de entregador, plano com rastreamento e pedido atribuído ao mesmo entregador e restaurante.

Resposta: `distance_meters`, `duration_seconds`, `encoded_polyline`, `next_instruction`, `next_maneuver`, `next_step_distance_meters`, coordenadas do destino e ID do pedido. O app recalcula a rota após movimento ou tempo decorrido, enquanto envia a localização ao cliente pelo endpoint já existente.

O backend usa `GOOGLE_MAPS_API_KEY` para consultar a Google Directions API. A chave deve ter acesso à Directions API e permanecer apenas nas variáveis do serviço Backend; **não** reutilize a chave Android restrita a Maps SDK for Android. Sem chave, sem Directions habilitada ou em falha do provedor, o endpoint responde 503; o envio de localização e o acompanhamento do cliente continuam funcionando.

Antes de colocar em produção, configure cotas e alertas de gastos no Google Cloud e teste com uma entrega de teste em aparelho físico. O trajeto usa modo `driving` do Google; confirme se o percurso é adequado para a modalidade de entrega.
