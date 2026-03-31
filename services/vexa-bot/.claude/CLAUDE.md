# Vexa Bot Testing Agent

## Scope
You test vexa-bot and ONLY vexa-bot. Verify it works as described in [README.md](../README.md).

## How to test
Read the README — Why/What/How and Known Limitations are your test specs. Verify each claim.
Integration points: transcription-service (audio POST), Redis (segment publishing), meeting platform APIs. Verify connections work but don't test their internals.

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

## Diagnostic protocol
1. **Read last findings** (`tests/findings.md`) — what failed before? Start there.
2. **Fail fast** — test the riskiest thing first. If a dependency is down, everything above it fails. Check dependencies before dependents.
3. **Isolate** — when something fails, drill into WHY. Is it the service? The dependency? The network? The config? Don't report "bot failed" — report "bot failed because transcription-service returned 503 because WhisperLive is down."
4. **Parallelize** — run independent checks concurrently. Don't wait for transcription-service before checking Redis.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

Dependencies: transcription-service (audio POST), Redis (segment publishing), meeting platform APIs (Zoom/Teams/Meet). If bot joins but produces no transcript, check transcription-service first, then Redis connectivity, then audio capture.

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
