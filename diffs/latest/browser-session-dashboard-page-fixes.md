# fix(dashboard): fix browser session page — session detection, stop, VNC readiness

## Commit title
`fix(dashboard): fix browser session page — correct session detection, stop, VNC readiness wait`

## Description
Multiple bugs in `services/dashboard/src/app/browser/page.tsx`:

### 1 — Session detection used wrong endpoint
`fetchActiveSession` called `GET /bots/status` which returns running pod metadata with no
`data.session_token`. The filter `b.data?.mode === "browser_session"` never matched so the
page always showed "Start Browser Session" even with an active session.

**Fix:** Query `GET /meetings` and filter client-side for
`mode === "browser_session" && status === "active"`.

### 2 — Stop called wrong ID (`undefined`)
Stop sent `DELETE /bots/browser_session/{session.id}` using the numeric DB id, but the
endpoint expects the native meeting ID (e.g. `bs-e1ec3bcc`). The `BrowserSession`
interface was missing `native_meeting_id` so it was `undefined`.

**Fix:** Added `native_meeting_id` to the interface; Stop now uses `session.native_meeting_id`.
Also added `res.ok` check — `fetch` doesn't throw on non-2xx, so failures were silently
reported as success.

### 3 — VNC URL had wrong WebSocket path
`path=b/{token}/vnc/websockify` caused noVNC to connect to `wss://host/b/.../websockify`
which doesn't match the `/vexa/api-gateway` HTTPRoute rule. The WebSocket was routed to
the dashboard instead of api-gateway.

**Fix:** Derives prefix from `apiUrl` (e.g. `/vexa/api-gateway`) and uses it in `path=`.

### 4 — CDP URL pointed to non-existent route
`/b/{token}/cdp` returns 404 — the route is `/b/{token}/cdp/{path:path}`. The CDP URL
for Playwright `connectOverCDP()` should be the WebSocket endpoint.

**Fix:** `cdpUrl` now points to `/b/{token}/cdp-ws`.

### 5 — VNC iframe loaded before pod was ready (race condition)
The iframe rendered immediately after session creation. The pod takes a few seconds to
start websockify, so the first HTTP load of `vnc.html` returned 502 and the iframe showed
a blank error page.

**Fix:** `waitForVnc` polls `vnc.html` with HEAD requests (1s interval, 20 attempts) and
shows a "Starting browser…" spinner until the pod responds 200. On page reload with an
existing session, the wait is skipped and the iframe loads immediately.
