# Environment Variables

## Why
Vexa needs a `.env` file at the repo root to configure services, ports, and credentials.

## What

One example file covers both deployment modes:

| File | Description |
|------|-------------|
| [env-example](env-example) | All variables with sensible defaults and comments |

Two modes:
- **Default** — external transcription. Set `TRANSCRIPTION_SERVICE_URL`.
- **Local GPU** — set `LOCAL_TRANSCRIPTION=true` to also start transcription-service.

## How

```bash
cp deploy/env/env-example .env
# Edit .env — set TRANSCRIPTION_SERVICE_URL and TRANSCRIPTION_SERVICE_TOKEN
make all
```

For the full variable reference, see [Deployment Guide](https://docs.vexa.ai/deployment).
