# Token Scoping Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test token scoping: creating tokens with specific scopes and verifying scope enforcement. You dispatch service agents — you don't write code.

### Gate (local)
Create token with scope=bot → token can only access bot endpoints, not admin. PASS: scoped token is accepted for in-scope requests and rejected for out-of-scope requests. FAIL: scoped token accesses out-of-scope endpoints.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

### Edges
**Crosses:**
- shared-models (token model + prefixes)
- admin-api (creates scoped tokens)
- api-gateway (enforces scope)

**Data flow:**
admin-api creates → api-gateway enforces

### Counterparts
- Service agents: `services/admin-api`, `services/api-gateway`
- Lib agents: `libs/shared-models`

## How to test
1. Dispatch service agents for admin-api, api-gateway, shared-models
2. Create a token with scope=bot via admin-api
3. Use the token to access bot endpoints (should succeed)
4. Use the token to access admin endpoints (should fail)
5. Verify error response is 403, not 500

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
