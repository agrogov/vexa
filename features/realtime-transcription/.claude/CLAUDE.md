# Realtime Transcription Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) -- phases, diagnostics, logging, gate rules

## Scope

You test the core realtime transcription pipeline end-to-end: bot joins meeting, captures per-speaker audio, transcribes in real-time, and delivers speaker-attributed segments live via WebSocket and historically via REST. You orchestrate service agents -- you don't write code.

### Gate (local)

3-speaker mock meeting -> live segments arrive via WebSocket with correct speaker names (Alice, Bob, Carol) -> GET /transcripts returns same segments with matching speakers and text.

**PASS:** All 3 speakers appear in WS segments with correct attribution AND REST returns the same segments after immutability (30s).
**FAIL:** Missing speakers, wrong attribution, WS/REST mismatch, or segments never arrive.

### Docs

Your README links to docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using these as your page list:
- `docs/per-speaker-audio.mdx`
- `docs/speaker-events.mdx`
- `docs/websocket.mdx`
- `docs/concepts.mdx`

### Edges

Agent-to-agent boundaries where data crosses:

| Edge | From | To | Data format | Failure mode |
|------|------|----|-------------|--------------|
| Audio capture | Browser (page.evaluate) | Node.js (`handlePerSpeakerAudioData` / `handleTeamsAudioData`) | `(index, number[])` or `(name, number[])` via exposed function | GC collects AudioContext -- no audio arrives |
| Transcription | `TranscriptionClient` | `transcription-service` | HTTP POST multipart WAV | 502/timeout -- buffer grows to hard cap, force-flushes empty |
| Publish | `SegmentPublisher` | Redis stream `transcription_segments` | XADD `{ payload: JSON }` | Redis down -- segments lost |
| Consume | Redis stream | `transcription-collector` | XREADGROUP | Consumer group lag -- delayed delivery |
| Live delivery | `transcription-collector` | `api-gateway` WS | Redis PUBLISH `meeting:{id}:transcription` | No subscribers -- segments in Redis but not on WS |
| Persist | `transcription-collector` background task | Postgres | INSERT after 30s immutability | DB down -- segments stuck in Redis Hash |
| Historical | `api-gateway` REST | Client | JSON merge of Redis Hash + Postgres | Stale data if background task is behind |

### Counterparts

- **Platform agents:** `features/realtime-transcription/google-meet`, `features/realtime-transcription/ms-teams`
- **Service agents:** `services/bot-manager`, `services/transcription-collector`, `services/api-gateway`
- **Related features:** websocket-streaming (WS delivery mechanics), post-meeting-transcription (deferred re-processing)

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Bot joins 3-speaker mock | 90 | 3 speakers found and locked | 2026-03-16 | Test with fresh stack |
| Audio reaches TX service | 90 | HTTP 200 with non-empty text | 2026-03-16 | -- |
| Speaker identity locks | 90 | All 3 locked permanently at 100% | 2026-03-16 | -- |
| Segments in Redis Hash | 90 | 7 segments in DB, meeting 8791 | 2026-03-16 | Verify Redis Hash directly |
| WS live delivery | 0 | Not tested | -- | Connect wscat, subscribe, verify segments arrive |
| REST /transcripts | 90 | 7 segments returned with speakers | 2026-03-16 | -- |
| WS/REST consistency | 0 | Not tested | -- | Compare WS segments to REST output |
| End-to-end latency | 0 | Not tested | -- | Measure speech-to-WS-arrival, expect <5s |

## How to test

1. Ensure compose stack is running (`make all` from `deploy/compose/`)
2. Start a bot in a 3-speaker Google Meet mock meeting
3. Connect to WS: `wscat -c ws://localhost:8056/ws -H "X-API-Key: <token>"`
4. Subscribe to the meeting's transcription channel
5. Verify live segments arrive with correct speaker names (Alice, Bob, Carol)
6. Wait 30s+ for immutability threshold
7. Verify `GET /transcripts/{meeting_id}` returns all segments with matching text and speakers
8. Cross-check: every WS segment should appear in REST, same content

## Critical findings

Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
