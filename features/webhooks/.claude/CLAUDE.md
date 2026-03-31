# Webhooks Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test webhook delivery: bot status changes and transcript-ready events fire webhooks to external endpoints. You dispatch service agents — you don't write code.

### Gate (local)
Bot status changes → webhook fires → external endpoint receives correct payload. PASS: webhook received with correct payload. FAIL: webhook not fired or payload incorrect.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

### Edges
**Crosses:**
- shared-models (webhook schema)
- bot-manager (fires webhooks on status change)
- transcription-collector (fires webhooks on transcript ready)

**Data flow:**
bot-manager → HTTP POST → external URL, transcription-collector → HTTP POST → external URL

### Counterparts
- Service agents: `services/bot-manager`, `services/transcription-collector`
- Lib agents: `libs/shared-models`
- Related features: recording-storage (recording-ready could trigger webhook)

## How to test
1. Dispatch service agents for bot-manager, transcription-collector, shared-models
2. Set up a webhook receiver (e.g., local HTTP server or webhook.site)
3. Configure webhook URL via PUT /user/webhook
4. Trigger bot status change
5. Verify webhook payload at receiver

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
