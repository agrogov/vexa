# MCP Integration

## Why

AI assistants (Claude, etc.) need structured access to meeting data. The Model Context Protocol (MCP) provides a standard interface for AI tools to query meetings, transcripts, and recordings without custom API integration.

## What

This feature exposes Vexa meeting data through the MCP protocol, allowing AI assistants to use MCP tool calls to access meetings, transcripts, and recordings.

### Documentation
- [Vexa MCP](../../docs/vexa-mcp.mdx)

### Components

- **mcp**: MCP protocol server that implements tool handlers for meeting data
- **api-gateway**: proxies MCP requests to the mcp service

### Data flow

```
MCP client → api-gateway → mcp service → Postgres/backend → response
```

### Key behaviors

- MCP tool calls are JSON-RPC formatted
- Available tools: list meetings, get transcript, get recording, etc.
- Authentication via API token (same as REST API)
- Gateway proxies MCP requests transparently to the mcp service
- Error responses follow MCP/JSON-RPC error format

## How

This is a cross-service feature. Testing requires api-gateway and mcp service running.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Send an MCP tool call via the gateway's MCP endpoint
3. Verify the response contains valid meeting data
4. Test error handling: invalid tool name, missing parameters

### Known limitations

- MCP protocol version compatibility not documented
- No streaming support for large responses
- Session management is stateless (no persistent MCP sessions)
