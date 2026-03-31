# Post-Meeting Transcription

## Why

Live transcription prioritizes speed over accuracy. After the meeting ends, re-transcribing the full recording with the complete audio context produces higher quality output and better speaker mapping.

## What

This feature triggers deferred re-transcription after a meeting ends, producing an improved transcript with better speaker attribution.

### Documentation
- [Deferred Transcription](../../docs/deferred-transcription.mdx)
- [Per-Speaker Audio](../../docs/per-speaker-audio.mdx)

### Components

- **transcription-collector**: triggers deferred processing after meeting ends, runs SPLM (speaker-language mapping)
- **transcription-service**: re-transcribes the full recording with better quality settings
- **bot-services**: provides the full meeting recording

### Data flow

```
recording file → transcription-service (full re-transcription)
                        ↓
              transcription-collector (SPLM)
                        ↓
              Postgres (update transcript)
                        ↓
              api-gateway (serves improved version)
```

### Key behaviors

- Deferred transcription is triggered automatically when meeting ends
- Uses the full recording for better context (vs real-time chunked processing)
- Speaker-language mapping (SPLM) improves speaker attribution
- Updated transcript replaces the real-time version in the database
- API serves the improved version transparently

## How

This is a cross-service feature. Testing requires a completed meeting with a recording.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Run a meeting with known speakers until completion
3. Wait for deferred transcription to trigger
4. Verify `GET /transcripts/{meeting_id}` returns the improved version
5. Compare speaker attribution accuracy: target >=70% correct

### Known limitations

- Deferred processing delay is not well-defined (could be minutes)
- No way to manually trigger re-transcription via API
- Speaker mapping accuracy depends on recording quality
