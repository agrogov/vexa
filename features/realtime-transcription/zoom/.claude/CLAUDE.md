# Zoom Realtime Transcription Agent

> Shared protocol: [agents.md](../../../../.claude/agents.md) -- phases, diagnostics, logging, gate rules

## Scope

You test the Zoom browser-based per-speaker audio capture and transcription pipeline: bot joins a Zoom meeting via the web client (zoom.us/wc/join/{id}), ScriptProcessor per element captures audio, speaker identity locks via voting, TranscriptionClient sends WAV to transcription-service, confirmed segments publish to Redis, collector persists to Postgres.

### Legacy vs New approach

**Legacy (current):** Zoom SDK integration via native binaries in `services/vexa-bot/core/src/platforms/zoom/`. Requires proprietary SDK, self-hosted only, separate codebase from Meet/Teams.

**New (this agent's scope):** Playwright browser joins Zoom web client at `zoom.us/wc/join/{id}` -- same browser-based architecture as Google Meet and Teams. This aligns all 3 platforms on the same codebase: same audio capture (ScriptProcessor), same speaker identity (voting/locking), same transcription pipeline, same testing (mocks).

### Gate (local)

Bot joins Zoom meeting via browser web client (zoom.us/wc/join/{id}), audio capture starts via ScriptProcessor, transcription returns non-empty text, segments appear in Redis with correct speaker names.

**PASS:** Bot joins via browser, media elements found, speakers locked, transcription returns non-empty text, segments in Redis and Postgres with correct names.
**FAIL:** Browser can't load Zoom web client, no media elements found, speaker lock fails, transcription returns empty, or segments missing.

### Edges

| Edge | From | To | What to verify |
|------|------|----|---------------|
| Audio capture | Browser ScriptProcessor | `handlePerSpeakerAudioData()` | Non-silent audio arrives (max amplitude > 0.005) |
| Speaker identity | `queryBrowserState()` | `recordTrackVote()` | Exactly 1 speaker active, vote recorded, lock at 3 votes |
| Transcription | `TranscriptionClient.transcribe()` | transcription-service | HTTP 200, response has non-empty `text` field |
| Publish | `SegmentPublisher` | Redis `transcription_segments` | XADD succeeds, segment has speaker name |
| Consume | Redis stream | transcription-collector | Segment appears in Redis Hash for the meeting |
| Persist | Background task | Postgres | After 30s, segment in `transcription_segments` table |

### Counterparts

- **Parent:** `features/realtime-transcription` (orchestrator)
- **Legacy platform agent:** `services/vexa-bot/core/src/platforms/zoom` (SDK-based Zoom code)
- **Service agents:** `services/bot-manager` (bot lifecycle), `services/transcription-collector` (segment persistence), `services/api-gateway` (delivery)
- **Siblings:** `features/realtime-transcription/google-meet` (reference implementation), `features/realtime-transcription/ms-teams`

### Confidence ladder

| Level | Gate |
|-------|------|
| 0 | Not implemented |
| 30 | Browser navigates to Zoom web client |
| 50 | Bot joins meeting, finds audio elements |
| 70 | Transcription works on mock |
| 80 | Transcription works on real meeting |
| 90 | Multiple meeting URLs |
| 95 | Browser-based replaces SDK approach |

**Current confidence: 0** -- not implemented, scaffold only.

## How to test

Not implemented yet. When implemented:

1. Ensure compose stack is running
2. POST to bot-manager to create a bot targeting a Zoom web client URL
3. Watch bot logs for media element discovery and speaker locking
4. Check Redis: `XLEN transcription_segments`
5. Check REST: `GET /transcripts/{meeting_id}`

## Diagnostic hints

- **Zoom web client won't load:** Check if zoom.us/wc/join/{id} requires authentication or CAPTCHA
- **No media elements found:** Zoom web client may render audio differently from Meet/Teams -- investigate DOM structure
- **Speaker identity doesn't lock:** Zoom speaking indicators differ from Meet/Teams -- need Zoom-specific selectors
- **SDK vs browser confusion:** This agent tests browser-based only. For SDK issues, see `services/vexa-bot/core/src/platforms/zoom/.claude/CLAUDE.md`

## Critical findings

Save to `tests/findings.md`.
