# MS Teams Realtime Transcription Agent

> Shared protocol: [agents.md](../../../../.claude/agents.md) -- phases, diagnostics, logging, gate rules

## Scope

You test the MS Teams per-speaker transcription pipeline: bot joins a Teams meeting, hooks the single mixed audio stream, routes audio by DOM-based speaker detection (`voice-level-stream-outline` + `vdi-frame-occlusion`), transcribes via TranscriptionClient, and publishes confirmed segments to Redis.

### Gate (local)

Bot joins Teams mock -> audio routed per speaker via DOM signals -> TranscriptionClient logs show HTTP 200 with non-empty text -> segments in Redis with correct speaker names.

**PASS:** Audio routed to correct speakers, transcription returns non-empty text, segments in Redis with correct names.
**FAIL:** Audio not captured, wrong speaker routing, transcription empty, or segments missing.

**Note:** Teams mock meeting does not exist yet. Gate cannot be tested until a mock is built that simulates:
- Single `<audio>` element with MediaStream srcObject
- `[data-tid="voice-level-stream-outline"]` elements in participant tiles
- `vdi-frame-occlusion` class toggling for speaking state
- Participant name elements matching `teamsNameSelectors`

### Edges

| Edge | From | To | What to verify |
|------|------|----|---------------|
| Audio hook | Browser ScriptProcessor (single stream) | `handleTeamsAudioData(name, data)` | Non-silent audio arrives, routed to correct speaker name |
| Speaker detection | MutationObserver on `voice-level-stream-outline` | `speakingStates` map | State transitions fire, `vdi-frame-occlusion` detected |
| Audio routing | `speakingStates` lookup | `__vexaTeamsAudioData()` | Active speaker names resolved, audio sent |
| Transcription | `TranscriptionClient.transcribe()` | transcription-service | HTTP 200, non-empty text |
| Publish | `SegmentPublisher` | Redis `transcription_segments` | XADD succeeds |

### Counterparts

- **Parent:** `features/realtime-transcription` (orchestrator)
- **Platform agent:** `services/vexa-bot/core/src/platforms/msteams` (bot-level Teams code)
- **Service agents:** `services/bot-manager`, `services/transcription-collector`, `services/api-gateway`
- **Sibling:** `features/realtime-transcription/google-meet` (reference implementation)

## How to test

**Currently blocked:** No Teams mock meeting exists.

When mock is available:
1. Ensure compose stack is running
2. POST to bot-manager to create a bot targeting Teams mock URL
3. Watch bot logs for:
   - `[Teams PerSpeaker] Audio routing active on stream {id}`
   - `[TEAMS SPEAKER] "{name}" -- first audio received` for each speaker
   - TranscriptionClient HTTP 200 responses
4. Check Redis: segments with Teams speaker names
5. Check REST: `GET /transcripts/{meeting_id}`

## Diagnostic hints

- **No audio element found:** Teams pre-join screen doesn't have audio until media warm-up completes. Bot must complete join flow first.
- **Speaker detection no signal:** Participant tiles missing `voice-level-stream-outline`. Teams UI may not render these for all participants.
- **Audio routed to wrong speaker:** `speakingStates` map stale, or DOM detection lag. Check `MIN_STATE_CHANGE_MS=200ms` debounce.
- **MS Edge required:** Teams may behave differently in Chromium vs Edge. Bot tries Edge first, falls back to Chromium.

## Critical findings

Save to `tests/findings.md`.
