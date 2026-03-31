# Audio Recording

## Why

Users need to revisit meeting audio after the fact — for review, compliance, or re-processing. Audio recording captures the meeting and makes it downloadable.

## What

This feature captures meeting audio using the bot's MediaRecorder, uploads it to object storage, and serves it via a download endpoint.

### Documentation
- [Recording Storage](../../docs/recording-storage.mdx)
- [Recording Only Mode](../../docs/recording-only.mdx)
- [Recordings API](../../docs/api/recordings.mdx)

### Components

- **vexa-bot**: captures meeting audio using MediaRecorder
- **bot-manager**: handles upload of recorded audio to storage
- **transcription-collector**: stores recording metadata
- **api-gateway**: serves recording downloads to clients

### Data flow

```
vexa-bot (MediaRecorder) → storage (MinIO/S3)
bot-manager → transcription-collector (metadata) → Postgres
api-gateway → storage → client (download)
```

### Key behaviors

- Bot captures audio using browser MediaRecorder API
- Recording is uploaded to MinIO/S3 object storage
- Metadata (duration, format, meeting ID) stored in Postgres
- GET /recordings/{id}/media/{fid}/download serves the file
- Recording-only mode available (transcription disabled)

## How

This is a cross-service feature. Testing requires the full compose stack with storage configured.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Start a bot with recording enabled
3. Run the meeting for a few minutes, then end it
4. List recordings: `GET /recordings/{meeting_id}`
5. Download: `GET /recordings/{id}/media/{fid}/download`
6. Verify the downloaded file is playable audio

### Known limitations

- Recording format depends on browser MediaRecorder support
- Large recordings may have slow upload times
- No streaming download — entire file must be downloaded at once
