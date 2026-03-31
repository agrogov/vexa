# MCP Integration Test Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| MCP proxy reachable | 90 | POST http://localhost:8056/mcp returns 200 with valid JSON-RPC initialize response, session ID returned in mcp-session-id header | 2026-03-17 11:59 | Test with real MCP client (mcp-remote) |
| Tool call returns data | 90 | tools/call list_meetings via gateway returns isError=false, content contains meetings array with id=8812, platform=google_meet, native_meeting_id=kyr-hxog-eah | 2026-03-17 11:59 | Test with real MCP client |
| Error handling correct | 90 | Invalid tool "nonexistent_tool" returns isError=true with "Unknown tool: nonexistent_tool"; tool call without auth returns isError=true with 401 detail | 2026-03-17 11:59 | -- |
| Auth enforced | 90 | REST endpoint without token returns HTTP 401 "Missing credentials"; MCP tool call without auth header returns isError=true with 401; initialize succeeds without auth (correct per MCP spec — auth is per-tool) | 2026-03-17 11:59 | -- |
| End-to-end pipeline | 90 | MCP client -> gateway:8056/mcp -> mcp:18888/mcp: initialize (session), tools/list (17 tools), tools/call list_meetings (real meeting data), prompts/list (4 prompts). All via Streamable HTTP transport with JSON-RPC. | 2026-03-17 11:59 | Test with real MCP client (Claude Desktop / mcp-remote) |

## Gate verdict: PASS

All checks >= 80. Lowest score: 90 (capped at mock — tested via curl JSON-RPC, not a real MCP client).

## MCP Protocol Details

**Transport:** Streamable HTTP (POST JSON-RPC to /mcp, session via mcp-session-id header)
**Protocol version:** 2024-11-05
**Server:** FastAPI + fastapi-mcp v1.26.0

**Tools exposed (17):** parse_meeting_link, request_meeting_bot, get_meeting_transcript, list_recordings, get_recording, delete_recording, get_recording_media_download, get_recording_config, update_recording_config, get_meeting_bundle, create_transcript_share_link, get_bot_status, update_bot_config, stop_bot, list_meetings, update_meeting_data, delete_meeting

**Prompts exposed (4):** vexa.meeting_prep, vexa.during_meeting, vexa.post_meeting, vexa.teams_link_help

## Gateway proxy

- GET http://localhost:8056/mcp/ returns 307 redirect to http://mcp:18888/mcp (internal hostname, not useful for external clients). This is the trailing-slash redirect from FastAPI, not a proxy bug.
- POST http://localhost:8056/mcp works correctly: gateway forwards JSON-RPC, passes Authorization header, returns session ID.
- Gateway converts X-API-Key to Authorization header for MCP compatibility.

## Docs gate — PASS

No inconsistencies found.

| Direction | Evidence |
|-----------|----------|
| README → code | docs/vexa-mcp.mdx lists 17 tool endpoints; code (main.py) has 17 @app route handlers. Auth methods (Bearer, X-API-Key) match. Self-hosted endpoint documented as localhost:18888, matches code (main.py:933 port=18888). |
| Code → README | All endpoints in main.py are documented in vexa-mcp.mdx. 4 prompts in code match 4 prompts in docs table. MeetingBundleRequest fields match docs table. |
| README → docs | vexa-mcp.mdx references self-hosted-management for admin API (link format correct for docs framework). URL patterns (Bearer token, X-API-Key) consistent. |

## Surprising findings

- MCP initialize works without auth, but tool calls correctly enforce auth. This is proper MCP behavior — the session is established first, then credentials are passed per-request via headers.
- The gateway GET /mcp/ (trailing slash) returns a 307 redirect to the internal hostname `http://mcp:18888/mcp`. External clients using GET for SSE would fail. POST works fine since it doesn't have the trailing-slash redirect issue.
