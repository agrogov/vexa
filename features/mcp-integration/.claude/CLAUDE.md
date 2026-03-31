# MCP Integration Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test MCP integration: MCP tool calls through the gateway to the MCP service return meeting data. You dispatch service agents — you don't write code.

### Gate (local)
MCP tool call → returns meeting data. PASS: MCP tool call returns valid meeting data. FAIL: tool call errors or returns empty/malformed response.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

### Edges
**Crosses:**
- mcp (MCP protocol server)
- api-gateway (proxies to mcp)

**Data flow:**
MCP client → api-gateway → mcp service → response

### Counterparts
- Service agents: `services/mcp`, `services/api-gateway`

## How to test
1. Dispatch service agents for mcp, api-gateway
2. Send an MCP tool call via api-gateway's MCP proxy endpoint
3. Verify the response contains valid meeting data
4. Test error cases: invalid tool, missing params

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
