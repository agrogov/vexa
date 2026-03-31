# TTS Service Testing Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test tts-service and ONLY tts-service. Verify it works as described in [README.md](../README.md).

### Gate (local)
POST text, get audio bytes back. PASS: HTTP POST with text returns 200 and a valid audio payload (non-zero bytes, correct content-type). FAIL: endpoint errors or returns empty/corrupt audio.

### Docs
No docs pages. Docs gate: README → code and code → README only.

## How to test
Read the README — Why/What/How and Known Limitations are your test specs. Verify each claim.
Integration points: audio synthesis backend. Verify the TTS endpoint works but don't test upstream dependencies.

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

