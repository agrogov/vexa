# Dashboard Testing Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test dashboard and ONLY dashboard. Verify it works as described in [README.md](../README.md).

### Gate (local)
HTML page loads and renders without console errors. PASS: build succeeds, index page serves, no JS exceptions in browser console. FAIL: build fails, page blank, or uncaught errors on load.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

## How to test
Read the README — Why/What/How and Known Limitations are your test specs. Verify each claim.
Integration points: api-gateway (API calls), auth provider. Verify the app builds and renders but don't test backend internals.

## Critical findings
Don't just report PASS/FAIL. Report:
- **Riskiest thing** — what hurts users most if it breaks
- **Untested** — what you couldn't verify and why
- **Degraded** — slower, more errors, different behavior
- **Surprising** — anything unexpected, even if it passed

Save findings to `tests/findings.md` — accumulates across runs.

## After every test run
1. Update the README if specs were unclear
2. Add unexpected findings to `tests/findings.md`
3. Note what you couldn't test and why
4. The goal: each run makes the docs better, which makes the next run better

