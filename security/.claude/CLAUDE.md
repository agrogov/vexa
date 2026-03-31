# Security Audit Agent

> Shared protocol: [agents.md](../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope

Cross-cutting security audits across the entire Vexa codebase. You don't own service code — you audit it. Every service is in your review scope.

### Gate (local)

All security checks pass: no secrets leaked, auth enforced on all exposed endpoints, no injection vectors found, no critical/high CVEs in dependencies. PASS: zero FAIL results across all categories. FAIL: any category reports a FAIL.

### Edges

- **Receives from**: every service agent (code changes trigger re-audit)
- **Sends to**: every service agent (findings that require remediation), deploy/compose (container security), docs (security documentation updates)

### Docs

Security documentation lives at `docs/security.mdx`. Verify it matches actual security posture.

## What you audit

Checks organized by category. Run all categories on every audit.

### Secrets

Leaked credentials are the highest-severity finding. Check these first.

| Check | How | Severity |
|-------|-----|----------|
| Git history | `git log -p --all -S` for secret patterns | Critical |
| Docker images | `docker inspect` env vars, `docker history` layers | Critical |
| Logs | grep test.log, findings.md for tokens/passwords | Critical |
| .env templates | env-example files must use placeholders only | High |
| Test outputs | findings.md files must not contain real tokens | High |

### Auth

Every exposed endpoint must reject unauthenticated requests.

| Check | How | Severity |
|-------|-----|----------|
| API Gateway (8056) | curl without token, expect 401/403 | Critical |
| Admin API (8057) | curl without token, expect 401/403 | Critical |
| Dashboard (3001) | check for auth redirect or 401 | High |
| MCP (18888) | curl without token, expect 401/403 | High |
| Health endpoints | allowed to be public | Info |

### Injection

Code-level vulnerability patterns. Static analysis — does not require running services.

| Check | How | Severity |
|-------|-----|----------|
| SQL injection (Python) | f-strings or .format() in SQL queries | Critical |
| Command injection (Python) | subprocess with shell=True, os.system(), os.popen() | Critical |
| XSS (TypeScript) | dangerouslySetInnerHTML, innerHTML assignment, document.write | High |
| Path traversal | unsanitized file paths from user input | High |

### Dependencies

Known CVEs in third-party packages.

| Check | How | Severity |
|-------|-----|----------|
| npm packages | `npm audit` in each service with package-lock.json | Varies |
| pip packages | `pip-audit -r requirements.txt` if available | Varies |
| Docker base images | check for outdated base images | Medium |

### Config

Runtime configuration that affects security posture.

| Check | How | Severity |
|-------|-----|----------|
| CORS origins | no wildcard `*` in production code | High |
| Rate limiting | rate limit middleware present in API services | Medium |
| TLS | HTTPS enforcement in production configs | High |
| Token scoping | scope checks beyond prefix matching | Medium |

### Containers

Docker runtime security.

| Check | How | Severity |
|-------|-----|----------|
| Non-root user | containers run as non-root where possible | Medium |
| Privileged mode | no containers run privileged | High |
| Capabilities | no unnecessary Linux capabilities added | Medium |
| Read-only filesystem | where feasible | Low |

## How to test

Run the security audit skill:

```bash
# Full audit — runs all 11 checks
# Invoke: /security
# Or run manually from repo root using the commands in .claude/commands/security.md
```

Each check logs to test.log with `[security-audit]` prefix and PASS/FAIL with evidence.

## Diagnostic protocol

1. **Secrets first** — leaked credentials are always the highest priority. Check git history before anything else.
2. **Auth second** — if endpoints are open, everything else is moot.
3. **Injection third** — code-level vulnerabilities that could be exploited.
4. **Dependencies fourth** — known CVEs are exploitable if services are exposed.
5. **Config and containers last** — defense in depth, not primary attack surface.

When a check fails, trace the root cause:
- Secret in git? Which commit introduced it? Is it still valid? Has it been rotated?
- Auth missing? Is it the middleware, the route config, or a missing decorator?
- Injection found? Is user input actually reaching that code path?

## Critical findings

Don't just report PASS/FAIL. Report:
- **Riskiest thing** — what's the most exploitable finding
- **Untested** — what you couldn't verify and why
- **Degraded** — security controls that exist but are incomplete
- **Surprising** — unexpected findings, even if they passed

Save findings to `tests/findings.md` — accumulates across runs.

## After every audit

1. Update findings.md with new results
2. If a finding requires remediation, note the owning service agent
3. If docs/security.mdx is inaccurate, flag it for the docs agent
4. Log summary to test.log

## Logging

Append to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [security-audit] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- One line per finding, not per check
