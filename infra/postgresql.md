# PostgreSQL

## Why

Persistent storage for users, meetings, transcriptions, and tokens. Redis is ephemeral (no persistence configured) — Postgres is the source of truth for all business data. Every transcript segment that flows through Redis streams eventually flushes here. Every user, API token, bot session, and recording is stored here.

## What

PostgreSQL 16, single instance. Schema managed by Alembic (SQLAlchemy migrations). JSONB data fields on `users` and `meetings` for flexible metadata without schema changes.

### Tables

| Table | Rows (prod import) | Purpose | Key columns |
|-------|-------------------:|---------|-------------|
| `users` | 1,588 | User accounts (OAuth + API) | `email` (unique), `name`, `data` (JSONB), `max_concurrent_bots` |
| `meetings` | 8,537 | Bot sessions per user | `user_id` FK, `platform`, `platform_specific_id`, `status`, `data` (JSONB), `bot_container_id` |
| `transcriptions` | 417,563 | Individual transcript segments | `meeting_id` FK, `start_time`/`end_time` (Float), `text`, `speaker`, `language`, `session_uid` |
| `api_tokens` | 1,701 | Bearer tokens for API auth | `token` (unique), `user_id` FK |
| `meeting_sessions` | 16,552 | Bot connection sessions per meeting | `meeting_id` FK, `session_uid` (unique per meeting), `session_start_time` (tz-aware) |
| `recordings` | 2 | Recording containers (audio/video) | `meeting_id` FK, `user_id` FK, `source` (bot/upload/url), `status` |
| `media_files` | 2 | Individual media artifacts | `recording_id` FK, `type` (audio/video/screenshot), `format`, `storage_path`, `storage_backend` |
| `transcription_jobs` | 0 | Async transcription processing | (unused so far) |
| `alembic_version` | 1 | Migration version tracking | `version_num` |

### Indexes

Notable composite/GIN indexes beyond standard PK and FK:
- `ix_meeting_user_platform_native_id_created_at` — (user_id, platform, platform_specific_id, created_at) for meeting lookup queries
- `ix_meeting_data_gin` — GIN index on meetings.data JSONB for flexible querying
- `ix_transcription_meeting_start` — (meeting_id, start_time) for ordered transcript retrieval
- `ix_recording_meeting_session` — (meeting_id, session_uid)
- `ix_recording_user_created` — (user_id, created_at)

### Relationships

```
users ──1:N──► meetings ──1:N──► transcriptions
  │                │
  │                ├──1:N──► meeting_sessions
  │                └──1:N──► recordings ──1:N──► media_files
  └──1:N──► api_tokens
```

### Migrations

Alembic-managed. 3 migrations to date:

| Version | File | Change |
|---------|------|--------|
| `5befe308fa8b` | `add_data_field_to_users_table.py` | Added JSONB `data` column to users |
| `dc59a1c03d1f` | `add_meeting_data_jsonb_column.py` | Added JSONB `data` column to meetings |
| `a1b2c3d4e5f6` | `add_recordings_media_files_transcription_jobs.py` | Added recordings, media_files, transcription_jobs tables |

Current production version: `a1b2c3d4e5f6` (head).

Models defined in: [`libs/shared-models/shared_models/models.py`](../libs/shared-models/shared_models/models.py)
Alembic config: [`libs/shared-models/alembic/`](../libs/shared-models/alembic/)

## How

### Connection

Two patterns depending on the service:

**URL-based** (bot-manager, api-gateway):
```
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/vexa
```

**Component-based** (transcription-collector, admin-api):
```
DB_HOST=postgres
DB_PORT=5432
DB_NAME=vexa
DB_USER=postgres
DB_PASSWORD=password
```

### Docker Compose

```yaml
postgres:
  image: postgres:16
  environment:
    POSTGRES_DB: vexa
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: password
  ports:
    - "5438:5432"     # host:container
  volumes:
    - postgres-data:/var/lib/postgresql/data
```

Host access: `localhost:5438`. Internal (container-to-container): `postgres:5432`.

### Running migrations

```bash
# Check current version
docker compose exec transcription-collector alembic -c /app/alembic.ini current

# Migrate to head
docker compose exec transcription-collector alembic -c /app/alembic.ini upgrade head

# Via Makefile
make migrate              # upgrade to head
make migration-status     # show current version
make makemigrations M="description"  # create new migration
```

### Direct DB access

```bash
# Docker Compose local
docker compose exec postgres psql -U postgres -d vexa

# Dev stack on BBB
docker exec vexa_dev-postgres-1 psql -U postgres -d vexa
```

### Known limitations

| Area | Status | Detail |
|------|--------|--------|
| **No backup automation** | Risk | No pg_dump cron, no WAL archiving. Manual backups only. |
| **No connection pooling** | Gap | No PgBouncer. Each service opens its own connection pool directly. Works at current scale (~5 services) but won't scale. |
| **No read replicas** | Gap | Single instance. All reads and writes hit the same server. |
| **transcription_jobs unused** | Debt | Table exists but has 0 rows. Created for async transcription but never wired up. |
| **recordings adoption low** | Observation | 2 recordings in production. Feature is implemented but barely used. |
| **No row-level security** | Risk | All services connect as `postgres` superuser. No per-service DB users. |

### References

- Models: [`libs/shared-models/shared_models/models.py`](../libs/shared-models/shared_models/models.py)
- Alembic versions: [`libs/shared-models/alembic/versions/`](../libs/shared-models/alembic/versions/)
- Redis (ephemeral layer): [redis.md](redis.md)
- Storage (media files): [storage.md](storage.md)
