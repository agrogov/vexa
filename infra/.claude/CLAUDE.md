# Infrastructure Agent

> Shared protocol: [agents.md](../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
Redis streams/pub-sub/queues, PostgreSQL schema, storage backends. Cross-cutting infra that all services depend on.

## What you know

### Redis ([redis.md](../redis.md))
- Redis 7 Alpine, single instance, no persistence (Postgres is source of truth).
- Streams: `transcription_segments` (bot→collector), `speaker_events_relative` (bot→collector).
- Pub/Sub: `tc:meeting:{id}:mutable` (collector→gateway→WS), `meeting:{id}:status` (bot-manager→gateway), `bot_commands:meeting:{id}` (bot-manager→bot).
- Hash: `meeting:{id}:segments` (mutable segment store, TTL 1h).
- Sorted Set: `speaker_events:{session_uid}` (TTL 24h).
- List: `webhook_retry_queue` (failed webhooks with backoff metadata).

### PostgreSQL ([postgresql.md](../postgresql.md))
- PostgreSQL 16, single instance, alembic-managed migrations (3 to date, current: `a1b2c3d4e5f6`).
- 9 tables: users (1,588), meetings (8,537), transcriptions (417K), api_tokens (1,701), meeting_sessions (16K), recordings (2), media_files (2), transcription_jobs (0), alembic_version.
- JSONB data fields on users and meetings. GIN index on meetings.data.
- No backup automation, no connection pooling, all services connect as postgres superuser.

### Storage ([storage.md](../storage.md))
- 3 backends: MinIO (default, Docker Compose), S3 (production), local filesystem (testing).
- Unified `StorageClient` interface in `shared_models/storage.py`. Factory: `create_storage_client()`.
- Default bucket: `vexa-recordings`. Tracked via recordings + media_files tables.
- Low adoption: 2 recordings in production. No upload retry, no lifecycle policies.

### Gate (local)
Redis responds to PING, Postgres passes pg_isready, MinIO bucket exists. PASS: all three checks succeed. FAIL: any infrastructure component unreachable or misconfigured.

### Docs
No docs pages. Docs gate: README → code and code → README only.

## Critical questions
- Are Redis streams being consumed? (check consumer group lag with XINFO)
- Is Postgres schema current? (alembic current vs head)
- Are storage backends accessible from all pods?
- Any Redis memory pressure? (INFO memory)

## After every run
Record consumer lag numbers, alembic version delta, storage accessibility results.

