# Vexa Lite Integration Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Why
Lite is a **production Docker image** published to Docker Hub. You own the full pipeline: build → validate → tag → publish. The image must work out of the box for anyone who pulls it.

Individual services have their own tests. You are the final gate — you verify that their code compiles into a working image and that data flows end-to-end. Nothing gets tagged or published unless it passes your gate.

## What
You build the Lite image, validate it against the Google Meet mock (7 integration edges), and publish it. See [README.md "What working means"](../README.md#what-working-means) for the full edge map.

### Pipeline

```
build → validate (edges 0-7) → tag → publish
                                 │
                    FAIL: stop, diagnose, fix/escalate
                                 │
                    PASS: tag version + latest
```

**On every run:**
1. **Build** the image from current code
2. **Validate** all 7 edges against the Google Meet mock
3. **Tag** with version (e.g. `vexa-lite:1.2.3`) if all edges pass
4. **Publish** to Docker Hub — version tag first, then update `latest` only after full validation

`latest` means "this image passed all 7 integration edges." Never tag `latest` on a partially validated build.

### Test specifications

Read [deploy/lite/README.md](../README.md) "What working means" section — those are your test specs. Each edge is an integration point between two components. Verify data crosses each edge correctly.

The README is the single source of truth. Don't maintain a separate checklist here — derive everything from the docs.

### Build

You own `Dockerfile.lite`, `supervisord.conf`, `entrypoint.sh`, and `requirements.txt`. The build packages code from every counterpart into a single production image. If any counterpart's code breaks the build, nothing ships.

**What the build pulls in:**

| Source | Destination in image | Owner agent |
|--------|---------------------|-------------|
| `libs/shared-models/` | `/app/shared-models/` + PYTHONPATH | shared-models |
| `services/api-gateway/` | `/app/api-gateway/` | api-gateway |
| `services/admin-api/` | `/app/admin-api/` | admin-api |
| `services/bot-manager/app/` | `/app/bot-manager/app/` | bot-manager |
| `services/transcription-collector/` | `/app/transcription-collector/` | transcription-collector |
| `services/mcp/` | `/app/mcp/` | mcp |
| `services/tts-service/` | `/app/tts-service/` | tts-service |
| `services/vexa-bot/core/` | `/app/vexa-bot/` (npm ci + build) | vexa-bot |
| `libs/shared-models/alembic/` | `/app/alembic/` | shared-models |

**Build requirements from counterparts:**
- **shared-models:** `pip install` succeeds, `import shared_models` works, models importable
- **api-gateway, admin-api, bot-manager, transcription-collector, mcp, tts-service:** Python code is syntactically valid, no missing imports that crash at startup
- **vexa-bot:** `npm ci` succeeds, `npm run build` produces `/app/vexa-bot/dist/docker.js`
- **All Python services:** compatible with deps in `deploy/lite/requirements.txt` — no conflicting version pins

**Rebuild policy:** Rebuild after any counterpart changes code that ships in the image. The build is your first diagnostic step — if edges break after a counterpart change, rebuild first to pick up their changes.

```bash
# Build from repo root
cd /home/dima/dev/vexa
docker build -f deploy/lite/Dockerfile.lite -t vexa-lite:test .
```

### Gate (local)

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

An **edge** is data crossing a boundary between two components. You test edges, not components. Each edge has an **input** (what you send in on one side) and an **expected output** (what must come out the other side). If the output matches, the edge passes.

Build succeeds + 7 integration edges verified against Google Meet mock (scenario: `full-messy`):

| Edge | Input | Expected output | How to verify |
|------|-------|----------------|---------------|
| **0. Build** | `docker build` on current code | Container starts, supervisord 9/9 RUNNING, API responds on :8056 | `supervisorctl status`, `curl :8056/` |
| **1. Client → Bot → Mock** | `POST /bots` with mock meeting URL | Bot container logs show "admitted", 3 speakers found | `docker logs` bot container, grep for "SPEAKER ACTIVE" |
| **2. Bot → Transcription** | Bot captures audio from mock | `[TranscriptionClient]` logs show HTTP 200 with non-empty text | `docker logs` bot container, grep for "TranscriptionClient" |
| **3. TC → WS → Client** | Transcription segments in Redis | WS client receives `{speaker, text, start_time}` messages | Connect WS to `/ws?api_key=...`, subscribe to meeting, read messages |
| **4. TC → DB → API** | Segments persisted by TC | `GET /transcripts/google_meet/{id}` returns segments with correct speakers and keywords | `curl` the endpoint, validate Alice="dashboard metrics", Bob="infrastructure", Carol=Russian text |
| **5. Bot → Storage → API** | Bot finishes recording | `GET /recordings` returns entry, `GET /recordings/{id}/media/{fid}/download` returns audio bytes | `curl` download, verify non-zero file size |
| **6. Client → Bot chat** | `POST /bots/{platform}/{id}/chat` with message | `GET .../chat` returns the sent message | `curl` POST then GET, compare message text |
| **7. SPLM** | Meeting ends, TC runs deferred processing | Speaker attribution ≥70% correct vs source scenario keywords | Query DB, compare speaker names against scenarios.py ground truth |

**Your gate is not done until you have a PASS or FAIL verdict for every edge, 0 through 7.** Not tested = FAIL. If an edge requires the mock meeting, set it up. If it requires a running bot, spawn one. If it requires env vars, derive them from the compose stack or ask the human. "Needs X" is not a finding — it's a task you haven't done yet.

**PASS:** All 8 verdicts (edge 0-7) are PASS → tag version + update `latest` → publish to Docker Hub.

**FAIL:** Any edge is FAIL or untested → stop, diagnose, fix or escalate to counterpart. Nothing gets tagged or published.

### Confidence tracking

Maintain this table in `tests/findings.md` after every run. Each row is an edge — not a component.

| Edge | Score | Input → Output evidence | Last checked | To reach 90+ |
|------|-------|------------------------|-------------|--------------|
| 0. Build | 0 | -- | -- | Build image, verify supervisord 9/9 |
| 1. Client → Bot → Mock | 0 | -- | -- | POST /bots → bot logs show "admitted" + 3 speakers |
| 2. Bot → Transcription | 0 | -- | -- | Bot logs show TranscriptionClient HTTP 200, non-empty text |
| 3. TC → WS → Client | 0 | -- | -- | WS client receives segments with speaker names |
| 4. TC → DB → API | 0 | -- | -- | GET /transcripts returns segments, keywords match source |
| 5. Bot → Storage → API | 0 | -- | -- | GET /recordings download returns audio bytes |
| 6. Client → Bot chat | 0 | -- | -- | POST chat → GET chat returns same message |
| 7. SPLM | 0 | -- | -- | Speaker attribution ≥70% vs scenarios.py |

All scores start at 0. Update with specific evidence after each check. See [agents.md](../../../.claude/agents.md) for scoring rules (0-95 scale, mock caps at 90, evidence must be specific and timestamped).

### Counterpart agents and requirements

These are the component agents you depend on. You don't own any service — you own the edges between them. For each counterpart, you specify what you **require** from them. If a counterpart doesn't meet its requirements, that edge fails and you escalate to them.

#### api-gateway
- **CLAUDE.md:** `services/api-gateway/.claude/CLAUDE.md`
- **Key files:** `services/api-gateway/main.py`
- **Requirements:**
  - `POST /admin/users` creates a user and returns `{id, email, name}`
  - `POST /admin/users/{id}/tokens` returns `{token: "vx_..."}` — valid API key
  - `POST /bots` with API key proxies to bot-manager and returns bot status
  - `GET /transcripts/{platform}/{meeting_id}` returns `{segments: [{speaker, text, start_time, ...}]}`
  - `GET /recordings` returns recording list; `GET /recordings/{id}/media/{fid}/download` returns audio bytes
  - `POST /bots/{platform}/{id}/chat` proxies to bot-manager; `GET .../chat` returns messages
  - `WS /ws` accepts connection with `?api_key=`, accepts `{action: "subscribe", meetings: [...]}`, streams messages from Redis pub/sub channels `tc:meeting:{id}:mutable` and `va:meeting:{id}:chat`
  - All endpoints reject requests without valid API key (401)

#### bot-manager
- **CLAUDE.md:** `services/bot-manager/.claude/CLAUDE.md`
- **Key files:** `services/bot-manager/app/orchestrators/process.py`
- **Requirements:**
  - On `POST /bots` with `{platform: "google_meet", native_meeting_id: "..."}`, spawns a Node.js bot process (not Docker container) within 5s
  - Bot process appears in `supervisorctl status` or process list
  - Publishes bot status to Redis channel `bm:meeting:{id}:status`
  - Forwards chat messages to the bot process and returns responses
  - On `DELETE /bots/{platform}/{id}`, kills bot process cleanly

#### vexa-bot + googlemeet
- **CLAUDE.md:** `services/vexa-bot/.claude/CLAUDE.md`, `services/vexa-bot/core/src/platforms/googlemeet/.claude/CLAUDE.md`
- **Key files:** `services/vexa-bot/core/src/index.ts`, `services/vexa-bot/core/src/platforms/googlemeet/`
- **Requirements:**
  - Navigates to meeting URL, completes pre-join screen (enters bot name, clicks "Ask to join")
  - Detects admission (meeting screen appears) within 30s
  - Extracts participant names from DOM: must find Alice Johnson, Bob Smith, Carol Williams from mock `.name-tag .notranslate` elements
  - Detects speaking indicators: `.participant-tile.speaking` / `.Oaajhc` CSS classes toggle per the mock schedule

#### vexa-bot/services (audio + speakers + recording)
- **CLAUDE.md:** `services/vexa-bot/core/src/services/.claude/CLAUDE.md`
- **Key files:** `services/vexa-bot/core/src/services/speaker-streams.ts`, `services/vexa-bot/core/src/services/speaker-identity.ts`
- **Requirements:**
  - Captures audio from each participant's `<audio>` element MediaStream via ScriptProcessor/AudioWorklet
  - Writes audio chunks to Redis stream (key pattern: `audio:{session_id}:{speaker}`)
  - Emits `SPEAKER_START` and `SPEAKER_END` events to Redis with `participant_name`, `participant_id_meet`, and `relative_timestamp_ms` — timestamps must be monotonically increasing and correspond to actual speaking periods in the mock
  - Writes combined recording to `LOCAL_STORAGE_DIR` — file must be non-zero, valid WAV or WebM
  - Chat: injects sent messages into the meeting DOM; reads messages from meeting chat panel

#### transcription-collector
- **CLAUDE.md:** `services/transcription-collector/.claude/CLAUDE.md`
- **Key files:** `services/transcription-collector/main.py`, `services/transcription-collector/mapping/speaker_mapper.py`, `services/transcription-collector/background/db_writer.py`
- **Requirements:**
  - Consumes audio chunks from Redis streams written by vexa-bot
  - POSTs audio to transcription service at `TRANSCRIBER_URL` with `Authorization: Bearer {TRANSCRIBER_API_KEY}`
  - Receives transcription segments and maps speakers using `speaker_mapper.py` (timestamp overlap against speaker events)
  - Publishes each new segment to Redis pub/sub channel `tc:meeting:{id}:mutable` as JSON with `{speaker, text, start_time, end_time, ...}`
  - Persists segments to PostgreSQL via `db_writer.py` with correct `speaker`, `text`, `start_time`, `end_time`, `language`
  - Stores recording metadata so `GET /recordings` returns it
  - SPLM: after meeting ends, runs deferred transcription on combined recording, maps speakers with ≥70% accuracy vs source speaker events

#### transcription-service (external)
- **CLAUDE.md:** `services/transcription-service/.claude/CLAUDE.md`
- **Requirements:**
  - Running and reachable at `TRANSCRIBER_URL`
  - `POST /v1/audio/transcriptions` accepts `file` (WAV/WebM), returns `{text, language, duration, segments: [{start, end, text}]}`
  - Detects language correctly: English for Alice/Bob, Russian for Carol
  - Returns segments with timestamps that correspond to actual speech positions in the audio
  - `/health` returns 200 (or `SKIP_TRANSCRIPTION_CHECK=true` is set)

#### shared-models
- **CLAUDE.md:** `libs/shared-models/.claude/CLAUDE.md`
- **Requirements:**
  - DB tables exist after migration: `meetings`, `transcription_segments`, `users`, `api_tokens` (at minimum)
  - `TranscriptionSegment` model has columns: `speaker`, `text`, `start_time`, `end_time`, `language`, `meeting_id`
  - Pydantic schemas match what api-gateway returns to clients

#### infra (PostgreSQL + Redis)
- **CLAUDE.md:** `infra/.claude/CLAUDE.md`
- **Requirements:**
  - PostgreSQL: reachable at `DATABASE_URL`, accepts connections, tables created by migrations
  - Redis: `PING` → `PONG`, supports streams (XADD/XREAD), supports pub/sub (PUBLISH/SUBSCRIBE), no auth required for internal Redis

### Environment

This is what you need to know about where you run, what must exist before you start, and what to protect.

#### What you run on

- **Host:** dev machine or CI runner with Docker daemon
- **Repo:** `/home/dima/dev/vexa` — you build from repo root, context is the full monorepo
- **Docker:** you run `docker build`, `docker run`, `docker exec`, `docker stop/rm` — you have full Docker access
- **Network:** the host can reach external Postgres and transcription service; the container binds port 8056
- **Disk:** build produces ~5.5GB image; container needs space for recordings in `LOCAL_STORAGE_DIR`

#### Environment requirements (must exist before you start)

| Requirement | How to verify | Who provides it |
|-------------|---------------|-----------------|
| Docker daemon running | `docker info` | host / CI |
| Port 8056 free | `lsof -i :8056` or `ss -tlnp \| grep 8056` | you — kill stale containers first |
| PostgreSQL reachable | `pg_isready -h $DB_HOST -p $DB_PORT` | infra agent / external |
| Transcription service reachable | `curl $TRANSCRIBER_URL/../health` | transcription-service agent / external |
| `DATABASE_URL` set | non-empty, valid postgres:// URL | human / CI config |
| `ADMIN_API_TOKEN` set | non-empty string | human / CI config |
| `REMOTE_TRANSCRIBER_URL` set | non-empty, valid HTTP URL | human / CI config |
| `REMOTE_TRANSCRIBER_API_KEY` set | non-empty string | human / CI config |
| No stale test container | `docker ps -a --filter name=vexa-lite-test` | you — clean up before and after |
| Mock meeting WAVs generated | `ls features/realtime-transcription/mocks/cache/full-messy/*.wav` | mock meeting test (generate_audio.py) |

#### Cleanup protocol

Always clean up after a test run, even on failure:
```bash
docker stop vexa-lite-test 2>/dev/null; docker rm vexa-lite-test 2>/dev/null
```
Check for stale containers before starting:
```bash
docker ps -a --filter name=vexa-lite-test --format '{{.ID}}' | xargs -r docker rm -f
```

#### Security and isolation

**Secrets — never leak these:**
- `DATABASE_URL` — contains DB credentials. Never log the full URL. Never write to `test.log` or `findings.md`.
- `ADMIN_API_TOKEN` — grants admin access to the API. Use a test-only value, never a production token.
- `REMOTE_TRANSCRIBER_API_KEY` — grants access to transcription service. Same: test-only, never log.
- `OPENAI_API_KEY` — if set, grants OpenAI API access for TTS.
- API tokens created during test (`vx_...`) — ephemeral but still credentials. Don't log them in findings.

**What to log instead:** log that a secret *is set* or *is empty*, never the value. Example: `ADMIN_API_TOKEN=set (length 10)` not `ADMIN_API_TOKEN=my-secret`.

**Container runs as root:**
- The Lite container runs as root (Playwright/Xvfb requirement). This is normal for this image.
- The container has network access to everything the host can reach. In CI, use network isolation if needed.
- Internal Redis has no auth — this is by design (localhost only inside container). If using external Redis, set `REDIS_PASSWORD`.

**Test data isolation:**
- Each test run should create its own user and meeting. Don't reuse data from previous runs.
- Clean up test meetings from Postgres after test if sharing a DB with other environments.
- Recordings written during test contain audio from the mock (not real meetings) — safe to delete.

**Docker Hub publish safety:**
- Never publish an image that has secrets baked in. Secrets are runtime env vars only — verify with `docker history` and `docker inspect`.
- Tag version first, validate, then update `latest`. Never push `latest` from a failed run.

### Mock meeting setup

The Google Meet mock at `features/realtime-transcription/mocks/google-meet.html` provides:
- 3 participants (Alice, Bob, Carol) with per-speaker WAV audio
- Speaking schedule with overlaps, pauses, noise, multilingual (Russian)
- Scenario: `full-messy` from `features/realtime-transcription/mocks/scenarios.py`
- Known ground truth for validation (keywords per speaker per utterance)

## How
```bash
# Clean up stale containers
docker ps -a --filter name=vexa-lite-test --format '{{.ID}}' | xargs -r docker rm -f

# Build
cd /home/dima/dev/vexa
docker build -f deploy/lite/Dockerfile.lite -t vexa-lite:test .

# Run (needs external postgres + transcription service)
docker run -d --name vexa-lite-test \
  -p 8056:8056 \
  -e DATABASE_URL="postgresql://postgres:postgres@host:5432/vexa" \
  -e ADMIN_API_TOKEN="test-token" \
  -e TRANSCRIBER_URL="https://your-transcription-service/v1/audio/transcriptions" \
  -e TRANSCRIBER_API_KEY="your-key" \
  vexa-lite:test

# Wait for startup
sleep 20

# Prerequisite check (container health)
docker exec vexa-lite-test supervisorctl status
curl -s http://localhost:8056/ | head -5

# Edge 1: Create user, get token, spawn bot against mock
curl -X POST http://localhost:8056/admin/users \
  -H "X-Admin-API-Key: test-token" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "name": "Test"}'
# → get user id, create token, POST /bots with mock meeting URL

# Edge 2-4: Wait for bot to join and transcribe, then:
# GET /transcripts/google_meet/{meeting_id} — check segments
# Validate keywords per speaker against scenarios.py ground truth

# Edge 3: Connect WS, subscribe, verify live segments stream

# Edge 5: GET /recordings — verify audio saved and downloadable

# Edge 6: POST + GET /bots/{platform}/{id}/chat — verify round-trip

# Edge 7: After meeting ends, verify SPLM attribution in transcript

# Cleanup (always, even on failure)
docker stop vexa-lite-test && docker rm vexa-lite-test
```

### After every test run
1. Update the README if specs were unclear
2. Add unexpected findings to `tests/findings.md` — **no secrets in findings**
3. Note what you couldn't test and why
4. The goal: each run makes the docs better, which makes the next run better

