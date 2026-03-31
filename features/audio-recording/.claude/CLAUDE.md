# Audio Recording Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test audio recording: bot captures meeting audio, saves it to storage, and makes it downloadable. You dispatch service agents — you don't write code.

### Gate (local)
Bot records meeting → recording saved to storage → GET /recordings/{id}/media/{fid}/download returns playable audio. PASS: downloadable audio file is valid and playable. FAIL: recording missing, corrupt, or download endpoint broken.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

### Edges
**Crosses:**
- vexa-bot (MediaRecorder capture)
- bot-manager (upload)
- transcription-collector (metadata)
- api-gateway (serve downloads)
- Storage (MinIO/S3)

**Data flow:**
bot → storage (MinIO/S3) → bot-manager → TC metadata → api-gateway → client download

### Counterparts
- Service agents: `services/bot-manager`, `services/transcription-collector`, `services/api-gateway`
- Related features: post-meeting-transcription (uses recording as source), realtime-transcription (parallel to recording)

## How to test
1. Dispatch service agents for bot-manager, transcription-collector, api-gateway
2. Start a bot in a mock meeting with recording enabled
3. After meeting ends, verify recording exists in storage
4. Verify GET /recordings/{id}/media/{fid}/download returns audio
5. Verify downloaded file is playable

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
