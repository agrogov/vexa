# Deployment

## Why
Vexa can be used without any deployment — the hosted service at [vexa.ai](https://vexa.ai) gives you an API key and you start sending bots immediately.

Self-hosting gives you control over your data and infrastructure. Three options, from simplest to most flexible.

## What

### Option 0: Hosted (no deployment)
Get an API key at [vexa.ai/dashboard/api-keys](https://vexa.ai/dashboard/api-keys). Start sending bots. No infrastructure needed.

### Option 1: Lite (easiest self-host)
Single Docker container. Needs external Postgres + transcription service.
See [lite/README.md](lite/README.md).

### Option 2: Docker Compose (development)
Full stack locally. All services, Postgres, Redis.
See [compose/README.md](compose/README.md) and the root Makefile: `make all`.

### Option 3: Helm (production K8s)
Two charts: `vexa` (full) and `vexa-lite` (single-pod).
See [helm/README.md](helm/README.md).

### Transcription service
All self-hosted deployments need a transcription service:
- **Ready to go:** Use Vexa transcription — sign up at [vexa.ai](https://vexa.ai), get a transcription API key. No GPU needed.
- **Self-host:** Run [services/transcription-service](../services/transcription-service/) on your own GPU for full data sovereignty.

## How

### Environment variables
One env-example covers both modes: [env/env-example](env/env-example)

| Variable | Required | Description |
|----------|----------|-------------|
| `DASHBOARD_PATH` | Compose only | Absolute path to vexa-dashboard checkout |
| `TRANSCRIPTION_SERVICE_URL` | Yes | Transcription API endpoint |
| `TRANSCRIPTION_SERVICE_TOKEN` | If needed | Auth token for transcription |
| `LOCAL_TRANSCRIPTION` | No | Set `true` to run GPU transcription locally |
| `REMOTE_DB` | No | Set `true` to use external Postgres |
| `ADMIN_API_TOKEN` | No | Admin API auth token (default: `changeme`) |

### Which mode?
| You want... | Use |
|-------------|-----|
| Use Vexa without deploying anything | Hosted at [vexa.ai](https://vexa.ai) |
| Easiest self-host | Lite |
| Develop / contribute | `make all` (Docker Compose) |
| Production with scaling | Helm |
