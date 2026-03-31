# Shared Models Test Findings
Date: 2026-03-16 23:45:00
Mode: compose-full (Postgres localhost:5438, Redis via docker)

## Summary
- PASS: 14
- FAIL: 0
- DEGRADED: 1
- SURPRISING: 2

## Test Results
| Suite | Result | Detail |
|-------|--------|--------|
| test_token_scope.py | 15/15 PASS | All scopes, generation, parsing, checking |
| test_webhook_delivery_history.py | 11/11 PASS | Metadata, worker updates, end-to-end |
| test_webhook_retry.py | 13/13 PASS | Enqueue, retry, max-age drop, deliver_one |

## Schema Comparison (ORM vs DB)
| Check | Status | Detail |
|-------|--------|--------|
| Postgres connectivity | PASS | localhost:5438 |
| Redis connectivity | PASS | PONG |
| Alembic version | PASS | a1b2c3d4e5f6 (at head, 3 migrations) |
| Table: users | PASS | exists, columns match ORM |
| Table: api_tokens | PASS | exists, columns match ORM |
| Table: meetings | PASS | exists, columns match ORM incl JSONB data, GIN index |
| Table: transcriptions | PASS | exists, columns match ORM |
| Table: meeting_sessions | PASS | exists, columns match ORM, unique constraint present |
| Table: recordings | PASS | exists, columns match ORM |
| Table: media_files | PASS | exists, columns match ORM (metadata JSONB mapped via extra_metadata) |
| Table: transcription_jobs | SURPRISING | Exists in DB (0 rows) but NO ORM model in models.py. Bot-manager references via cascade delete. |
| users.email unique index | DEGRADED | ORM declares unique=True but DB has partial key (users_email_partial_key) from Supabase/GoTrue. Functionally equivalent but not a standard unique constraint. |
| api_tokens.scope column | PASS | Correctly absent — scoping is prefix-based (vxa_<scope>_<random>), no DB column needed |
| Meeting statuses in DB | PASS | completed, failed, joining present. Other transient statuses (requested, awaiting_admission, active) expected absent from cold data. |

## Token Scope Enforcement
Services using check_token_scope/parse_token_scope:
- api-gateway: services/bot-manager/app/auth.py (likely shared auth)
- bot-manager: services/bot-manager/app/main.py, app/auth.py
- admin-api: services/admin-api/app/main.py
- transcription-collector: services/transcription-collector/api/auth.py

All 4 enforcing services import from shared_models.token_scope. Consistent.

## Risks
1. **transcription_jobs has no ORM model** — any service that needs to query/create transcription_jobs must use raw SQL or a local model. This is a coverage gap that will bite when the transcription pipeline matures.
2. **No alembic.ini** — `alembic` CLI commands fail. Migrations work only via env.py with DATABASE_URL. Makes schema drift detection harder.

## What changed since last run
- `users` table: now exists (was missing last run — likely DB was mid-import)
- Token scope tests: now 15/15 PASS (were 0 collected last run — likely path issue)
- Webhook tests: 24/24 PASS (were untested last run)
- Schema drift: none detected. ORM matches DB for all 7 modeled tables.
