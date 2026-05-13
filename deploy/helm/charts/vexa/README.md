# Vexa Helm Chart

## What
Deploys the Vexa real-time meeting transcription platform to Kubernetes.

## Why
Self-hosted deployment of the full Vexa stack: bot management, per-speaker transcription, real-time delivery via WebSocket, and a dashboard UI.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  Dashboard   │────>│  API Gateway  │────>│  Admin API          │
│  (Next.js)   │     │  (FastAPI)    │     │  (FastAPI)          │
└─────────────┘     └──────┬───────┘     └─────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼───────┐ ┌─────▼──────┐  ┌──────▼─────┐
   │ Meeting API   │ │ Agent API  │  │ Runtime API │
   │ (FastAPI)     │ │ (FastAPI)  │  │ (FastAPI)   │
   └──────┬───────┘ └────────────┘  └──────┬──────┘
          │                                │
   ┌──────▼───────┐                 ┌──────▼──────┐
   │  Bot Pods     │                │   Postgres   │
   │  (Playwright) │                │   Redis      │
   └──────────────┘                └─────────────┘
```

## Services

| Service | Description | Port |
|---------|-------------|------|
| api-gateway | HTTP + WebSocket API entry point | 8000 |
| admin-api | User/token CRUD, meeting management | 8001 |
| meeting-api | Meeting domain — bot lifecycle, transcription pipeline, recordings, webhooks | 8080 |
| runtime-api | Container lifecycle — Docker, K8s, process backends | 8090 |
| transcription-service | GPU inference (Whisper) — optional, can run externally | 8000 |
| mcp | Model Context Protocol server | 18888 |
| tts-service | Text-to-speech | 8002 |
| dashboard | Next.js meeting dashboard | 3000 |
| calendar-service | Calendar sync — auto-schedules bots for upcoming meetings | 8050 |
| agent-api | AI agent chat runtime — streaming, workspaces, scheduling | 8100 |

## Infrastructure

| Component | Description | Default |
|-----------|-------------|---------|
| postgres | Database (bundled, optional) | enabled |
| redis | Stream + pub/sub (bundled, optional) | enabled |
| minio | Object storage for recordings (bundled, optional) | enabled |
| pgbouncer | Connection pooler in front of Postgres (optional) | disabled |

## Bot Orchestration

The meeting-api delegates container lifecycle to Runtime API, which supports three orchestrator modes:

- **process** (default): Bots run as child processes. Simple, no extra permissions.
- **kubernetes**: Bots spawn as separate Pods. Requires RBAC. Best for scale.
- **docker**: Bots spawn as Docker containers. Requires Docker socket mount.

Bot pod configuration (image, resources, node selector) is set via `runtimeApi.browser.*` and rendered into the runtime profiles ConfigMap.

## Transcription Service

The transcription-service requires a GPU. Options:
- **External**: Run on a GPU machine outside K8s. Set `transcriptionService.enabled=false` and configure the URL in meeting-api.
- **In-cluster**: Set `transcriptionService.enabled=true` with a GPU node pool and appropriate tolerations.

## Operational Features

| Feature | Values key | Default |
|---------|-----------|---------|
| Deployment strategy (maxSurge:0) | Applied to all stateless services | enabled |
| Pod anti-affinity (stateful pods) | postgres, redis, minio, tts-service | enabled |
| PgBouncer connection pooler | `pgbouncer.enabled` | false |
| PodDisruptionBudgets | `podDisruptionBudgets.<service>.enabled` | false |
| Redis durability (AOF + appendfsync) | `redis.durability.*` | enabled |
| Postgres idle transaction timeout | `postgres.idleInTransactionTimeoutMs` | 60000 |
| Security context hardening | `global.securityContext` | drop ALL capabilities |
| Migrations Job (ArgoCD PreSync) | `migrations.enabled` | false |

## Configuration

See `values.yaml` for all options. Key overrides for production:

```yaml
secrets:
  existingSecretName: "vexa-secrets"   # Use pre-created K8s secret

database:
  host: "your-postgres-host"           # Only when postgres.enabled=false

ingress:
  enabled: true
  host: "vexa.yourdomain.com"
  className: "nginx"
  tls:
    - secretName: vexa-tls
      hosts: ["vexa.yourdomain.com"]
```
