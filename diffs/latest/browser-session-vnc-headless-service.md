# fix(bot-manager): create headless Service per browser session pod + fix VNC/WebSocket path prefix

## Commit title
`fix(bot-manager): headless Service per browser session pod + VNC prefix for sub-path deployments`

## Description
Two related fixes to make browser sessions work end-to-end behind a sub-path reverse proxy
(e.g. `/vexa/api-gateway`).

### Problem 1 — VNC 502: pod not DNS-resolvable
The api-gateway proxies VNC and CDP traffic to the bot by `container_name` as a hostname.
In Kubernetes, bare pod names are not DNS-resolvable — only Service names are. The pod was
reachable by IP but hostname lookup failed with "Temporary failure in name resolution".

**Fix:** `start_browser_session_container` now creates a headless (`clusterIP: None`)
Kubernetes Service with the same name as the pod immediately after pod creation. The
Service selects the pod via `app.kubernetes.io/name: vexa-bot` + `vexa.meeting-id` labels.
`stop_bot_container` deletes the Service alongside the pod (404 ignored).

**RBAC:** Added `services: [create, delete, get]` to the bot-manager Role.

### Problem 2 — WebSocket 1006: wrong path after sub-path rewrite
noVNC connects via WebSocket using the `path=` query parameter in the VNC URL. The path
was hardcoded as `b/{token}/vnc/websockify` (no prefix), so the WebSocket connected to
`wss://host/b/.../websockify` which doesn't match the HTTPRoute — the gateway routed it
to the dashboard instead of api-gateway, causing connection close 1006.

**Fix:** `_browser_dashboard_html` now accepts a `prefix` argument (e.g. `/vexa/api-gateway`)
read from the `X-Forwarded-Prefix` request header. All paths in the generated HTML
(iframe src, Fullscreen button, save fetch) are prefixed correctly.

### Files changed
- `services/bot-manager/app/orchestrators/kubernetes.py` — headless Service create/delete
- `helm/charts/vexa/templates/bot-manager-rbac.yaml` — services RBAC
- `services/api-gateway/main.py` — prefix-aware VNC HTML generation
