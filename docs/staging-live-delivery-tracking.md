# Staging live delivery tracking

## Included behavior
- Customer map and browser driver map use NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN (or legacy NEXT_PUBLIC_MAPBOX_TOKEN); no fixed token fallback.
- Customer display does not turn null coordinates/metrics into zero coordinates or an invented one-minute ETA. ETA requires an out-for-delivery order, a driver coordinate, and positive numeric metrics.
- Customer location polling reads driver_lat/driver_lng from the public order contract.
- Delivery status aliases use the shared normalizer.
- Customer map handles missing configuration, waits for actual coordinates, initializes without resetting on every GPS update, and uses Mapbox Directions for the route. Route requests are limited to one per 30 seconds while coordinates update.
- Driver GPS uploads use the existing authenticated HTTP endpoint. There is at most one upload in flight, and the latest sampled position is sent after throttling or retried after a transient error. A confirmed active delivery resumes tracking when its page is opened.
- Customer updates use Redis events when available. Without Redis, the SSE status poll also publishes changed coordinates from the database. The last-updated indicator relies on verified location timestamps.
- Driver feedback reports send/connection state; denied GPS prevents starting from the driver page. A missing embedded map does not prevent GPS permission and external navigation.
- Session tokens, order ownership checks, token expiry and tenant boundaries remain enforced by existing backend endpoints.

## Mapbox setup for staging
1. Create um token público (`pk.`) para o navegador, com acesso aos mapas e à Directions API. Restrinja pelos domínios de staging.
2. Configure `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN` no frontend de staging e `MAPBOX_ACCESS_TOKEN` no backend de staging.
3. Faça o build/deploy de ambos os serviços. Variáveis `NEXT_PUBLIC_*` são incluídas no build do frontend.
4. Se o mapa não carregar, verifique os erros de rede para Mapbox e as restrições do token.

## Real-device validation required
- Assign a controlled staging order to an active delivery user. Starting an order as an owner is not evidence that a delivery user's GPS is connected.
- Log in as that delivery user on a phone over HTTPS. Permit location and start the assigned delivery.
- Verify an authenticated location request succeeds and driver UI reports sent, then verify the customer sees that position.
- Move with the phone safely (a passenger or walking tester); verify successive real locations and smooth marker movement, not simulated location presented as real.
- Deny location, disconnect/reconnect data, reload the client, finish delivery, and log out. Confirm honest feedback, recovery and stopped GPS after completion/logout.
- Browser geolocation requires the driver app open and device permissions. Screen lock, background suspension and switching to another app may pause updates. Native background tracking is outside this patch and cannot be promised.
- Verify stale/disconnected indications and ETA quality with real data before public release. This patch does not certify continuous background operation.

## Validation limitation
O teste em aparelho real e no ambiente de staging continua necessário antes da publicação.
