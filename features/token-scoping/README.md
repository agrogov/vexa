# Token Scoping

## Why

Not every API token should have full access. Token scoping restricts what each token can do — a bot-only token cannot manage users, and a read-only token cannot start bots. This follows the principle of least privilege.

## What

This feature creates API tokens with specific permission scopes and enforces those scopes at the gateway level.

### Documentation
- [Token Scoping](../../docs/token-scoping.mdx)

### Components

- **shared-models**: defines the token model, scope enum, and token prefixes
- **admin-api**: creates scoped tokens (POST /admin/tokens)
- **api-gateway**: reads token scope and enforces access control per endpoint

### Data flow

```
admin-api (create token with scope) → Postgres (store token + scope)
api-gateway (read token scope) → allow/deny request
```

### Key behaviors

- Tokens have a scope field (e.g., bot, admin, read-only)
- Token prefixes indicate scope (visible in the token string)
- api-gateway checks scope before proxying to backend
- Out-of-scope requests return 403
- Unscoped (legacy) tokens have full access for backward compatibility

## How

This is a cross-service feature. Testing requires admin-api and api-gateway running.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Create a scoped token: `POST /admin/tokens` with `scope=bot`
3. Use the token for `GET /bots/status` — should succeed (200)
4. Use the token for `GET /admin/users` — should fail (403)

### Known limitations

- Scope granularity is coarse (per-service, not per-endpoint)
- Legacy tokens without scope get full access
