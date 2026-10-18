# Verified customer history: protected foundation, delivery integration pending

Guest checkout and order-specific tracking stay available. The session-scoped recent-order button is a convenience for that browser, not proof of customer identity. Public tracking tokens remain bearer capabilities: anyone given a token can see its limited tracking summary until expiry/revocation.

## Account access

The account history and legacy customer profile/address/history/benefit endpoints now require a signed customer cookie with a verified-phone claim, matching tenant, and an active customer with recorded phone verification. Caller-supplied IDs/phones cannot select another account. National, country-code and E.164 forms identify equivalent legacy guest records within that tenant after verification. No bulk customer merge or migration runs.

OTP validity is seven minutes, with five guesses, a sixty-second resend cooldown, ten requests per phone per hour, prior-code invalidation, hashed codes, and PostgreSQL row locks for verification. Codes are never returned or logged. Explicit terms acceptance is required. Sessions use a host-only HttpOnly SameSite=Lax cookie, Secure in staging/production, expiring in twenty-four hours; tokens are not returned to browser JavaScript or accepted from Authorization headers. Old customer JWTs without the verification claim need reauthentication. Private responses are marked no-store.

Logout removes the browser cookie and clears tracking caches, pending phone and legacy local history, preserving a new cart. Switching accounts also clears the previous person's shortcuts. Failed logout clears local shortcuts but reports failure because it cannot claim the HttpOnly cookie was removed. JWT sessions are stateless: logout does not revoke an already-copied cookie on another device; server-side session revocation is a separate requirement for broader account lifecycle/security work.

Unauthenticated guest checkout cannot overwrite verified customer name/email or add saved account addresses. Customer phone changes cannot bypass a new proof of ownership. History shows orders associated with the verified phone; phone possession does not prove original purchaser identity, nor prevent malicious orders using another person's contact number. A shared browser and shared/copied tracking links are distinct from authenticated history.

## Delivery is intentionally unavailable

The existing null OTP sender silently accepted requests without sending a message. No WhatsApp/SMS account is configured. This change therefore fails with a clear 503 before creating or verifying codes unless a provider is injected by automated tests. The old test flag is restricted to ENV=test; staging and production cannot return test codes or use that adapter. No real messages are sent by this implementation.

Before enabling real customer sign-in, choose and implement a delivery provider with credentials, sender/template approval, delivery failure handling, provider-level/global abuse limits, and monitoring. Do not tell customers that a code has been delivered until the provider accepts it. Keep production deployment paused until that integration is ready. Guest purchases continue in the meantime.

## Validation

Backend tests cover separate customers and tenants, unverified access, malformed claims, OTP expiry/replay/attempt and resend limits, no-provider/send-failure handling, legacy phone formats, disabled accounts, and verified profile protection. Existing lookup tests now authenticate their owner fixture and expect forbidden responses when querying other phones.

Frontend cache/session tests cover cleanup, account switch, provider-unavailable errors, tenant context, and cart preservation. A Chromium fixture test covers unauthenticated history redirect, the unavailable-provider screen, simulated OTP verification, private history, and logout. Fixture delivery is not a real SMS/WhatsApp test.

Commands: `pytest -q tests/test_customer_auth_security.py tests/test_store_customer_lookup.py`; `npm run test:customer-auth`; with a local Next dev server, `npm run test:customer-auth:browser`. Browser tests accept CHROMIUM_PATH and CUSTOMER_AUTH_TEST_BASE_URL. No database migration is required. On staging, check that guest checkout and inline order tracking still work, private history asks for phone verification, and requesting a code clearly reports unavailability until real delivery is configured.
