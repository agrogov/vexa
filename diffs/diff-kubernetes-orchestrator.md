# Kubernetes Orchestrator for Bot Manager

## PR Title

Add Kubernetes orchestrator for bot pod lifecycle management

## PR Description

Introduces a new `kubernetes` orchestrator backend for the bot-manager service, allowing Vexa to spawn and manage meeting bots as Kubernetes Pods instead of Docker containers or Nomad jobs. This enables native K8s deployments without relying on Docker-in-Docker or an external scheduler.

### Summary

- Add `kubernetes` orchestrator module that manages bot pods via the Kubernetes Python client
- Update bot-manager main.py with sync/async compatibility wrappers for orchestrator functions
- Fix stop-bot flow to detect and clean up orphaned containers in terminal meeting states

### Test plan

- [ ] Deploy bot-manager with `BOT_ORCHESTRATOR=kubernetes` inside a K8s cluster
- [ ] Verify bot pods are created in the configured namespace on meeting start
- [ ] Verify bot pods are deleted on meeting stop and via reconciliation
- [ ] Confirm `get_running_bots_status` returns correct pod list filtered by user
- [ ] Confirm health check and reconciliation work with sync K8s client calls
- [ ] Verify existing Docker and Nomad orchestrators are unaffected

## Changes

### New file: `services/bot-manager/app/orchestrators/kubernetes.py`

New orchestrator module that implements the full bot lifecycle via the Kubernetes API:

- **K8s client initialization** -- uses `load_incluster_config()` with a lazily-initialized singleton `CoreV1Api` client.
- **Namespace resolution** -- reads `BOT_NAMESPACE` or `POD_NAMESPACE` env vars, falls back to `default`.
- **Pod construction** (`_build_bot_pod`) -- builds a `V1Pod` spec with:
  - Configurable image (`BOT_IMAGE_NAME`), pull policy, and resource requests/limits.
  - `BOT_CONFIG` env var containing the full bot configuration as JSON (platform, meeting URL, tokens, automatic-leave timeouts, Teams speaker tuning, etc.).
  - `/dev/shm` emptyDir volume (Memory-backed) for browser shared memory.
  - Kubernetes labels for filtering (`vexa.user_id`, `vexa.meeting_id`, `app.kubernetes.io/component`).
  - Optional `ServiceAccount` attachment.
- **Meeting token minting** (`_mint_meeting_token`) -- generates an HS256 JWT scoped to `transcribe:write`, issued by `bot-manager` for `transcription-collector`.
- **`start_bot_container`** -- creates the pod in the target namespace using `asyncio.to_thread` to avoid blocking the event loop.
- **`stop_bot_container`** -- deletes the pod with configurable grace period and propagation policy; treats 404 as success (idempotent).
- **`verify_container_running`** -- reads pod status and returns `True` if phase is `Pending` or `Running`.
- **`get_running_bots_status`** -- lists pods by label selector for a given user, returning container ID, status, start time, and labels.

### Modified: `services/bot-manager/app/orchestrators/__init__.py`

- Registered `"kubernetes"` as a valid `BOT_ORCHESTRATOR` value, mapping it to `app.orchestrators.kubernetes`.

### Modified: `services/bot-manager/app/main.py`

- **Sync/async compatibility layer** -- added three wrapper functions that use `inspect.isawaitable()` to normalize orchestrator calls:
  - `_is_container_running()` -- wraps `verify_container_running`
  - `_get_running_bots_status_safe()` -- wraps `get_running_bots_status`
  - `_record_session_start_safe()` -- wraps `_record_session_start`

  This is necessary because the Kubernetes orchestrator uses the synchronous `kubernetes` Python client, while Docker/Nomad orchestrators return awaitables.

- **Orphaned container cleanup in stop-bot** -- terminal meetings (`COMPLETED`/`FAILED`) that still have a running container are now detected and stopped.
- All direct `await verify_container_running(...)` / `await get_running_bots_status(...)` calls replaced with the safe wrappers across `stop_bot`, `get_user_bots_status`, and `reconcile_meetings_and_containers`.

### Modified: `services/bot-manager/requirements.txt`

- Added `kubernetes==35.0.0` dependency.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BOT_ORCHESTRATOR` | `docker` | Set to `kubernetes` to enable |
| `BOT_NAMESPACE` / `POD_NAMESPACE` | `default` | Target K8s namespace for bot pods |
| `BOT_IMAGE_NAME` | `vexa-bot:dev` | Container image for bot pods |
| `BOT_IMAGE_PULL_POLICY` | `IfNotPresent` | Kubernetes image pull policy |
| `BOT_SERVICE_ACCOUNT_NAME` | _(none)_ | Optional ServiceAccount for bot pods |
| `BOT_POD_CPU_REQUEST` | `500m` | CPU request |
| `BOT_POD_CPU_LIMIT` | `2000m` | CPU limit |
| `BOT_POD_MEMORY_REQUEST` | `512Mi` | Memory request |
| `BOT_POD_MEMORY_LIMIT` | `4Gi` | Memory limit |
| `BOT_POD_DELETE_GRACE_SECONDS` | `0` | Pod termination grace period |
| `BOT_POD_DELETE_PROPAGATION` | `Background` | Pod deletion propagation policy |
| `BOT_MANAGER_CALLBACK_URL` | _(none)_ | Lifecycle callback URL |
| `BOT_WAITING_ROOM_TIMEOUT_MS` | `300000` | Automatic leave: waiting room timeout |
| `BOT_NO_ONE_JOINED_TIMEOUT_MS` | `120000` | Automatic leave: no-one-joined timeout |
| `BOT_EVERYONE_LEFT_TIMEOUT_MS` | `60000` | Automatic leave: everyone-left timeout |
| `TEAMS_SIGNAL_LOSS_GRACE_MS` | `2000` | Teams speaker signal loss grace period |
| `TEAMS_SPEAKING_KEEPALIVE_MS` | `8000` | Teams speaker keepalive interval |
