# Tenant resolution under concurrent load

The tenant-context middleware previously called synchronous SQLAlchemy queries directly
inside async dispatch. A slow query or QueuePool checkout could block the event loop,
including other requests that need it to finish and return database connections.

Run the entire existing resolution operation with Starlette run_in_threadpool. Session
creation, resolution and close remain together in the same worker thread; close still
runs on errors. Tenant priority, cookies, headers, webhook/OPTIONS bypasses and request
state behavior are unchanged. No schema, pool-size or worker-count changes.

The regression test holds the only connection in a real SQLAlchemy QueuePool. An async
task must run to return it while middleware resolution waits. The original middleware
times out; the corrected middleware completes. Additional tests verify same-thread
session lifecycle and cleanup on failure, and OPTIONS/billing webhook bypasses.

## Staging validation

Deploy this backend change to staging, keeping current resource and worker settings.
Repeat the same public-menu k6 script with stages 30s:10, 1m:20, 1m:50, 2m:50, 30s:0.
Compare p95, invalid-response rate, timeouts and Railway HTTP 499s with the failed run.
Check backend and Postgres metrics during the same interval. Do not raise the timeout
to hide slow requests. Verify login, tenant separation and a normal order flow as well.

The local regression proves an event-loop blocking defect, not that it was the only
cause of the observed staging failures. Load testing has not been rerun remotely.
Per-product modifier queries and middleware observability coverage are separate follow-ups.
This change does not establish capacity for 1,000 restaurants.
