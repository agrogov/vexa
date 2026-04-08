# fix(api-gateway): prevent 503s from stale httpx connections with keepalive expiry and retry

## Commit title
`fix(api-gateway): set httpx keepalive_expiry and retry once on stale connection errors`

## Description
The api-gateway uses a single shared `httpx.AsyncClient` for all upstream proxying.
With no configuration, httpx reuses HTTP/1.1 connections indefinitely. When an upstream
pod restarts or closes an idle socket, the gateway doesn't detect the stale connection
until it tries to send on it — raising a silent `RequestError` and returning 503 to the
client. This was observed when deleting meeting `teams/39975953777562`.

### Changes to `services/api-gateway/main.py`

**`httpx.AsyncClient` configuration (startup)**

Added three settings:
- `timeout=httpx.Timeout(30.0, connect=5.0)` — 5 s connect timeout, 30 s read/write timeout; prevents silent hangs on unresponsive upstreams.
- `keepalive_expiry=30.0` — connections idle for more than 30 s are evicted from the pool before reuse; eliminates the stale-socket window entirely.
- `max_keepalive_connections=20`, `max_connections=100` — explicit pool bounds (httpx defaults are unbounded).

**One-shot retry in `forward_request`**

On `httpx.RequestError`, retry the same request once before raising 503. Covers the
narrow race where a connection expires between the pool health-check and the actual
send. If the retry also fails, the original 503 behaviour is preserved.
