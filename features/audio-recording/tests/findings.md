# Audio Recording Test Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Bot captures audio | 85 | 16 recordings from recent bot runs (meeting IDs 8786-8812), all status=completed, webm format, sizes 15KB-4.9MB | 2026-03-17 12:00 | Observe live bot capturing MediaRecorder output in real meeting |
| Recording uploaded to storage | 90 | MinIO bucket vexa-recordings/recordings/ has 29 user dirs; verified direct HTTP 200 download of files at /data/vexa-recordings/recordings/2/{id}/{session}.webm; bot-manager logs show POST /internal/recordings/upload returning 201 Created | 2026-03-17 12:00 | -- |
| Metadata persisted | 85 | meetings.data JSONB contains recording arrays with id, media_files, session_uid, status, created_at. Recordings table only has 2 legacy rows — API uses meeting_data mode | 2026-03-17 12:00 | Verify recordings table is populated alongside meetings.data for consistency |
| Download endpoint works | 90 | GET /recordings/638595733514/media/149462839738/raw returned HTTP 200, content-type audio/webm, 15301 bytes. GET /recordings/479780691227/media/566543050749/raw returned HTTP 200, 4947692 bytes. Both verified as valid WebM by file(1) | 2026-03-17 12:00 | -- |
| Downloaded file playable | 85 | file(1) confirms valid WebM format with Chrome encoder signature. Sizes range from 15KB to 4.9MB, consistent with real audio | 2026-03-17 12:00 | Play back in browser/ffprobe to verify codec and duration |
| Recording-only mode | 0 | Not tested — no bot run with transcription disabled | — | Start bot with recording_enabled=true, transcribe_enabled=false, verify no transcription segments created |

## Gate Verdict: FAIL

Bottleneck: Recording-only mode at score 0. All other checks pass at 85+.

## Surprising Findings

1. **Presigned URL uses internal hostname**: `/download` endpoint returns presigned URL with `minio:9000` (Docker-internal hostname). External clients cannot use this URL. The `/raw` endpoint streams through the API and works correctly from any client. This is a significant UX issue — clients calling `/download` get a URL they cannot reach.

2. **duration_seconds is null for all recordings**: The `RecordingService.writeBlob()` path (used by browser-based bots for WebM) sets `isFinalized = true` without computing duration. Only the WAV path (`appendChunk` + `finalize`) calculates duration from sample count. Since all current recordings are WebM blobs from Chrome's MediaRecorder, none have duration metadata.

3. **Dual storage: recordings table vs meetings.data JSONB**: The `recordings` SQL table has only 2 legacy rows. All 16 recent recordings are stored in `meetings.data` JSONB. The API reads from JSONB via `get_recording_metadata_mode() == "meeting_data"`. The `recordings` table appears unused for new data — potential dead code.

## Docs gate — not run

Skipped: no README found at feature level to gate against. Service-level docs gates are owned by service agents.
