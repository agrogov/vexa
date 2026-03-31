# Token Scoping Test Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Scoped token created | 90 | All 4 scopes (user/bot/tx/admin) created successfully with correct prefixes. user_id=1596, token_ids=2553-2556 | 2026-03-17 11:53 | Test against real production |
| Token prefix matches scope | 90 | vxa_user_, vxa_bot_, vxa_tx_, vxa_admin_ all generated correctly by shared-models/token_scope.py | 2026-03-17 11:53 | -- |
| In-scope access allowed | 90 | user token: GET /meetings=200, POST /bots=201, GET /recordings=200. bot token: POST /bots=409(allowed,conflict), GET /recordings=200. tx token: GET /meetings=200. admin token: all=200/409. | 2026-03-17 11:53 | -- |
| Out-of-scope access denied | 90 | bot token: GET /meetings=403 (correct, tx-collector allows tx/user/admin). tx token: POST /bots=403 (correct, bot-manager allows bot/user/admin), GET /recordings=403 (correct). | 2026-03-17 11:53 | -- |
| Legacy token backward compat | 80 | Code review confirms: parse_token_scope returns None for non-vxa_ tokens, check_token_scope returns True for None scope. Not tested with live legacy token. | 2026-03-17 11:53 | Create a raw DB token without vxa_ prefix, test access |

## Gate verdict: PASS (lowest score: 80)

All checks >= 80. Token scoping is functional and enforced.

## Scope enforcement matrix (actual, tested 2026-03-17)

| Endpoint | Routes to | Allowed scopes | user | bot | tx | admin |
|----------|-----------|---------------|------|-----|-----|-------|
| GET /meetings | transcription-collector | tx, user, admin | 200 | 403 | 200 | 200 |
| POST /bots | bot-manager | bot, user, admin | 201 | 409* | 403 | 409* |
| GET /recordings | bot-manager | bot, user, admin | 200 | 200 | 403 | 200 |

*409 = allowed but meeting already exists (Conflict)

## Architecture finding

Previous finding "Token scoping is prefix-based only -- admin-api ignores scope parameter, all tokens grant same access" is **OUTDATED and WRONG**.

**Current state:** Scope enforcement is real and works. It is implemented in three layers:
1. **shared-models/token_scope.py** -- generates prefixed tokens, parses scopes, checks scope membership
2. **Downstream services** enforce scopes (NOT the api-gateway):
   - bot-manager/app/auth.py: allows `{"bot", "user", "admin"}`
   - transcription-collector/api/auth.py: allows `{"tx", "user", "admin"}`
   - admin-api/app/main.py (user router): allows `{"user", "admin"}`
3. **api-gateway** does NOT enforce scopes -- it forwards X-API-Key headers to downstream services which do the enforcement

## Bugs found

1. **Invalid scope returns 500 instead of 422** -- `POST /admin/users/{id}/tokens?scope=invalid` returns HTTP 500 (Internal Server Error). Root cause: `generate_prefixed_token()` raises `ValueError` which is uncaught in the admin-api endpoint. Should return 422 with a descriptive message listing valid scopes.

## Docs gate -- FAIL

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | Code -> README | Scope enforcement architecture not documented | Enforcement happens in bot-manager and transcription-collector auth.py, not documented in any README |
| 2 | Code -> README | Valid scope values and per-endpoint scope requirements not documented | shared_models/token_scope.py:24 defines VALID_SCOPES, each service auth.py defines allowed scopes, no README covers this |
| 3 | Code -> README | api-gateway does NOT enforce scopes (forwards only) -- this is undocumented | api-gateway/main.py has no scope import/check; downstream services enforce |
