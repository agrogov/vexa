# Shared Models

## Why

ORM models, Pydantic schemas, database sessions, storage abstraction, webhook delivery, and token scoping used by all Python services. Centralizes data layer so services share one source of truth for database schema and validation.

## What

### Documentation
- [Webhooks](../../docs/webhooks.mdx)
- [Token Scoping](../../docs/token-scoping.mdx)

- `models.py` -- SQLAlchemy ORM models (User, APIToken, Meeting, Transcription, MeetingSession, Recording, MediaFile)
- `schemas.py` -- Pydantic request/response schemas, Platform enum
- `token_scope.py` -- prefix-based API token scoping (vxa_bot_, vxa_tx_, vxa_user_, vxa_admin_)
- `webhook_delivery.py` -- durable webhook delivery with Redis retry queue
- `webhook_retry_worker.py` -- background retry worker with exponential backoff
- `storage.py` -- S3/MinIO/local filesystem abstraction
- `database.py` -- SQLAlchemy session factory

## How

```bash
# Install
pip install -e libs/shared-models/

# Run existing tests
cd libs/shared-models
pytest test_token_scope.py test_webhook_delivery_history.py test_webhook_retry.py -v

# Check migration status
alembic current
alembic heads
```
