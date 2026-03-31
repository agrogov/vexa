# Docs Gate Findings

**Run date:** 2026-03-17
**Result:** 14 FAIL / 1 PASS

---

## Summary

| # | Agent | Result | Blocker count |
|---|-------|--------|---------------|
| 1 | tts-service | PASS | 0 |
| 2 | docs structure | FAIL | 16 |
| 3 | shared-models | FAIL | 2 |
| 4 | transcription-collector | FAIL | 7 |
| 5 | mcp | FAIL | 3 |
| 6 | transcription-service | FAIL | 5 |
| 7 | deploy/compose | FAIL | 3 |
| 8 | admin-api | FAIL | 5 |
| 9 | dashboard | FAIL | 2 |
| 10 | deploy/helm | FAIL | 6 |
| 11 | api-gateway | FAIL | 7 |
| 12 | bot-manager | FAIL | 10 |
| 13 | deploy/lite | FAIL | 5 |
| 14 | infra | FAIL | 6 |
| 15 | vexa-bot | FAIL | 6 |

---

## docs structure

| # | Issue | Evidence |
|---|-------|----------|
| 1 | Orphan page: `docs/meeting-ids.mdx` not in docs.json | File exists, not in navigation |
| 2 | Orphan page: `docs/bot-overview.mdx` not in docs.json | File exists, not in navigation |
| 3 | Orphan page: `docs/per-speaker-audio.mdx` not in docs.json | File exists, not in navigation |
| 4 | Orphan page: `docs/deferred-transcription.mdx` not in docs.json | File exists, not in navigation |
| 5 | Orphan page: `docs/speaker-events.mdx` not in docs.json | File exists, not in navigation |
| 6 | Orphan page: `docs/token-scoping.mdx` not in docs.json | File exists, not in navigation |
| 7 | Orphan page: `docs/recording-only.mdx` not in docs.json | File exists, not in navigation |
| 8 | Stale .md: `docs/platforms/zoom.md` | .md duplicate alongside .mdx |
| 9 | Stale .md: `docs/api/settings.md` | .md duplicate alongside .mdx |
| 10 | Stale .md: `docs/api/meetings.md` | .md duplicate alongside .mdx |
| 11 | Stale .md: `docs/api/recordings.md` | .md duplicate alongside .mdx |
| 12 | Stale .md: `docs/platforms/google-meet.md` | .md duplicate alongside .mdx |
| 13 | Stale .md: `docs/platforms/microsoft-teams.md` | .md duplicate alongside .mdx |
| 14 | Stale .md: `docs/api/voice-agent.md` | .md file with no .mdx counterpart |
| 15 | Stale .md: `docs/api/transcripts.md` | .md duplicate alongside .mdx |
| 16 | Stale .md: `docs/api/bots.md` | .md duplicate alongside .mdx |

---

## shared-models

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README vs docs | Token scoping enforcement: README says `api-gateway`, docs say `transcription-collector` | README.md:15 vs token-scoping.mdx:61 |
| 2 | Code vs docs | webhooks.mdx doesn't document HMAC signing headers (`X-Webhook-Signature`, `X-Webhook-Timestamp`) | webhook_delivery.py `build_headers()` lines 76-81 |
| 3 | Code vs README | `webhook_url.py` (SSRF validation) not in README file inventory | shared_models/webhook_url.py exists, README doesn't list it |
| 4 | Code vs README | `retry.py` not in README file inventory | shared_models/retry.py exists |
| 5 | Code vs README | DB env vars undocumented: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSL_MODE` | database.py lines 15-22 |
| 6 | Code vs README | Storage env vars undocumented (13 vars) | storage.py |

---

## transcription-collector

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README vs code | Port mismatch: README says 8004, Dockerfile says 8000 | README.md:80,104 vs Dockerfile:24,27 |
| 2 | README vs code | `REDIS_DB` documented but doesn't exist in config.py | README.md:89 vs config.py (no REDIS_DB) |
| 3 | Code vs README | `REDIS_PASSWORD` undocumented | config.py:32 |
| 4 | Code vs README | 8 env vars undocumented: `REDIS_SPEAKER_EVENTS_STREAM_NAME`, `REDIS_SPEAKER_EVENTS_CONSUMER_GROUP`, `REDIS_SPEAKER_EVENT_KEY_PREFIX`, `REDIS_SPEAKER_EVENT_TTL`, `BACKGROUND_TASK_INTERVAL`, `IMMUTABILITY_THRESHOLD`, `LOG_LEVEL`, `POD_NAME` | config.py lines 9-24 |
| 5 | Code vs README | 2 endpoints undocumented: `POST /ws/authorize-subscribe`, `GET /internal/transcripts/{meeting_id}` | api/endpoints.py:515,567 |
| 6 | README vs docs | transcripts.mdx documents share endpoints not in this service's code | docs/api/transcripts.mdx:81,135 |
| 7 | Docs vs code | speaker-events.mdx says "2-hour TTL", code defaults to 86400 (24h) | docs/speaker-events.mdx:88 vs config.py:16 |

---

## mcp

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README vs code | Tool name: README says `start_bot`, code says `request_meeting_bot` | README.md:14 vs main.py operation_id |
| 2 | README vs code | Teams enterprise links documented as "not supported" but code handles them | README.md vs main.py:307-319 |
| 3 | Code vs README | config.json port 8056 vs code port 18888 | config.json vs main.py:933, Dockerfile EXPOSE 18888 |
| 4 | Code vs README | 5 tools undocumented: `update_bot_config`, `list_meetings`, `delete_meeting`, `get_recording_config`, `update_recording_config` | main.py |
| 5 | Code vs README | `API_GATEWAY_URL` env var undocumented | main.py:15 |
| 6 | README vs docs | MCP server name: README uses `fastapi-mcp`, docs uses `vexa` | README config vs vexa-mcp.mdx config |
| 7 | README vs code | Zoom ID range: README says 10-11 digits, code validates 9-11 | README.md:90 vs main.py:346 |

---

## transcription-service

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README vs code | `MAX_CONCURRENT_TRANSCRIPTIONS` default: README says 2, code says 20 | README.md env table vs main.py:165 |
| 2 | README vs code+docs | README says "word-level timing", code sets `word_timestamps=False`, docs say segment-level | README.md:103 vs main.py:415 vs concepts.mdx:50 |
| 3 | README vs code | "Ships with one worker" — docker-compose has two uncommented | README.md vs docker-compose.yml worker-1 + worker-2 active |
| 4 | Code vs README | `MAX_ACTIVE_REQUESTS` env var undocumented (takes precedence over MAX_CONCURRENT_TRANSCRIPTIONS) | main.py:165 |
| 5 | Code vs README | Transcription tier system (realtime/deferred) undocumented in README, documented in concepts.mdx | main.py X-Transcription-Tier header, REALTIME_RESERVED_SLOTS |

---

## deploy/compose

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | Docs vs code | `docs/deployment.mdx` references nonexistent `make test-api` | deployment.mdx:177 vs Makefile (no such target) |
| 2 | Docs vs code | `docs/deployment.mdx` references `make test MEETING_ID=...` — no MEETING_ID support | deployment.mdx:157 vs Makefile test target |
| 3 | Code vs README | `TRANSCRIPTION_SERVICE_TOKEN` in env-example + docker-compose but missing from README required table | env-example:10, docker-compose.yml bot-manager:68 |
| 4 | Code vs README | ~15 env vars in docker-compose undocumented in README optional table | docker-compose.yml |
| 5 | README vs docs | docs tells user to `cp` env manually; README says `make all` does it automatically | Minor — not contradictory but confusing |

---

## admin-api

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README vs code | `DB_SSL_MODE` default: README says `disable`, code says `prefer` | README.md vs database.py:22 |
| 2 | README vs code | PATCH field: README says `image`, code says `image_url` | README.md vs schemas.py:327 |
| 3 | README vs code | `GET /admin/users` on analytics_router, not admin-only as README implies | main.py:246 |
| 4 | README vs code | Telematics + user-details endpoints on admin_router (require admin token), README groups under analytics | main.py:538,608 |
| 5 | Code vs README | `webhook_secret` field on `PUT /user/webhook` undocumented | WebhookUpdate model |
| 6 | Code vs README | SSRF validation on webhook URLs undocumented | validate_webhook_url() call |
| 7 | Code vs README | Query params on telematics/user-details endpoints undocumented | main.py |

---

## dashboard

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README+docs vs code | Port mismatch: README and docs say `VEXA_API_URL` default 8056, code defaults to 18056 everywhere | README.md, ui-dashboard.mdx vs 20+ code occurrences of `localhost:18056` |
| 2 | Code vs README | 16 env vars undocumented, including full Microsoft OAuth (`ENABLE_MICROSOFT_AUTH`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID`), `COOKIE_DOMAIN`, `NEXT_PUBLIC_EXTERNAL_AUTH_URL`, `VEXA_PUBLIC_API_URL`, `NEXT_PUBLIC_TRACKER_ENABLED`, `NEXT_PUBLIC_DECISION_LISTENER_URL`, `NOTIFICATIONS_URL`, `NEXT_PUBLIC_BLOG_URL` | Various route files in src/app/api/ |

---

## deploy/helm

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README vs code | `whisperLive.profile` referenced — doesn't exist in chart | README.md:54 vs zero hits in chart |
| 2 | README vs code | Orchestrator options missing `nomad` | README.md:53 vs values.yaml:91 |
| 3 | README vs code | "Caddy LoadBalancer" referenced — no Caddy or LoadBalancer in chart | README.md:77 vs no Caddy template |
| 4 | README vs code | Health probe paths: README says `/health` and `/`, code uses `/docs` | README.md:91-94 vs deployment templates |
| 5 | README vs code | "Stale WhisperLive vars" check criterion — nothing to check | README.md:103 |
| 6 | Code vs README | 8 undocumented config sections: transcriptionService, mcp, dashboard, migrations, bot shm, bot resources, collector Redis config | values.yaml, templates/ |

---

## api-gateway

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README vs code | `POST /meetings/{meeting_id}/transcribe` listed under transcription-collector, actually proxied to bot-manager | README.md:66 vs main.py:488 forwards to BOT_MANAGER_URL |
| 2 | Code vs README | `GET /recordings/{recording_id}/media/{media_file_id}/raw` endpoint undocumented | main.py:440-448 |
| 3 | README vs code | `LOG_LEVEL` env var documented but never read in code | README.md:122 vs no os.getenv("LOG_LEVEL") in main.py |
| 4 | README vs docs | `errors-and-retries.mdx` says `POST /bots` returns 202, code returns 201 | docs/errors-and-retries.mdx:45 vs main.py:228, bot-manager main.py:582 |
| 5 | README vs code | `REDIS_URL` default `redis://redis:6379/0` not documented | main.py:154 |
| 6 | README vs code | WS subscribes to 3 channels, README says 1 (`bm:meeting:{id}:status`) | README.md:147 vs main.py:953-957 (also tc:mutable, va:chat) |
| 7 | README vs code | CORS default: README limitation says "localhost", config table correctly says `localhost:3000,localhost:3001` | README.md:86 vs :121 vs main.py:137 |

---

## bot-manager

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README vs code | `BOT_IMAGE_NAME` default: README says `vexa-bot:latest`, Docker orchestrator uses `vexa-bot:dev` | README.md:97 vs orchestrator_utils.py:42 |
| 2 | README vs code | `ORCHESTRATOR` missing `nomad` option | README.md:107 vs orchestrators/__init__.py:20 |
| 3 | README vs code | `RECORDING_ENABLED` default: README says `false`, Kubernetes orchestrator defaults to `true` | README.md:104 vs kubernetes.py:170 |
| 4 | README vs code | Log format hardcodes `bot_manager`, code uses `%(name)s` | README.md:129 vs main.py:307 |
| 5 | Code vs README | `TRANSCRIPTION_SERVICE_URL` and `TRANSCRIPTION_SERVICE_TOKEN` undocumented | orchestrator_utils.py:241-242 |
| 6 | Code vs README | `TRANSCRIPTION_GATEWAY_URL` undocumented | main.py:3130 |
| 7 | Code vs README | `CORS_ORIGINS` undocumented (default: `localhost:3000,localhost:3001`) | main.py:317 |
| 8 | Code vs README | `ENABLE_RECONCILIATION` and `RECONCILIATION_INTERVAL_SECONDS` undocumented | main.py:474,2698 |
| 9 | Code vs README | `POST_MEETING_HOOKS` undocumented | post_meeting_hooks.py:18 |
| 10 | Code vs README | `DOCKER_HOST` undocumented (default: `unix://var/run/docker.sock`) | orchestrator_utils.py:40 |

---

## deploy/lite

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README vs docs | Docker Hub image: README says `vexa/vexa-lite`, docs say `vexaai/vexa-lite` | README.md vs vexa-lite-deployment.mdx |
| 2 | Docs vs code | `TRANSCRIBER_URL` docs claim default `https://transcription.vexa.ai/...` — code has no default, exits if unset | vexa-lite-deployment.mdx vs entrypoint.sh |
| 3 | README vs code | `DEVICE_TYPE`, `WHISPER_BACKEND`, `WHISPER_MODEL_SIZE` documented but never wired into container | README.md vs Dockerfile.lite, entrypoint.sh, supervisord.conf |
| 4 | README vs docs | `WHISPER_MODEL_SIZE` options: README says `tiny,small,medium,large`, docs say `tiny,base,small,medium` | README.md vs vexa-lite-deployment.mdx |
| 5 | README vs docs | Transcriber var naming: README uses `REMOTE_TRANSCRIBER_*` as primary, docs use `TRANSCRIBER_*` | README.md vs vexa-lite-deployment.mdx |
| 6 | Code vs README | `ADMIN_API_TOKEN` marked required but not validated at startup | entrypoint.sh (no exit on missing) |

---

## infra

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | Docs vs code | redis.md says "no persistence" — compose has `appendonly yes` with volume | redis.md vs docker-compose.yml |
| 2 | Docs vs code | postgresql.md says `postgres:16` — compose uses `postgres:17-alpine` | postgresql.md vs docker-compose.local-db.yml |
| 3 | Docs vs code | postgresql.md says bot-manager uses `DATABASE_URL`, api-gateway connects to PG — both wrong | postgresql.md vs docker-compose.yml (component vars), api-gateway proxies only |
| 4 | Docs vs code | postgresql.md default password: doc says `password`, code says `postgres` | postgresql.md vs docker-compose.local-db.yml `${DB_PASSWORD:-postgres}` |
| 5 | Docs vs code | redis.md documents `REDIS_DB` env var — doesn't exist in config.py | redis.md vs transcription-collector config.py |
| 6 | Docs vs code | redis.md compose snippet stale (missing AOF config, volume, restart policy) | redis.md vs docker-compose.yml |
| 7 | Code vs docs | `DB_SSL_MODE` undocumented in postgresql.md | database.py:22 default `prefer`, compose `disable` |
| 8 | Code vs docs | `REDIS_PASSWORD` undocumented in redis.md | config.py:32 |
| 9 | Code vs docs | 4 speaker event Redis env vars undocumented in redis.md | config.py:13-16 |
| 10 | Code vs docs | `REDIS_CLEANUP_THRESHOLD` set in compose but never read by any code (orphan) | docker-compose.yml |

---

## vexa-bot

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README vs code | Teams speaker identity: README says RTCPeerConnection metadata, code uses DOM traversal | README.md:39 vs speaker-identity.ts:273 `traverseTeamsDOM()` |
| 2 | README vs code | Speaker resolution: README says "one-time, cached", code uses voting/locking (LOCK_THRESHOLD=3, LOCK_RATIO=0.7) | README.md:37 vs speaker-identity.ts:30-31 |
| 3 | README vs code | Pub/Sub channel: README says `tc:meeting:{id}:mutable`, code publishes to `meeting:{id}:segments` | README.md:175 vs segment-publisher.ts:192 |
| 4 | Code vs README | 14+ BOT_CONFIG fields undocumented: `transcriptionServiceUrl`, `transcriptionServiceToken`, `botManagerCallbackUrl`, `recordingEnabled`, `captureModes`, `recordingUploadUrl`, `voiceAgentEnabled`, `transcriptionTier`, `transcribeEnabled`, `language`, `task`, `reconnectionIntervalMs`, `container_name`, `defaultAvatarUrl` | docker.ts:6-36, types.ts:1-34 |
| 5 | Code vs README | 6 services missing from key modules table: `chat.ts`, `screen-content.ts`, `screen-share.ts`, `tts-playback.ts`, `microphone.ts`, `hallucination-filter.ts` | core/src/services/ |
| 6 | README vs code | "~2s dashboard latency" — actual floor is `minAudioDuration` (2s) + network + transcription | index.ts:1020 minAudioDuration=2 |

---

## Cross-cutting patterns

### 1. Stale claims (code evolved, docs didn't follow)
- Speaker identity mechanism (vexa-bot)
- Redis persistence (infra)
- Worker count (transcription-service)
- Teams support (mcp)
- Postgres version (infra)

### 2. Default mismatches
- Ports: 8004 vs 8000 (collector), 8056 vs 18056 (dashboard), 8056 vs 18888 (mcp config)
- Concurrency: MAX_CONCURRENT 2 vs 20 (transcription-service)
- SSL: `disable` vs `prefer` (admin-api/database)
- Image names: `vexa-bot:latest` vs `vexa-bot:dev` (bot-manager), `vexa/` vs `vexaai/` (lite)

### 3. Undocumented env vars (most common finding)
- bot-manager: 7 missing
- dashboard: 16 missing
- transcription-collector: 9 missing
- deploy/compose: ~15 missing
- infra: 5+ missing

### 4. Cross-doc contradictions
- Token scope enforcement: README says api-gateway, docs say transcription-collector (shared-models)
- POST /bots status code: 202 in docs, 201 in code (api-gateway)
- Speaker event TTL: 2h in docs, 24h in code (transcription-collector)
- Whisper model options differ between README and docs (deploy/lite)
