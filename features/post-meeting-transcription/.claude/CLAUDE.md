# Post-Meeting Transcription Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope

After a meeting ends, re-transcribe the full recording with Whisper batch mode and map speakers using the complete set of speaker events. Produces higher quality transcripts than realtime.

## Why

Realtime transcription works on 3-second audio chunks with incomplete speaker data. Post-meeting has the full recording + all speaker events → better accuracy, better speaker mapping, correct language detection.

## What

### Pipeline

```
Bot exits meeting
  → bot-manager: run_all_tasks(meeting_id)
    → aggregate_transcription: extract participants/languages
    → post_meeting_hooks: fire webhooks

Later (on-demand or automatic):
  POST /meetings/{meeting_id}/transcribe
    → Download full recording from storage (MinIO/S3)
    → POST to transcription-service (Whisper v3 turbo, batch mode)
    → Parse segments with timestamps
    → Map speakers using meeting.data['speaker_events'] (overlap algorithm)
    → Write to Transcription table (PostgreSQL)
    → GET /transcripts now returns improved version (auto-merged)
```

### Speaker mapping algorithm

Source: `bot-manager/app/main.py` `_map_speakers_to_segments()`

1. Build time ranges from speaker events: `(name, start_ms, end_ms)`
2. For each Whisper segment, find speaker with max overlap:
   ```
   overlap = max(0, min(seg_end, range_end) - max(seg_start, range_start))
   ```
3. Best overlap wins

Post-meeting advantage: all events available, no late-arriving events, no incremental updates.

### Transcript serving

`GET /transcripts/{platform}/{native_meeting_id}` auto-merges:
- PostgreSQL immutable segments (from post-meeting)
- Redis mutable segments (from realtime, if still live)
- Dedup by start_time, prefer longer/newer segments

Transparent improvement — when post-meeting completes, next GET returns improved version.

## Gate (local)

Meeting completes → `POST /meetings/{id}/transcribe` → response has segments → speaker attribution ≥70% correct vs known speakers → GET /transcripts returns improved version.

| Check | Score | To reach 90+ |
|-------|-------|-------------|
| Bot exit triggers post-meeting tasks | 0 | Verify run_all_tasks fires |
| Recording available in storage | 0 | Check MinIO/S3 after meeting |
| POST /transcribe returns segments | 0 | Call endpoint, verify response |
| Speaker mapping ≥70% correct | 0 | Compare mapped speakers vs source |
| GET /transcripts serves improved | 0 | Verify merge with post-meeting data |
| Language correctly detected | 0 | Test with Russian speaker |

**Overall: 0/100** — Not tested.

## Edges

**Receives from:**
- bot-in-meeting → completed meeting with recording + speaker events
- audio-recording → recording file in storage

**Sends to:**
- transcription-service → full recording for batch Whisper
- api-gateway → improved transcript via GET /transcripts

## Counterparts
- `services/bot-manager` — triggers post-meeting tasks, hosts /transcribe endpoint
- `services/transcription-collector` — serves merged transcripts via GET /transcripts
- `services/transcription-service` — Whisper batch inference

## Key files
- `services/bot-manager/app/tasks/bot_exit_tasks/` — post-meeting task discovery
- `services/bot-manager/app/main.py:3044` — `POST /meetings/{id}/transcribe`
- `services/bot-manager/app/main.py:3017` — `_map_speakers_to_segments()`
- `services/transcription-collector/api/endpoints.py:151` — transcript merge/dedup (396 lines)
- `services/vexa-bot/tests/messy-meeting/test_deferred.py` — test reference
- `docs/deferred-transcription.mdx` — API docs

## How to test

1. Complete a meeting with known speakers (TTS bots with named voices)
2. Verify recording saved: `GET /recordings`
3. Call: `POST /meetings/{id}/transcribe`
4. Verify: response has segments with speaker names
5. Compare speaker attribution vs known script (line by line)
6. Verify: `GET /transcripts` returns improved version
