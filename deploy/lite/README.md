# [Vexa](../../README.md) Lite Deployment

## Why

Lite is the **production Docker image** for self-hosting Vexa. One container, one port, no Docker socket needed. Pull from Docker Hub and run.

### Documentation
- [Vexa Lite Deployment](../../docs/vexa-lite-deployment.mdx)

```bash
docker pull vexa/vexa-lite:latest
docker run -d -p 8056:8056 \
  -e DATABASE_URL="..." -e ADMIN_API_TOKEN="..." \
  -e REMOTE_TRANSCRIBER_URL="..." -e REMOTE_TRANSCRIBER_API_KEY="..." \
  vexa/vexa-lite:latest
```

The `latest` tag means the image passed all integration edges (build, bot join, transcription, live streaming, chat, recordings, speaker mapping). Version tags (e.g. `1.2.3`) are pinned releases.

You provide: PostgreSQL + a transcription service.
Lite provides: everything else in a single image.

Runs on any platform: EasyPanel, Dokploy, Railway, Render, bare metal.

**Transcription service:** Use Vexa transcription (sign up at [vexa.ai](https://vexa.ai) for a transcription API key — ready to go, no GPU needed), or self-host [transcription-service](../../services/transcription-service/) on your own GPU for full data sovereignty.

## What

Single Docker container running all Vexa services via supervisord:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Lite Container                               │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────┐ │
│  │ API Gateway  │  │  Admin API  │  │ Bot Manager  │  │ MCP  │ │
│  │   :8056      │  │    :8057    │  │    :8080     │  │:18888│ │
│  │  (external)  │  │  (internal) │  │  (internal)  │  │(int.)│ │
│  └──────┬───────┘  └──────┬──────┘  └──────┬───────┘  └──┬───┘ │
│         │                 │                │              │     │
│         └─────────────────┴────────────────┴──────────────┘     │
│                    (routes: /admin/*, /mcp, /bots, /transcripts) │
│                                           │                     │
│                                    spawns processes              │
│                                           ↓                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Bot Processes (Node.js/Playwright)          │    │
│  │         bot-1 (pid)    bot-2 (pid)    bot-3 (pid)       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                          │                                      │
│                     audio stream                                │
│                          ↓                                      │
│                    Redis Stream                                  │
│                          ↓                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Transcription Collector :8123               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ Xvfb :99 │  │ PulseAudio   │  │ TTS Service│  │Redis :6379│ │
│  └──────────┘  └──────────────┘  └────────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────┘
                    │              │
                    ▼              ▼
             ┌──────────────┐  ┌──────────┐
             │ Transcription │  │ Postgres │
             │   Service     │  │(external)│
             │   (remote)    │  │          │
             └──────────────┘  └──────────┘
```

**Bundled services:** [api-gateway](../../services/api-gateway/README.md), [admin-api](../../services/admin-api/README.md), [bot-manager](../../services/bot-manager/README.md), [transcription-collector](../../services/transcription-collector/README.md), [MCP](../../services/mcp/README.md), [TTS](../../services/tts-service/README.md), Redis, Xvfb, PulseAudio.

**Key difference from standard deployment:** Bots spawn as Node.js child processes (process orchestrator), not Docker containers. No Docker socket required.

## How

### Quick start

```bash
# Build
docker build -f deploy/lite/Dockerfile.lite -t vexa-lite .

# Run
docker run -d \
  --name vexa \
  -p 8056:8056 \
  -e DATABASE_URL="postgresql://user:pass@host:5432/vexa" \
  -e ADMIN_API_TOKEN="your-secret-admin-token" \
  -e REMOTE_TRANSCRIBER_URL="http://localhost:8083/v1/audio/transcriptions" \
  -e REMOTE_TRANSCRIBER_API_KEY="your-api-key" \
  vexa-lite
```

**API access:** `http://localhost:8056/docs` (Swagger UI — includes Admin API at `/admin/*`, MCP at `/mcp`)

### Environment variables

#### Required

```bash
docker run -d -p 8056:8056 \
  -e DATABASE_URL="postgresql://user:pass@host:5432/vexa" \
  -e ADMIN_API_TOKEN="your-secret-token" \
  -e REMOTE_TRANSCRIBER_URL="http://host:8083/v1/audio/transcriptions" \
  -e REMOTE_TRANSCRIBER_API_KEY="your-api-key" \
  vexa-lite
```

| Variable | What it does |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection. Also accepts individual vars: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSL_MODE` |
| `ADMIN_API_TOKEN` | Auth token for `/admin/*` endpoints (user creation, token generation) |
| `REMOTE_TRANSCRIBER_URL` | Whisper-compatible transcription endpoint. Alias: `TRANSCRIBER_URL` |
| `REMOTE_TRANSCRIBER_API_KEY` | Bearer token for transcription service. Alias: `TRANSCRIBER_API_KEY` |

#### Redis (optional — internal by default)

Redis runs inside the container. Only set these to use an external Redis:

| Variable | Default | What it does |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | `localhost` = internal Redis server. Set to external host to disable internal. |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | (empty) | Redis auth password |
| `REDIS_URL` | Auto-generated | Full URL. Auto-built from host/port/password if not set. |

#### Recording storage (optional — local filesystem by default)

| Variable | Default | What it does |
|----------|---------|-------------|
| `STORAGE_BACKEND` | `local` | `local`, `minio`, or `s3` |
| `LOCAL_STORAGE_DIR` | `/var/lib/vexa/recordings` | Path inside container. Mount a volume for persistence. |
| `LOCAL_STORAGE_FSYNC` | `true` | fsync writes for durability |

<details>
<summary>MinIO / S3 configuration</summary>

For `STORAGE_BACKEND=minio`:

```bash
-e STORAGE_BACKEND=minio
-e MINIO_ENDPOINT=minio.example.com:9000
-e MINIO_ACCESS_KEY=...
-e MINIO_SECRET_KEY=...
-e MINIO_BUCKET=vexa-recordings
-e MINIO_SECURE=false
```

For `STORAGE_BACKEND=s3` (or S3-compatible):

```bash
-e STORAGE_BACKEND=s3
-e AWS_REGION=us-east-1
-e AWS_ACCESS_KEY_ID=...
-e AWS_SECRET_ACCESS_KEY=...
-e S3_BUCKET=vexa-recordings
-e S3_ENDPOINT=https://provider-endpoint  # optional, for non-AWS S3
-e S3_SECURE=true
```

</details>

#### TTS / Voice agent (optional)

| Variable | Default | What it does |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (empty) | Required for `/speak` endpoint (text-to-speech via OpenAI). Bot voice agent won't work without it. |

#### Local transcription (optional — remote is default)

Only needed if you want to run Whisper inside the container instead of calling a remote service:

| Variable | Default | What it does |
|----------|---------|-------------|
| `DEVICE_TYPE` | `remote` | `cpu` for local faster-whisper |
| `WHISPER_BACKEND` | `remote` | `faster_whisper` for local CPU |
| `WHISPER_MODEL_SIZE` | `tiny` | `tiny`, `small`, `medium`, `large` — bigger = slower + more RAM |

#### Other

| Variable | Default | What it does |
|----------|---------|-------------|
| `LOG_LEVEL` | `info` | `debug`, `info`, `warning`, `error` |
| `SKIP_TRANSCRIPTION_CHECK` | `false` | Skip startup reachability check for transcription service. Only needed for non-Vexa external services without a `/health` endpoint. |

### Create a user and start a bot

```bash
# Create user
curl -X POST "http://localhost:8056/admin/users" \
  -H "X-Admin-API-Key: your-admin-token" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "name": "Test User"}'

# Generate API token
curl -X POST "http://localhost:8056/admin/users/1/tokens" \
  -H "X-Admin-API-Key: your-admin-token"
# → {"token": "vx_abc123..."}

# Start a bot
curl -X POST "http://localhost:8056/bots" \
  -H "X-API-Key: vx_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "google_meet",
    "native_meeting_id": "abc-defg-hij",
    "bot_name": "Vexa Bot",
    "language": "en"
  }'

# Get transcript
curl "http://localhost:8056/transcripts/google_meet/abc-defg-hij" \
  -H "X-API-Key: vx_abc123..."
```

### MCP (Model Context Protocol)

The MCP service lets Claude Desktop, Cursor, and other MCP clients interact with Vexa.

```json
{
  "mcpServers": {
    "Vexa": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8056/mcp", "--header", "Authorization:${VEXA_API_KEY}"],
      "env": { "VEXA_API_KEY": "your-api-key-here" }
    }
  }
}
```

For remote deployments, replace `http://localhost:8056/mcp` with your public URL. See [MCP docs](../../services/mcp/README.md).

### Persistent storage

```bash
docker run -d \
  --name vexa \
  -p 8056:8056 \
  -v vexa-logs:/var/log/vexa-bots \
  -v vexa-recordings:/var/lib/vexa/recordings \
  -e DATABASE_URL="..." \
  -e ADMIN_API_TOKEN="..." \
  -e REMOTE_TRANSCRIBER_URL="..." \
  -e REMOTE_TRANSCRIBER_API_KEY="..." \
  vexa-lite
```

| Volume | Path | Description |
|--------|------|-------------|
| `vexa-logs` | `/var/log/vexa-bots` | Bot process logs |
| `vexa-recordings` | `/var/lib/vexa/recordings` | Recording files (`STORAGE_BACKEND=local`) |

### Management

```bash
docker exec vexa supervisorctl status    # All service statuses
docker logs vexa                          # All stdout
docker logs -f vexa                       # Follow logs
docker exec vexa supervisorctl restart vexa-core:bot-manager  # Restart one service
```

### Platform-specific deployment

<details>
<summary>EasyPanel / Dokploy / Railway / Render</summary>

**EasyPanel:** Create app from Git/Docker image → expose port 8056 → set env vars (`DATABASE_URL`, `ADMIN_API_TOKEN`, `REMOTE_TRANSCRIBER_URL`, `REMOTE_TRANSCRIBER_API_KEY`).

**Dokploy:** Create Application → Docker → use `Dockerfile.lite` → expose 8056 → set env vars → configure PostgreSQL service.

**Railway / Render:** Deploy from GitHub with `Dockerfile.lite` → expose 8056 → add PostgreSQL as managed service → set env vars.

</details>

## What working means

This is the **integration gate**. Individual services have their own tests. This gate verifies the edges between components — data flows end-to-end through the full pipeline against the Google Meet mock (`features/realtime-transcription/mocks/google-meet.html`, scenario: `full-messy`).

### Moving parts and integration edges

```
Client (curl/WS)
  │
  ├─ POST /bots ──→ API Gateway ──→ Bot Manager ──→ spawns Bot process
  │                                                      │
  │                                          Bot ──→ Mock Google Meet
  │                                           │         (meeting.html)
  │                                           │
  │                           ┌───────────────┼───────────────────┐
  │                           │               │                   │
  │                    speaker events    audio streams      recording
  │                           │               │               file
  │                           ▼               ▼                │
  │                        Redis ◄────────────┘                │
  │                           │                                ▼
  │                           ▼                          Storage
  │                  Transcription Collector               (local/S3)
  │                    │             │
  │                    │             ▼
  │                    │     Transcription Service (external)
  │                    │             │
  │                    │    segments + speaker mapping
  │                    │             │
  │                    ▼             ▼
  │                  PostgreSQL (segments, meetings, speakers)
  │                           │
  ├─ WS /ws ──→ API GW ──→ Redis pub/sub ──→ live segments to client
  ├─ GET /transcripts ──→ API GW ──→ TC ──→ PostgreSQL ──→ segments
  ├─ POST/GET /chat ──→ API GW ──→ Bot Manager ──→ Bot ──→ meeting
  └─ GET /recordings ──→ API GW ──→ TC ──→ Storage ──→ audio file
```

### Edges

| # | Edge | What must happen |
|---|------|-----------------|
| 0 | **Build** | `docker build` succeeds, image < 6GB, container starts, supervisord all RUNNING |
| 1 | **Client → API GW → Bot Manager → Bot → Mock** | Bot spawns, navigates to mock, passes admission, detects 3 participants |
| 2 | **Bot → Redis → TC → Transcription Service** | Audio captured from mock WAVs, streamed via Redis, transcribed by external service |
| 3 | **TC → Redis pub/sub → API GW → WS → Client** | Live segments stream to WS client with speaker names, text matches scenario |
| 4 | **TC → PostgreSQL → API GW → Client** | Segments persisted, speaker-attributed, keyword_attribution passes, no cross-contamination, multilingual (Russian) |
| 5 | **Bot → Storage → API GW → Client** | Recording saved, `GET /recordings` lists it, download returns playable audio |
| 6 | **Client → API GW → Bot → Mock (chat)** | `POST /chat` sends message, `GET /chat` returns it |
| 7 | **SPLM** | Post-meeting speaker mapping ≥70% correct vs source, deferred_keyword_attribution passes |

**PASS:** Build + all 7 edges. Data flows from mock meeting through every component and arrives correct at the client.

**FAIL:** Any edge broken. The failing edge number identifies which integration point is broken.

### Prerequisites

- Container healthy: supervisord shows all processes RUNNING, no FATAL
- `DATABASE_URL` connects to external Postgres, tables exist
- `REMOTE_TRANSCRIBER_URL` reachable (or `SKIP_TRANSCRIPTION_CHECK=true`)
- `ADMIN_API_TOKEN` set
- Redis: `redis-cli PING` → PONG

## Comparison with standard deployment

| Feature | Standard (Docker Compose) | Lite |
|---------|---------------------------|------------|
| **Services** | Multiple containers | Single container |
| **Bot Spawning** | Docker containers | Node.js processes |
| **Docker Socket** | Required | Not required |
| **Traefik/Consul** | Included | Not needed |
| **Redis** | External container | Internal (included) |
| **PostgreSQL** | External container | External (required) |
| **Transcription** | GPU/CPU/Remote | Remote (default) or CPU |
| **GPU Support** | Yes | No (uses remote transcription) |
| **Scaling** | Horizontal | Vertical |
| **Max Concurrent Bots** | Unlimited* | depends on VM size |
| **Use Case** | Production, self-hosted | PaaS, simple deployments |

## Limitations

- **Remote Transcription Default:** Requires `REMOTE_TRANSCRIBER_URL` and `REMOTE_TRANSCRIBER_API_KEY`
- **Concurrent Bots:** Depends on VM size — each bot is a Playwright browser process (~300-500MB RAM)
- **Process Isolation:** Less isolated than container-per-bot
- **Redis Persistence:** Internal Redis is ephemeral unless volumes are mounted

## Troubleshooting

### External transcription services without health endpoint

The entrypoint checks `BASE_URL/health` at startup. If your external (non-Vexa) transcription service doesn't expose this, set `SKIP_TRANSCRIPTION_CHECK=true`. The Vexa transcription service has `/health` and works without this.

### Bot fails to start

```bash
docker logs vexa 2>&1 | grep -i "bot-manager"
docker exec vexa supervisorctl status vexa-core:xvfb
```

### Transcriptions not appearing

```bash
docker logs vexa 2>&1 | grep -i "redis"
docker exec vexa env | grep REDIS
```

## Files

| File | Description |
|------|-------------|
| `Dockerfile.lite` | Main Dockerfile |
| `supervisord.conf` | Supervisor configuration |
| `entrypoint.sh` | Container initialization |
| `requirements.txt` | Python dependencies |

## Changes from open source project

**New files:** `deploy/lite/*`, `services/bot-manager/app/orchestrators/process.py`

**Minimal modifications (backwards compatible):**
- `services/bot-manager/app/orchestrators/__init__.py` — loads process orchestrator when `ORCHESTRATOR=process`
- `services/transcription-collector/config.py` — `REDIS_PASSWORD` support
- `services/transcription-collector/main.py` — password parameter in Redis connection
