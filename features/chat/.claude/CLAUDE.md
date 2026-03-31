# Chat Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test meeting chat: bot reads messages from meeting chat and injects messages into meeting chat via API. You dispatch service agents — you don't write code.

### Gate (local)
POST /bots/{id}/chat with message → message appears in meeting chat DOM → GET /bots/{id}/chat returns messages from other participants. PASS: bidirectional chat works (send and receive). FAIL: messages not delivered or not captured.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

### Edges
**Crosses:**
- vexa-bot (DOM chat observer + injection)
- bot-manager (relay)
- api-gateway (chat endpoints)
- Redis (message relay)

**Data flow:**
client → api-gateway → bot-manager → bot → meeting DOM; meeting DOM → bot → Redis → api-gateway → client

### Counterparts
- Service agents: `services/bot-manager`, `services/api-gateway`
- Related features: speaking-bot (another interactive bot capability)

## How to test
1. Dispatch service agents for bot-manager, api-gateway
2. Start a bot in a mock meeting
3. POST /bots/{id}/chat with a test message
4. Verify message appears in the meeting chat DOM
5. Have a mock participant send a message
6. Verify GET /bots/{id}/chat returns that message

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
