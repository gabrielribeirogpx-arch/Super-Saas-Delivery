# Staging live delivery tracking

> STATUS — PAUSADO em 18/10/2026 por decisão do fundador. O Google exibiu pré-pagamento de R$150 e a ativação aguardará orçamento. O PR #803 já foi mesclado, mas faturamento/API/chave, build e GPS real ainda não estão homologados. Não executar pagamento, gerar contas ou promover a produção automaticamente. Retomar a partir de “Google Cloud setup for staging”. O desenvolvimento de outras frentes continua conforme docs/fomizero-marketplace-roadmap.md.


## Included behavior
- Customer map and driver map use NEXT_PUBLIC_GOOGLE_MAPS_API_KEY; no fixed key fallback.
- Customer display does not turn null coordinates/metrics into zero coordinates or an invented one-minute ETA. ETA requires an out-for-delivery order, a driver coordinate, and positive numeric metrics.
- Customer location polling reads driver_lat/driver_lng from the public order contract.
- Delivery status aliases use the shared normalizer.
- Customer map handles missing configuration/auth failure, waits for actual coordinates, initializes without resetting on every GPS update, and uses the Maps JavaScript DirectionsService rather than calling the Directions REST endpoint from the browser. Route requests are limited to one per 30 seconds while coordinates update.
- Driver GPS uses the existing authenticated HTTP endpoint when NEXT_PUBLIC_API_URL is relative/empty (the same-origin proxy does not supply a WebSocket tunnel). Direct absolute API deployments retain WebSocket with HTTP fallback.
- Driver feedback reports send/connection state; denied GPS prevents starting from the driver page. A missing embedded map does not prevent GPS permission and external navigation.
- Session tokens, order ownership checks, token expiry and tenant boundaries remain enforced by existing backend endpoints.

## Google Cloud setup for staging
1. Create/select a Google Cloud project dedicated to staging and attach billing for Google Maps usage.
2. Enable Maps JavaScript API.
3. Create a browser API key. Restrict application usage to HTTP referrers:
   - https://*.staging.fomizero.com.br/*
   - https://staging.fomizero.com.br/*
4. Restrict API usage to Maps JavaScript API and the directions service/API enabled for the project. This implementation uses Maps JavaScript DirectionsService; confirm project eligibility/API availability in Google Cloud. If directions is not available, the position map can still load but route rendering requires follow-up provider configuration or Routes migration.
5. Set NEXT_PUBLIC_GOOGLE_MAPS_API_KEY on Railway Frontend - Staging. It is a browser key and must have referrer/API restrictions.
6. Build/deploy the frontend after setting the variable (NEXT_PUBLIC values are embedded at build time). Do not change production variables or enable production auto-deploy.
7. If Maps still reports an error, inspect the exact Google Maps JavaScript error code in Console (billing, API activation, invalid key or referrer restriction) before changing permissions.

## Real-device validation required
- Assign a controlled staging order to an active delivery user. Starting an order as an owner is not evidence that a delivery user's GPS is connected.
- Log in as that delivery user on a phone over HTTPS. Permit location and start the assigned delivery.
- Verify an authenticated location request succeeds and driver UI reports sent, then verify the customer sees that position.
- Move with the phone safely (a passenger or walking tester); verify successive real locations and smooth marker movement, not simulated location presented as real.
- Deny location, disconnect/reconnect data, reload the client, finish delivery, and log out. Confirm honest feedback, recovery and stopped GPS after completion/logout.
- Browser geolocation requires the driver app open and device permissions. Screen lock, background suspension and switching to another app may pause updates. Native background tracking is outside this patch and cannot be promised.
- Verify stale/disconnected indications and ETA quality with real data before public release. This patch does not certify continuous background operation.

## Validation limitation
Managed execution environment is unavailable. Full frontend tests, type checking/build and browser/device tests were not run. Isolated numeric/ETA helper checks were executed in the tool JavaScript runtime after stripping TypeScript annotations. Review and staging validation are required before merge or promotion.
