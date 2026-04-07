# helm changes

## Chart.yaml
- `appVersion`: `0.6.0` → `0.6.1`

## templates/deployment-bot-manager.yaml
- Added `BOT_NODE_SELECTOR` env var injection (conditional on `botManager.bot.nodeSelector` being set) — allows constraining bot pods to a specific K8s node pool
- Fixed Zoom credential secret resolution: removed fallback to `secrets.existingSecretName` for `ZOOM_CLIENT_ID` / `ZOOM_CLIENT_SECRET`; now only reads from `botManager.zoom.existingSecretName` to avoid accidental cross-secret resolution

## templates/deployment-dashboard.yaml
- Renamed env var `NEXT_PUBLIC_DECISION_LISTENER_URL` → `DECISION_LISTENER_URL` (server-side only, not a public Next.js build-time variable)

## values.yaml
- Added `botManager.bot.nodeSelector`: JSON string for K8s node selector on bot pods (e.g. `{"k8s.infobip.com/nodepool":"worker"}`); empty means no constraint
