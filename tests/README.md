# Tests

## Why
Every folder has its own testing agent. Tests are derived from docs. Each agent is scoped, self-improving, and delivers critical findings — not just pass/fail.

## What

### Unit tests (per service)
Each service has `tests/` with unit tests that verify code logic. No external dependencies.
- Invoked by: agent in `services/{name}/`
- Scope: that service only

### Integration tests (per service)
Services with external dependencies have `tests/integration/` testing those connections.
- Invoked by: agent in `services/{name}/`
- Scope: this service + its immediate dependencies
- Locations:
  - `services/api-gateway/tests/integration/` — gateway proxy to backend services
  - `services/bot-manager/tests/integration/` — bot lifecycle, Redis pub/sub, K8s pods
  - `services/transcription-collector/tests/integration/` — Redis stream to Postgres pipeline
  - `services/vexa-bot/tests/integration/` — bot to transcription-service, bot to Redis

### Deployment tests (per mode)
Each deploy mode has `.claude/` and `tests/` verifying the full stack.
- Invoked by: agent in `deploy/{mode}/`
- Scope: that deployment mode end-to-end
- Modes: compose, lite, helm

### Pipeline tests (full e2e)
Full pipeline from bot join to transcript delivery.
- Invoked by: agent in `/home/dima/dev/1/operations/`
- Scope: entire system

### Audit tests
Security, config, architecture, and staleness audits.
- Location: `tests/audit/`
- Scripts: security_audit.py, config_audit.py, architecture_audit.py, staleness_audit.py

### Self-improvement
Every agent improves its docs after each run. The README gets more specific, known issues grow, testing gaps shrink. Each run makes the next run better.

## How

### Quick: verify your deployment works
```bash
make test-unit      # unit tests, no Docker needed, < 30 seconds
make test-smoke     # all services healthy? APIs respond? DB connected?
```

### Standard: full test pass before merging
```bash
make test-all       # unit + integration + smoke (< 10 min)
make audit          # security + config + architecture (< 2 min)
```

### Thorough: stress test and deep audit
```bash
make test-full      # unit + integration + smoke + load (< 30 min)
make audit          # all audit scripts
```

### Single service
```bash
cd services/admin-api && pytest tests/ -v
cd services/bot-manager && pytest tests/ -v
```

### To test anything
Start an agent in the relevant folder. It reads the `.claude/CLAUDE.md`, reads the README, and knows what to do.

### Full cycle
See [CYCLE.md](CYCLE.md) — 8 phases, bottom-up, human in the loop.

## Results
Test outputs persist in `results/` directories and are committed. History enables regression detection and baseline comparison.
