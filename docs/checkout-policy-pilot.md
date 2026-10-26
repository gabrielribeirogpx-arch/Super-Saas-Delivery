# Checkout policy pilot: server-side rules, native adapter still pending

This change connects the existing commercial policy to public checkout method discovery and order creation. It is not a Free-plan launch or a real payment integration. No fee percentages, PSP credentials, native payment confirmations or simulated paid orders are introduced.

## Default and controlled activation

With CHECKOUT_POLICY_ENABLED absent/false, existing storefronts retain legacy checkout/finance behavior. Explicit native_pix/native_card submissions are always rejected because no native adapter exists; they cannot reach the legacy auto-paid helper. The Free catalog is not seeded or offered. Do not provision/promote commercial Free stores before native payments and comprehensive order-entry enforcement are ready.

The pilot requires both CHECKOUT_POLICY_ENABLED=true and CHECKOUT_POLICY_TENANT_IDS containing only the IDs of approved test stores. It runs only in test/staging/stage/homolog; activation against production fails closed. Invalid enabled allowlist configuration also fails closed. Do not add flags to Railway merely after merging. Prepare a dedicated test store and a reviewed commercial assignment first; no existing tenant/subscription is mutated by this PR.

Within the pilot, the server reads Subscription and Plan for the resolved store. There is no implicit Free fallback. Only active assignments with active, recognized plans qualify; paid assignments need a future current_period_end, and future starts/expired ends are rejected. Trialing, past-due/grace, inactive and canceled assignments are conservatively unavailable until those commercial rules are explicitly approved.

Free exposes native Pix/card only, currently disabled. Active essential/operation/pro assignments expose Pix directly with the store, cash and the store's card collection. Native methods remain disabled for paid plans too. Public responses contain method availability and a generic store-unavailable message, not subscription IDs, billing dates or internal plan rejection reasons. The canonical public order path and /api/store/orders re-check policy on creation; changing plan/method/channel/fees in the browser does not override server state. Body store_id cannot select a different store. Pilot order origin is fixed by the server as own_store.

## Financial behavior and boundaries

Pilot manual payments create OrderPayment(status=pending, paid_at=null). Selecting a method is not proof of collection. No paid cash movement or stock debit is triggered by that pending payment. Financial creation failures roll back the pilot order instead of being swallowed. Manual collection may proceed to the kitchen, because cash/card-on-delivery orders are paid later.

No native order is created at all until a real adapter and approved fee rules exist. Therefore this release does not implement a pending-native order queue, native payment confirmation endpoint, native refund/settlement or release-to-KDS workflow. Native payment persistence remains an isolated simulation component. Do not claim full payment/KDS integration from this policy pilot.

Outside the pilot, the historical manual auto-paid helper remains unchanged; its broader migration is separate work. Administrative/import/WhatsApp order-entry paths are outside this checkout pilot and must be audited before commercial Free enforcement is offered across the product. Marketplace origin/acquisition fees are not activated; these storefront routes always evaluate own-store policy, never a caller-declared marketplace channel.

## UI and deployment

Checkout fetches /public/checkout-policy for the resolved store, uses server-listed methods, disables unavailable methods, and prevents submission while loading, with no available option, or after a discovery failure. The client never falls back to hard-coded manual methods on an error. Retry is explicit; server policy is authoritative even after a valid earlier discovery. Store-scoped requests are not cached.

No database migration or new Railway variables are required to merge/deploy with the pilot OFF. Deploy backend before frontend where possible so method discovery is present. A temporary discovery failure blocks checkout safely and offers retry. Keep production auto-deploy disabled.

## Validation

Backend regressions cover Free manual-method aliases, forged plan/fees/channel, unknown methods, missing/inactive/expired/future/unknown assignments, real native IDs outside and inside the pilot, store-ID substitution, manual pending collection and rollback on finance failure. Browser fixture tests exercise Free disabled options, failed discovery/retry and paid manual checkout. These are not real financial transactions.

Run pytest -q tests/test_checkout_policy.py, npm run test:checkout-policy, and, against a local Next dev server, npm run test:checkout-policy:browser. Optional CHECKOUT_POLICY_TEST_BASE_URL and CHROMIUM_PATH configure the browser test.

Next milestones: choose the PSP, approve fee rules and plan/trial/grace behavior, implement idempotent native pending checkout and authenticated confirmation with operational release, then validate all entry paths and enable a controlled store. Do not enable a Free commercial offering based on this pilot alone.
