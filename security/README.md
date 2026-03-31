# Security

## Why

Vexa handles meeting transcriptions, user data, and API tokens. A single leaked secret or unprotected endpoint can compromise all users. Security is a cross-cutting concern that no single service owns — this agent audits all of them.

## What

Automated security auditing across the Vexa monorepo. Covers:

- **Secret detection** in git history, Docker images, logs, and config templates
- **Auth enforcement** on every exposed API endpoint
- **Injection analysis** for SQL, command, and XSS patterns
- **Dependency scanning** for known CVEs in npm and pip packages
- **Configuration review** for CORS, rate limiting, TLS, and token scoping
- **Container security** for privilege escalation and unnecessary capabilities

This is an audit tool, not a code owner. It reads service code and reports findings. Remediation is the responsibility of each service's agent/owner.

## How

### Run the audit

From any agent context:

```
/security
```

Or manually from repo root — each check in `.claude/commands/security.md` is a standalone bash block.

### Findings

Results are saved to:
- `security/tests/findings.md` — confidence table with scores per check
- `/home/dima/dev/vexa/test.log` — line-per-finding log with `[security-audit]` prefix

### Categories

| Category | What | Severity |
|----------|------|----------|
| Secrets | Leaked credentials anywhere in repo/infra | Critical |
| Auth | Unauthenticated access to protected endpoints | Critical |
| Injection | SQL, command, XSS patterns in code | Critical-High |
| Dependencies | Known CVEs in packages | Varies |
| Config | CORS, rate limits, TLS, token scoping | High-Medium |
| Containers | Root user, privileged mode, capabilities | High-Medium |

### Documentation

Full security documentation: [docs/security.mdx](../docs/security.mdx)

## Known Limitations

- Static analysis only for injection patterns — no dynamic testing (fuzzing, DAST)
- Dependency scanning depends on `npm audit` and `pip-audit` availability
- Container checks require Docker daemon running with Vexa containers up
- Cannot verify TLS configuration without a production-like environment
- Secret detection uses pattern matching — may miss obfuscated or encoded secrets
