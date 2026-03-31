# Google Meet Realtime Transcription Agent

> Shared protocol: [agents.md](../../../../.claude/agents.md) -- phases, diagnostics, logging, gate rules

## Scope

You test the Google Meet per-speaker audio capture and transcription pipeline: bot joins a Google Meet mock, ScriptProcessor per element captures audio, speaker identity locks via voting, TranscriptionClient sends WAV to transcription-service, confirmed segments publish to Redis, collector persists to Postgres.

### Gate (local)

Bot joins Google Meet mock (3 speakers: Alice, Bob, Carol) -> TranscriptionClient logs show HTTP 200 with non-empty text for all 3 speakers -> segments appear in Redis with correct speaker names -> GET /transcripts returns segments with Alice/Bob/Carol attribution.

**PASS:** All 3 speakers locked, transcription returns non-empty text, segments in Redis and Postgres with correct names.
**FAIL:** Speaker lock fails, transcription returns empty, segments missing, or wrong speaker attribution.

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
- **Platform agent:** `services/vexa-bot/core/src/platforms/googlemeet` (bot-level Google Meet code)
- **Service agents:** `services/bot-manager` (bot lifecycle), `services/transcription-collector` (segment persistence), `services/api-gateway` (delivery)

## How to test

1. Ensure compose stack is running
2. POST to bot-manager to create a bot targeting the Google Meet mock URL
3. Watch bot logs for:
   - `[PerSpeaker] Found N media elements with audio` (expect 3)
   - `[SpeakerIdentity] Track N -> "Alice" LOCKED PERMANENTLY`
   - `[SpeakerIdentity] Track N -> "Bob" LOCKED PERMANENTLY`
   - `[SpeakerIdentity] Track N -> "Carol" LOCKED PERMANENTLY`
   - TranscriptionClient HTTP 200 responses with non-empty text
4. Check Redis: `XLEN transcription_segments`, `HGETALL meeting:{id}:segments`
5. Check REST: `GET /transcripts/{meeting_id}` -- verify 3 speakers present

## Testing on real meetings

When browser-control provides a real meeting URL (`MEETING_READY:<url>`):

1. **Launch bot with `voice_agent_enabled: true`:**
```bash
curl -s -X POST http://localhost:8056/bots \
  -H "X-API-Key: <token>" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"<code>","voice_agent_enabled":true}'
```
WITHOUT `voice_agent_enabled: true`, the bot uses `--use-file-for-fake-audio-capture=/dev/null` which tells Google's SFU "no audio" → SFU forwards 0 packets → bot hears nothing.

2. Wait for bot to reach lobby, signal: `BOT_IN_LOBBY`
3. Browser-control admits, signals: `BOT_ADMITTED`
4. Verify remote audio: `NEW SPEAKER` events in bot logs (maxVal > 0.005)
5. Wait 30-45s for transcription
6. Verify: `GET /transcripts` returns segments with text

## Diagnostic hints

- **No media elements found:** Mock meeting audio not playing, or `<audio>` elements not yet in DOM. Check mock page serves audio correctly.
- **Speaker identity doesn't lock:** Multiple speakers talking simultaneously in mock (no single-speaker window for voting). Check mock has non-overlapping speech segments.
- **Transcription returns empty:** Audio is silence (below 0.005 threshold), or transcription-service is down. Check `docker logs transcription-service`.
- **GC kills audio:** `window.__vexaAudioStreams` not populated. Check `startPerSpeakerAudioCapture()` ran after admission.
- **Bot reports admitted but 0 audio:** FALSE POSITIVE. Check from host side — is bot really in "In the meeting"? If not, admission detection failed. If yes, check `voice_agent_enabled` — without it, SFU won't forward audio.
- **SFU 0 inbound packets:** Bot has `--use-file-for-fake-audio-capture=/dev/null`. Must use `voice_agent_enabled: true`.

## Critical findings

Save to `tests/findings.md`.
