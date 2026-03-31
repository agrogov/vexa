# Multi-Platform Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test multi-platform support: same API works across Google Meet, Microsoft Teams, and Zoom. You dispatch service agents — you don't write code.

### Gate (local)
POST /bots with each platform and meeting type -> bot joins platform-specific mock -> captures audio -> transcribes. PASS: all meeting types produce transcripts via the same API. FAIL: any meeting type fails to join, capture, or transcribe.

**Meeting type test matrix:**

| Platform | Meeting type | Test URL pattern |
|----------|-------------|-----------------|
| Google Meet | Standard (`abc-defg-hij`) | `meet.google.com/abc-defg-hij` |
| Google Meet | Custom nickname | `meet.google.com/my-team-standup` |
| MS Teams | Personal (`teams.live.com`) | `teams.live.com/meet/1234567890123?p=PASSCODE` |
| MS Teams | Enterprise (`teams.microsoft.com`) | `teams.microsoft.com/meet/1234567890123?p=PASSCODE` |
| MS Teams | Legacy deep link | `teams.microsoft.com/l/meetup-join/19%3ameeting_...` |
| MS Teams | US Government | `gov.teams.microsoft.us/meet/...` |
| Zoom | Standard | `zoom.us/j/1234567890` |
| Zoom | Regional subdomain | `us05web.zoom.us/j/1234567890?pwd=abc123` |

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

### Edges
**Crosses:**
- vexa-bot (platform-specific join flows)
- googlemeet/msteams/zoom agents (DOM handling)
- bot-manager (platform routing)
- api-gateway (unified API)

**Data flow:**
api-gateway -> bot-manager -> platform-specific bot -> platform-specific mock meeting

### Counterparts
- Service agents: `services/bot-manager`, `services/api-gateway`
- Related features: realtime-transcription (transcription after platform join), audio-recording (recording across platforms)

## How to test
1. Dispatch service agents for bot-manager, api-gateway
2. POST /bots with Google Meet standard URL -> verify bot joins and captures
3. POST /bots with Google Meet custom nickname URL -> verify bot joins and captures
4. POST /bots with Teams personal URL -> verify bot joins and captures
5. POST /bots with Teams enterprise URL -> verify bot joins and captures
6. POST /bots with Teams legacy deep link URL -> verify bot joins and captures
7. POST /bots with Teams government URL -> verify bot joins and captures
8. POST /bots with Zoom standard URL -> verify bot joins and captures
9. POST /bots with Zoom regional subdomain URL -> verify bot joins and captures
10. Verify transcription works for each meeting type
11. Compare: same API call, different platform URLs, same result shape

### Confidence

Full confidence ladders (per-platform, per-meeting-type, with specific gates from 60→99) are in `tests/findings.md`. The ladders define exactly what scenario to test at each level and what score it earns.

**Current scores:** Google Meet 75, Teams 65, Zoom 0, Cross-platform 60. Weighted: 50/100.

**Optimize for coverage:** each new meeting type/URL format that passes raises the score. Don't test the same meeting type twice — test a new one instead.

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
