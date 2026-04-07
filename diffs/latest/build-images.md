# build-images.sh changes

## Correct Dockerfile path for vexa-bot
- Fixed build command: was using `services/vexa-bot/core/Dockerfile` with context `services/vexa-bot/core`
- Corrected to: `-f services/vexa-bot/Dockerfile services/vexa-bot` (multi-stage Dockerfile at repo root of the service, not inside core/)
- The production Dockerfile sets paths at `/app/vexa-bot/` which the entrypoint.sh expects; the old core/Dockerfile used `/app/` paths causing `cd: /app/vexa-bot/core: No such file or directory` at startup
