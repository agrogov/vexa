# Shared Models Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
ORM models, Pydantic schemas, database sessions, storage abstraction, webhook delivery, token scoping. Used by all Python services.

## What you know
- models.py: User, APIToken, Meeting (status: requested→joining→awaiting_admission→active→completed→failed), Transcription, MeetingSession, plus JSONB `data` fields on User and Meeting.
- schemas.py: request/response schemas, Platform enum, voice_agent_enabled defaults to False.
- token_scope.py: prefix-based scoping — vxa_bot_, vxa_tx_, vxa_user_, vxa_admin_. Enforced in api-gateway, bot-manager, admin-api.
- webhook_delivery.py: durable delivery with Redis retry queue, exponential backoff.
- webhook_retry_worker.py: BRPOP from webhook_retry_queue, re-deliver with backoff.
- storage.py: S3/MinIO/local filesystem abstraction.
- database.py: SQLAlchemy session factory.
- test_token_scope.py, test_webhook_delivery_history.py, test_webhook_retry.py: existing tests.

### Gate (local)
All tables exist, alembic version matches head, and models import without error. PASS: `alembic current` equals `alembic heads`, `from shared_models.models import *` succeeds, existing pytest tests pass. FAIL: schema drift, import errors, or test failures.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

## Critical questions
- Do models match actual DB schema? (run alembic check)
- Are token scope prefixes consistent across all 3 enforcing services?
- Does webhook retry actually redeliver? (test_webhook_retry.py passing?)
- Is storage backend accessible from all services that import it?

## After every run
Run existing tests: `pytest test_token_scope.py test_webhook_delivery_history.py test_webhook_retry.py`. Update with results.

