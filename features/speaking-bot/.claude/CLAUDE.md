# Speaking Bot Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test the speaking bot: bot speaks in the meeting using text-to-speech. You dispatch service agents — you don't write code.

### Gate (local)
POST speak command → tts-service generates audio → bot plays it → meeting participants hear it. PASS: speak command produces audible output in meeting. FAIL: TTS fails, audio not played, or participants cannot hear.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

### Edges
**Crosses:**
- tts-service (text → audio)
- vexa-bot (plays audio via PulseAudio virtual mic)
- bot-manager (relays speak commands)
- api-gateway (speak endpoint)

**Data flow:**
client → api-gateway → bot-manager → bot → tts-service → bot → PulseAudio → meeting audio

### Counterparts
- Service agents: `services/tts-service`, `services/bot-manager`, `services/api-gateway`
- Related features: chat (another interactive bot capability)

## How to test
1. Dispatch service agents for tts-service, bot-manager, api-gateway
2. Start a bot in a mock meeting
3. POST a speak command with text
4. Verify tts-service generates audio
5. Verify bot plays audio into meeting via PulseAudio virtual mic
6. Verify meeting participants can hear the output

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
