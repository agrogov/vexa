# Docker Compose Integration Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Why

Compose is the **full stack on one machine**. You own the integration: all services wired together via Docker Compose. Individual services have their own agents and tests. You are the final gate — you verify that their code composes into a working stack and that data flows between services. Nothing is "working" unless `make all` passes.

## What

You build, start, migrate, and validate the full compose stack. See [README.md "What working means"](../README.md#what-working-means) for the full spec.

### Pipeline

```
make all (env → build → up → migrate → test)
    │
    FAIL: stop, diagnose which service broke, dispatch that agent
    │
    PASS: all containers running, 0 restarts, make test green
```

### Gate (local)

`make all` passes. All containers running, 0 restarts, `make test` green. Then dispatch all specialist agents and collect a PASS or FAIL from each one.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

**Your gate is not done until every specialist agent has reported PASS or FAIL on its local gate.** Not dispatched = not tested = FAIL. If an agent needs something to run (mock meeting, env vars, external service), set it up or escalate to the human. Don't report partial results as success.

If any agent fails, dispatch it to fix. Don't debug manually.

### System gate (integration)

When all local agent gates pass, the system gate should emerge: bot joins → transcribes → delivers via API. This is not your gate to fix — it's the result of every agent's local gate passing. If it fails, identify which local gate is broken and dispatch that agent.

### Test specifications

Read [deploy/compose/README.md](../README.md) "What working means" section — those are your test specs. The README is the single source of truth. Don't maintain a separate checklist here — derive everything from the docs.

## Counterpart agents and requirements

You don't own any service — you own the edges between them. For each counterpart, you specify what you **require**. If a counterpart doesn't meet its requirements, that edge fails and you escalate to them.

#### infra (PostgreSQL + Redis + MinIO)
- **CLAUDE.md:** `infra/.claude/CLAUDE.md`
- **Requirements:**
  - PostgreSQL on :5438 — `pg_isready` succeeds, `vexa` database exists
  - Redis — `PING` returns `PONG`, `transcription_segments` stream exists
  - MinIO on :9000 — bucket `vexa-recordings` exists

#### shared-models
- **CLAUDE.md:** `libs/shared-models/.claude/CLAUDE.md`
- **Requirements:**
  - `alembic_version` table exists with current version
  - `users`, `meetings`, `transcriptions`, `api_tokens`, `meeting_sessions`, `recordings`, `media_files` tables exist
  - Zero FK orphans

#### api-gateway
- **CLAUDE.md:** `services/api-gateway/.claude/CLAUDE.md`
- **Requirements:**
  - Port :8056 — returns JSON at `/`, Swagger at `/docs`
  - Proxies to admin-api, bot-manager, transcription-collector, mcp
  - `POST /admin/users` with admin token → 201
  - `POST /admin/users/{id}/tokens` → returns API token
  - `GET /meetings` with API token → returns list
  - `POST /bots` → 201 or 400
  - `GET /bots/status` → bot list
  - `DELETE /bots/{platform}/{id}` → 200 or 404

#### admin-api
- **CLAUDE.md:** `services/admin-api/.claude/CLAUDE.md`
- **Requirements:**
  - Port :8057 — returns JSON at `/`, Swagger at `/docs`
  - CRUD users and tokens works via `X-Admin-API-Key` header

#### bot-manager
- **CLAUDE.md:** `services/bot-manager/.claude/CLAUDE.md`
- **Requirements:**
  - Port :8080 (internal) — health at `/health`
  - Spawns bot containers on `POST /bots`, stops them on `DELETE`
  - Connected to Redis

#### transcription-collector
- **CLAUDE.md:** `services/transcription-collector/.claude/CLAUDE.md`
- **Requirements:**
  - Port :8123 — health at `/health`
  - Connected to Redis and Postgres

#### mcp
- **CLAUDE.md:** `services/mcp/.claude/CLAUDE.md`
- **Requirements:**
  - Port :18888 (internal) — responds to MCP protocol

#### tts-service
- **CLAUDE.md:** `services/tts-service/.claude/CLAUDE.md`
- **Requirements:**
  - Port :8002 (internal) — ready for TTS requests
  - bot-manager → tts-service connected

#### dashboard
- **CLAUDE.md:** `services/dashboard/.claude/CLAUDE.md`
- **Requirements:**
  - Port :3001 — HTML page loads

#### vexa-bot + googlemeet
- **CLAUDE.md:** `services/vexa-bot/.claude/CLAUDE.md`, `services/vexa-bot/core/src/platforms/googlemeet/.claude/CLAUDE.md`
- **Requirements:**
  - Bot navigates to mock meeting URL, joins, captures audio, sends to transcription service
  - Spawned by bot-manager, reports status back via callback

#### transcription-service (external)
- **CLAUDE.md:** `services/transcription-service/.claude/CLAUDE.md`
- **Requirements:**
  - Reachable at `TRANSCRIPTION_SERVICE_URL`
  - Returns transcription text for speech audio

## Environment

### What you run on
- **Host:** dev machine with Docker daemon
- **Repo:** `/home/dima/dev/vexa` — compose files at `deploy/compose/`
- **Docker:** full access — build, compose up/down, exec, logs
- **Network:** host can reach external transcription service; containers on `vexa-network`
- **Ports:** 8056 (api-gateway), 8057 (admin-api), 3001 (dashboard), 5438 (postgres), 9000 (minio)

### Environment requirements (must exist before you start)

| Requirement | How to verify | Who provides it |
|-------------|---------------|-----------------|
| Docker daemon running | `docker info` | host |
| `.env` file | `ls /home/dima/dev/vexa/.env` | `make env` creates from template |
| `DASHBOARD_PATH` set | non-empty, valid path to vexa-dashboard checkout | human |
| `TRANSCRIPTION_SERVICE_URL` set | non-empty, reachable URL | human / transcription-service agent |
| `ADMIN_API_TOKEN` set | non-empty string | `.env` template provides default |
| Ports free | `ss -tlnp \| grep -E '8056\|8057\|3001\|5438\|9000'` | you — `make down` first |
| No stale containers | `docker compose ps` | you — `make down` first |

### Security

- **Never log secrets.** ADMIN_API_TOKEN, DB credentials, API keys — log that they're set, not their values.
- **Test data isolation.** Create test users/meetings per run. Don't reuse data from previous runs.
- **No stale WhisperLive vars.** Verify no container has WhisperLive environment variables.

### Cleanup protocol

Always clean up, even on failure:
```bash
make down
```
Check for stale state before starting:
```bash
make down && docker compose ps  # should be empty
```

## Orchestration

You are the root of the test tree. You do NOT write ad-hoc test scripts. You dispatch the specialist agents that already exist in the repo.

### Specialist agents (20 total)

**Services (9):** api-gateway, admin-api, bot-manager, dashboard, transcription-collector, transcription-service, mcp, tts-service, vexa-bot
**Deploy (3):** compose (this one), helm, lite
**Infra/Libs (2):** infra, shared-models
**Docs (2):** docs, experiments
**Bot platforms (4):** googlemeet, msteams, zoom, bot-services

Each agent has a CLAUDE.md at `{service}/.claude/CLAUDE.md`. Dispatch them — don't reinvent their tests.

### How to dispatch

1. `make up` to bring the stack up
2. Dispatch specialist agents in dependency order:
   - **Wave 1 (infra):** Redis, Postgres, MinIO — dispatch infra agent
   - **Wave 2 (foundation):** transcription-collector, admin-api — dispatch their agents
   - **Wave 3 (dependent):** api-gateway, bot-manager, mcp, tts-service — dispatch their agents
   - **Wave 4 (frontend):** dashboard — dispatch dashboard agent
   - **Wave 5 (gate):** dispatch googlemeet agent + bot-services agent to run the gate test
3. Collect findings, aggregate report
4. If any local gate fails, dispatch the agent that owns the broken component to fix it

### Constraints
- Max 3 concurrent background agents
- Waves ordered by dependency
- Never write ad-hoc test scripts — use the specialist agents
- Gate is binary — no "PASS (DEGRADED)"

### Mock meetings

Platform-specific mock pages served from `https://mock.dev.vexa.ai/`:
- `google-meet.html` — Google Meet mock (DOM, admission flow, WAV speech audio)
- `ms-teams.html` — Teams mock (to be built by msteams agent)
- `zoom.html` — Zoom mock (to be built by zoom agent)

Source: `/home/dima/dev/vexa/features/realtime-transcription/mocks/`
Nginx: `mock.dev.vexa.ai` → that directory

Each platform agent owns building and maintaining its mock.

## How

```bash
# Full test from scratch
make down && rm -f .env && make all

# Quick health check
make test

# Check all containers
make ps

# Check logs for errors
make logs 2>&1 | grep -i "error\|exception\|fatal" | head -20

# Verify database
docker compose exec transcription-collector alembic -c /app/alembic.ini current

# Verify Redis
docker compose exec redis redis-cli ping
docker compose exec redis redis-cli xlen transcription_segments
```

### After every test run
1. Update the README if specs were unclear
2. Add unexpected findings to `tests/findings.md` — **no secrets in findings**
3. Note what you couldn't test and why
4. The goal: each run makes the docs better, which makes the next run better

### Findings format
Each service saves tests/findings.md. You aggregate into tests/results/report-{timestamp}.md.

### Self-improvement
If a service agent's findings contradict the README spec, update the README. Findings bubble up; specs flow down.
