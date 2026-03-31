# Lite Integration Findings

## 2026-03-17 Gate Run #3

**Result: PASS — all 8 edges pass**

### Confidence tracking

| Edge | Score | Evidence | Last checked | To reach 90+ |
|------|-------|----------|-------------|--------------|
| 0. Build | 95 | Image 5.62GB (<6GB), 10/10 processes RUNNING, API docs at :8056/docs | 2026-03-17 | — |
| 1. Bot joins mock | 95 | Bot spawned (PID 134), joined mock, detected 3 participants (Alice, Bob, Carol), speaking indicators working | 2026-03-17 | — |
| 2. Audio → transcription | 90 | 3 per-speaker streams captured, GPU transcription (large-v3-turbo) returned 12 segments | 2026-03-17 | — |
| 3. Live WS segments | 85 | WS subscription OK, received `transcript.mutable` messages with speaker-attributed text | 2026-03-17 | Test with longer meeting to verify sustained streaming |
| 4. Persisted transcripts | 90 | 12 segments in DB, 3 speakers, keyword attribution 100% (16/16), 0 cross-contamination | 2026-03-17 | — |
| 5. Recording | 90 | 805KB WebM uploaded to local storage, GET /recordings returns it, /raw download returns valid WebM | 2026-03-17 | — |
| 6. Chat round-trip | 90 | POST chat → bot typed in mock → mock replied → GET chat returns 2 messages (bot + participant) | 2026-03-17 | — |
| 7. SPLM | 90 | 100% keyword attribution (16/16), all 3 speakers correct, well above 70% threshold | 2026-03-17 | Carol's Russian tagged as `en` (language detection issue, not SPLM) |

### Edge Verdicts

| Edge | Description | Verdict |
|------|-------------|---------|
| 0 | Build + startup | **PASS** |
| 1 | Client → API GW → Bot Manager → Bot → Mock | **PASS** |
| 2 | Bot → Redis → TC → Transcription Service | **PASS** |
| 3 | TC → Redis pub/sub → API GW → WS → Client | **PASS** |
| 4 | TC → PostgreSQL → API GW → Client | **PASS** |
| 5 | Bot → Storage → API GW → Client | **PASS** |
| 6 | Client → API GW → Bot → Mock | **PASS** |
| 7 | SPLM | **PASS** |

### Bugs Fixed (this run)

1. **`start_bot_container()` missing `agent_enabled` parameter** (Run #2) — `main.py:901` passes `agent_enabled=req.agent_enabled` but `process.py` didn't accept it.
   - Fix: Added `agent_enabled: Optional[bool] = None` parameter to `start_bot_container()`.

2. **Bot not receiving transcription service config** (Run #2) — Process orchestrator didn't pass `transcriptionServiceUrl` or `transcriptionServiceToken` in BOT_CONFIG. Per-speaker pipeline was disabled.
   - Fix: Added `transcriptionServiceUrl` (from `TRANSCRIBER_URL`) and `transcriptionServiceToken` (from `TRANSCRIBER_API_KEY`) to bot_config dict.

3. **Recording not uploaded — missing `recordingUploadUrl`** (Run #3) — Process orchestrator didn't include `recordingUploadUrl` in BOT_CONFIG. The upload step in `performGracefulLeave()` silently skipped because `currentBotConfig.recordingUploadUrl` was undefined.
   - Fix: Added `"recordingUploadUrl": f"{BOT_CALLBACK_BASE_URL}/internal/recordings/upload"` to bot_config.

4. **`leaveGoogleMeet()` called without botConfig** (Run #3) — `index.ts:554` called `leaveGoogleMeet(page)` without passing botConfig, causing "No bot config provided" warning.
   - Fix: Changed to `leaveGoogleMeet(page, currentBotConfig, reason)`.

5. **Mock meeting lacked chat panel** (Run #3) — The mock HTML had no chat input element, so the bot couldn't send messages.
   - Fix: Added chat panel with `textarea[aria-label="Send a message to everyone"]`, send button, and message display with `[data-message-id]` / `.poVWob` / `.jO4O1` selectors matching Google Meet's DOM.

### Minor Issues (not blocking)

- **Carol's language**: Russian text detected as `en` by transcription service. The text itself is correct Russian. This is a language detection issue in the transcription model, not a pipeline bug.
- **Meeting data mode**: Recordings stored in `meetings.data` JSON (default `RECORDING_METADATA_MODE=meeting_data`) rather than `recordings` table. Both paths work.

### Infrastructure Used

- PostgreSQL: fresh container (postgres:17-alpine) on Docker network
- Transcription: existing GPU cluster (3x workers, large-v3-turbo) on port 8085
- Admin token: standard `test-token`
- Mock meeting: served from inside container on port 8099

### Files Changed

- `services/bot-manager/app/orchestrators/process.py` — Added `agent_enabled` param, `transcriptionServiceUrl`, `transcriptionServiceToken`, `recordingUploadUrl` to BOT_CONFIG
- `services/vexa-bot/core/src/index.ts` — Pass `currentBotConfig` and `reason` to `leaveGoogleMeet()`
- `features/realtime-transcription/mocks/google-meet.html` — Added chat panel (CSS + HTML + JS)
