# Vexa Helm Chart

## What
Deploys the Vexa real-time meeting transcription platform to Kubernetes.

## Why
Self-hosted deployment of the full Vexa stack: bot management, per-speaker transcription, real-time delivery via WebSocket, AI meeting intelligence, and a dashboard UI.

## Architecture

```
 Browser / API clients
        │
 ┌──────▼────────┐     ┌──────────────┐
 │  API Gateway   │────▶│  Admin API    │
 │  (HTTP + WS)   │     │              │
 └──────┬─────┬──┘     └──────────────┘
        │     │
   ┌────▼─┐   └──────────────────────┐
   │ MCP  │                 ┌────────▼──────┐
   └──────┘                 │  Bot Manager   │
                            └────────┬──────┘
                ┌───────────────┬────┴──────────────┐
                ▼               ▼                    ▼
        ┌──────────────┐  ┌────────────────┐  ┌───────────────┐
        │  Bot Pods     │  │ Transcription  │  │  TTS Service  │
        │  (Playwright) │  │ Service (opt.) │  │  (optional)   │
        └──────┬───────┘  └────────────────┘  └───────────────┘
               │
        ┌──────▼──────────────┐
        │ Transcription        │     ┌──────────────────┐
        │ Collector            │────▶│ Decision Listener │
        └──────┬───────┬──────┘     │ (optional)        │
               │       │            └──────────────────┘
        ┌──────▼──┐  ┌─▼──────┐
        │ Postgres │  │ Redis  │
        └─────────┘  └────────┘

 Bot Manager ──▶ MinIO (recording storage, optional)
```

## Services

| Service | Default | Port | Description |
|---------|:-------:|------|-------------|
| api-gateway | on | 8000 | HTTP + WebSocket API entry point |
| admin-api | on | 8001 | User/token CRUD, meeting management |
| bot-manager | on | 8080 | Spawns and manages meeting bots |
| transcription-collector | on | 8000 | Redis stream → Postgres persistence |
| mcp | on | 18888 | Model Context Protocol server |
| postgres | on | 5432 | Database (bundled, disable to use external) |
| redis | on | 6379 | Stream + pub/sub (bundled, disable to use external) |
| dashboard | **off** | 3000 | Next.js meeting dashboard |
| transcription-service | **off** | 8000 | GPU Whisper inference |
| tts-service | **off** | 8059 | Text-to-speech for bots |
| decision-listener | **off** | 8765 | AI meeting intelligence (decisions, actions, insights) |
| minio | **off** | 9000/9001 | Recording storage (S3-compatible, bundled) |

## Quick Start

```bash
helm install vexa ./helm/charts/vexa \
  --set secrets.adminApiToken=your-secret \
  --set database.host=your-pg-host \
  --set redisConfig.host=your-redis-host
```

## Bot Orchestration

The bot-manager supports four orchestrator modes (`botManager.orchestrator`):

- **process** (default): Bots run as child Node.js processes inside the bot-manager pod. Requires the bot-manager image to include the vexa-bot runtime + Playwright deps. Recommended for small deployments.
- **kubernetes**: Bots spawn as separate Pods via the Kubernetes API. Set `botManager.kubernetesOrchestrator.createRbac=true` to create the required ServiceAccount/Role. Best for scale.
- **docker**: Bots spawn as Docker containers via a mounted Docker socket. Not recommended for standard Kubernetes clusters.
- **nomad**: Bots spawn via Nomad jobs. For hybrid/VM environments.

## Transcription Service

The transcription-service requires a GPU. Options:
- **External** (default): Run on a GPU machine outside K8s. Leave `transcriptionService.enabled=false` and set `botManager.transcriptionServiceUrl`.
- **In-cluster**: Set `transcriptionService.enabled=true` with a GPU node pool.

## Recording (MinIO)

Enable bundled MinIO storage for meeting recordings:

```yaml
minio:
  enabled: true
  defaultBucket: "vexa-recordings"

minioConfig:
  enabled: true   # injects MINIO_* env vars into bot-manager
```

To use an external S3-compatible store, set `minioConfig.enabled=true` and configure `minioConfig.endpoint/bucket/accessKey/secretKey` directly.

## Configuration

See `values.yaml` for all options. Key overrides for production:

```yaml
secrets:
  adminApiToken: "strong-random-token"
  transcriberApiKey: "match-transcription-service-API_TOKEN"

database:
  host: "your-postgres-host"

ingress:
  enabled: true
  host: "gateway.yourdomain.com"
  className: "nginx"
  tls:
    - secretName: vexa-tls
      hosts: ["gateway.yourdomain.com"]
```
