# Delivery Tracking Architecture Investigation (Customer Real-Time Map)

## Scope
This report maps the current delivery tracking architecture and identifies what is missing for real-time customer tracking on `/pedido/[token]` when order status becomes `OUT_FOR_DELIVERY`.

---

## 1) Map provider used

### Customer tracking page
- **Provider:** Google Maps JavaScript API.
- Evidence:
  - Loads Google Maps script with `https://maps.googleapis.com/maps/api/js?key=...`.
  - Initializes `new google.maps.Map(...)` and `new google.maps.Marker(...)`.

### Driver navigation page
- **Provider:** Google Maps JavaScript API.
- Evidence:
  - Loads same Google Maps script.
  - Uses `google.maps.DirectionsService`, `google.maps.DirectionsRenderer`, markers, and polyline.

### Admin/other map areas
- **Provider:** Mapbox is also present in the codebase.
- Evidence:
  - `mapbox-gl` dynamic loader and `NEXT_PUBLIC_MAPBOX_TOKEN` in shared map utilities.
  - Backend directions/geocoding services call Mapbox APIs (`MAPBOX_ACCESS_TOKEN`).

**Conclusion:** The repository currently uses a **hybrid mapping stack**:
- Google Maps for driver/customer live UI maps.
- Mapbox for parts of admin map usage and backend route/geocode services.

---

## 2) Driver navigation engine architecture

### Frontend route and map implementation
- Driver delivery page: `super_saas_frontend/app/driver/delivery/[orderId]/page.tsx`.
- Driver map component: `super_saas_frontend/components/driver/DeliveryMap.tsx`.

### How map is initialized
- Driver map component loads Google Maps JS and creates map instance once container is visible.
- Initializes:
  - `DirectionsService`
  - `DirectionsRenderer`
  - custom polyline for route overlay
  - destination and driver markers

### How driver GPS is captured
- Uses browser geolocation `navigator.geolocation.watchPosition(...)` while `navigationMode` is enabled.
- Options: `enableHighAccuracy: true`, `timeout: 10000`, `maximumAge: 0`.

### How frequently location updates happen
- **Primary cadence:** geolocation watch callback frequency (OS/browser-driven).
- Additional sync loop for order state every 2s.
- Separate tracking module (not the active driver app endpoint) has a 2s throttle.

### Which backend endpoint receives location updates
- Driver UI sends to `POST /api/driver/location` via `sendDriverLocation`.
- Backend endpoint stores location in `DeliveryTracking` and publishes Redis event `driver_location` to channel `tenant:{tenant_id}:delivery_driver_location`.

### Which API/service calculates route
- Driver UI route rendering/ETA on map is calculated in-browser by **Google DirectionsService**.
- Backend also has route/ETA service (`app/services/directions_service.py`) using **Mapbox Directions API** (mainly used by `/api/delivery/location` flow).

---

## 3) Realtime location pipeline

There are **multiple realtime paths** currently coexisting:

### A) Driver app realtime channel (currently used by driver page and admin live-map stream)
1. Driver app posts GPS to `POST /api/driver/location`.
2. Backend publishes Redis message via `publish_delivery_driver_location_event(...)`.
3. Channel: `tenant:{tenant_id}:delivery_driver_location`.
4. Consumers:
   - `GET /api/delivery/live-map/stream` SSE subscribes to this channel.
   - Driver frontend `useSSE` can consume `/sse/delivery/status` (but this endpoint currently emits keepalive payloads only, not driver_location events).

### B) Public tracking websocket channel
1. Endpoint: `WS /ws/public/tracking/{tracking_token}`.
2. Subscribes to Redis channel: `tenant:{tenant_id}:order:{order_id}:tracking`.
3. Sends initial snapshot and subsequent Redis envelope events.
4. Events published to this order-tracking channel occur in `/api/delivery/location` flow (not `/api/driver/location`).

### C) Public tracking SSE channel (customer page uses this)
1. Endpoint: `GET /sse/order/{order_token}`.
2. Polls Redis key `tracking:order:{order_id}` once per second.
3. Redis key is written by `POST /driver/location` (module tracking router), with throttle window 2s.
4. **Important mismatch:** customer page listens here, but driver app posts to `/api/driver/location`, not `/driver/location`.

---

## 4) Customer tracking page analysis

### Route/page
- Customer tracking page is `super_saas_frontend/app/pedido/[token]/page.tsx`.

### Data inputs
- Initial fetch: `GET /api/public/order/{token}`.
- Status realtime: `WS /ws/public/tracking/{token}`.
- Location realtime for marker movement: `EventSource('/sse/order/{token}')`.

### Does this page initialize the map?
- Yes, but only if:
  - status is out-for-delivery and window `ORDER_STATUS === OUT_FOR_DELIVERY`.
  - Google Maps script loads.
  - `#tracking-map` has non-zero dimensions.
  - `customer_lat` and `customer_lng` are finite.

### Does it subscribe to driver location?
- Yes, via SSE `/sse/order/{token}`.
- It parses `lat/lng` and animates marker movement.

### Does it receive and render markers/routes?
- Marker rendering is attempted.
- No route drawing on customer page currently (only driver marker + map center/pan).
- Marker update requires SSE payload with valid `lat/lng`.

---

## 5) Coordinate source (customer coordinates)

- `orders` table model stores `customer_lat`, `customer_lng`, `delivery_lat`, `delivery_lng`.
- Order creation (`/api/orders`) geocodes address and stores these coords.

**Gap observed:** `GET /api/public/order/{tracking_token}` payload does **not** include coordinate fields expected by customer page (`customer_lat`, `customer_lng`, etc.).

---

## 6) Route generation

### Driver navigation route generation
- Client-side: Google `DirectionsService.route(...)` in driver map component.

### Backend route generation
- `app/services/directions_service.py` uses Mapbox Directions API and `MAPBOX_ACCESS_TOKEN`.
- Used by `/api/delivery/location` to compute `distance`, `duration`, `geometry` for tracking metadata.

### Customer page reuse
- Customer page does **not** reuse backend route geometry or draw route polyline.
- It only places and moves driver marker.

---

## 7) Map key / API key validation

### Google key
- Frontend requires `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` for driver and customer map components.
- If missing, code explicitly rejects map script load and logs an error.

### Mapbox key
- Backend route/geocode services use `MAPBOX_ACCESS_TOKEN`.
- Frontend mapbox utilities require `NEXT_PUBLIC_MAPBOX_TOKEN` where used.

Potential blank-map causes present in code:
1. Missing `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`.
2. Invalid/blocked Google key/domain/billing (runtime behavior external).
3. Invalid customer coordinates causing map init short-circuit.

---

## 8) Current failure analysis (blank customer map)

### Primary root cause (code-level)
- Customer page aborts map initialization when `customer_lat/customer_lng` are invalid.
- Public order endpoint (`/api/public/order/{token}`) does not return these coordinates.
- Result: map container appears, but map object is never constructed (`new google.maps.Map(...)` is not reached).

### Secondary architecture gap
- Customer page location stream is `/sse/order/{token}`, whose backend data source is `/driver/location` (tracking module).
- Driver app publishes to `/api/driver/location`, which writes DB + publishes `delivery_driver_location`, but does not write tracking Redis key used by `/sse/order/{token}`.
- Even after map init is fixed, realtime marker movement may still fail because producer/consumer channels are not unified.

### Additional inconsistency
- Customer websocket `/ws/public/tracking/{token}` receives public tracking payloads but frontend only applies status fields from that websocket (ignores location data from payloads).

---

## 9) Architecture gap analysis (what is missing)

Target architecture:
`Driver GPS -> Backend realtime channel -> Customer tracking page -> moving marker`

### Missing pieces to achieve this reliably
1. **Public order payload must provide map bootstrap coordinates**
   - Include `customer_lat/customer_lng` (and optionally `delivery_lat/delivery_lng`, `last_location`) in `/api/public/order/{token}`.
2. **Single canonical realtime pipeline for customer updates**
   - Driver location producer and customer consumer must use the same channel/data store.
   - Currently split between:
     - `/api/driver/location` + `tenant:*:delivery_driver_location`
     - `/driver/location` + `tracking:order:*` Redis key
     - `/api/delivery/location` + `tenant:*:order:*:tracking`
3. **Customer page should consume location from the chosen canonical channel**
   - Either SSE or WebSocket, but unified and consistent with driver producer.
4. **Message schema normalization**
   - Standardize payload fields (`lat`, `lng`, `order_id`, `updated_at`, status/ETA optional).
5. **Lifecycle robustness**
   - Decouple map init from strict coordinate availability (fallback strategy) or guarantee coordinates are always present before OUT_FOR_DELIVERY.

---

## 10) Final architectural recommendation (no implementation yet)

### Recommended canonical flow
1. Driver app sends GPS to **one authoritative endpoint** (`/api/driver/location`).
2. Backend persists location + publishes to **order-scoped realtime channel**.
3. Customer page subscribes to that same order-scoped channel.
4. Customer page initializes map with order/customer coordinates from public order payload and updates marker on each location event.

### Suggested logical contracts
- **Bootstrap API (`GET /api/public/order/{token}`)** returns:
  - `customer_lat`, `customer_lng`
  - `last_location` (if available)
  - tracking status metadata
- **Realtime channel payload** returns:
  - `order_id`, `lat`, `lng`, `updated_at`
  - optional `remaining_seconds`, `distance_meters`, `status`

### Why this solves the issue
- Map no longer fails due to missing bootstrap coordinates.
- Driver updates reach customer page through the same pipeline.
- UI can render immediate map + continuous marker movement during OUT_FOR_DELIVERY.

