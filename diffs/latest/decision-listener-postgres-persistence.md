# feat(decision-listener): persist decisions to Postgres with Redis fallback

## Commit title
`feat(decision-listener): persist detected insights to Postgres with Redis-first read fallback`

## Description
Decisions (action items, key insights, commitments) detected by the decision-listener were previously stored only in Redis with a TTL. Once the TTL expired, all decisions for a meeting were permanently lost. This change adds durable Postgres persistence so decisions survive Redis expiry and are available for historical queries.

### Changes

**`services/decision-listener/db.py`** *(new)*
- Lightweight async SQLAlchemy layer (asyncpg driver).
- No-op when `DB_HOST` is not set, so existing deployments without DB config are unaffected.
- `init_db()` — called at startup, builds connection pool.
- `persist_decision()` — fire-and-forget insert into `meeting_decisions`; failure is logged but never bubbles up to the caller.
- `load_decisions()` — ordered SELECT by `created_at` for a given `meeting_id`.

**`services/decision-listener/listener.py`**
- `_store_decision()` now fires `decision_db.persist_decision()` as an async task after every Redis write (regardless of Redis success/failure).
- New `load_decisions_for_meeting()` helper: tries Redis first; falls back to Postgres when the key is expired or missing. Replaces three duplicated inline Redis-read blocks in `main.py`.

**`services/decision-listener/main.py`**
- Calls `decision_db.init_db()` in the lifespan startup hook.
- `/decisions/{meeting_id}/all`, `/summary/{meeting_id}`, and `/narrative/{meeting_id}` all replaced their inline Redis reads with `load_decisions_for_meeting()`.

**`services/decision-listener/requirements.txt`**
- Added `sqlalchemy>=2.0.0` and `asyncpg>=0.27.0`.

**`services/decision-listener/Dockerfile`**
- Copies and installs `libs/shared-models` before the service requirements so `shared_models.models.MeetingDecision` is available at runtime.

**`libs/shared-models/shared_models/models.py`**
- New `MeetingDecision` ORM model (`meeting_decisions` table): `type`, `summary`, `speaker`, `confidence`, `entities` (JSONB), `created_at`.
- Composite index on `(meeting_id, created_at)` for efficient per-meeting ordered reads.
- `Meeting` model gets a `decisions` relationship with `cascade="all, delete-orphan"`.

**`libs/shared-models/alembic/versions/b2c3d4e5f6a7_add_meeting_decisions_table.py`** *(new)*
- Alembic migration creating the `meeting_decisions` table with all indexes.
- Downgrade drops the table.

**`helm/charts/vexa/templates/deployment-decision-listener.yaml`**
- Injects `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSL_MODE` into the decision-listener container.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD` are sourced from the existing Postgres credentials secret when `postgres.enabled=true`; plain values otherwise.
