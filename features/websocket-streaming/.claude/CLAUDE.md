# WebSocket Streaming Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test WebSocket streaming: clients connect, subscribe to a meeting, and receive live transcript segments. You dispatch service agents — you don't write code.

### Gate (local)
Connect WS → subscribe to meeting → receive live transcript segments as they're produced. PASS: segments arrive via WS with correct content and speaker info. FAIL: WS connects but no segments arrive, or segments are malformed.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

### Edges
**Crosses:**
- api-gateway (WS endpoint)
- transcription-collector (publishes to Redis pubsub)
- Redis (pubsub channel)

**Data flow:**
transcription-collector → Redis pubsub → api-gateway WS → client

### Counterparts
- Service agents: `services/api-gateway`, `services/transcription-collector`
- Related features: per-speaker-audio (segments carry speaker attribution)

## How to test
1. Dispatch service agents for api-gateway, transcription-collector
2. Connect to WS endpoint on api-gateway
3. Subscribe to an active meeting
4. Verify live transcript segments arrive
5. Check segment format: text, speaker, timestamp

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
