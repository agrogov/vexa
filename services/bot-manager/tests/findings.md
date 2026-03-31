# Bot Manager Test Findings
Date: 2026-03-17 14:25:00
Mode: compose-full (gateway at localhost:8056)

## Summary
- PASS: 10
- FAIL: 1
- DEGRADED: 2
- UNTESTED: 4
- SURPRISING: 3

## Results
| Status | Test | Detail |
|--------|------|--------|
| PASS | Dependencies up | Redis PONG, Postgres OK, bot-manager container 0 restarts |
| PASS | GET /bots/status (auth) | 200, returns running_bots array |
| PASS | GET /bots/status (no auth) | 403 "Missing API token" |
| PASS | GET /bots/status (bad auth) | 403 "Invalid API token" |
| PASS | POST /bots (Google Meet) | 201, container launched, meeting record created. Bot runs 3.5+ min without false alone-timeout. |
| PASS | POST /bots (Teams + mock) | 201, container launched, full pipeline: join->audio->speakers->transcription->Redis. Mock regression confirmed. |
| PASS | POST /bots (Teams + real meeting) | 201, container launched, joins lobby with passcode URL, admitted by host, audio pipeline active with muted tracks. |
| PASS | DELETE /bots (running bot) | 202 accepted, bot cleaned up, concurrency slot freed |
| PASS | POST /bots (concurrency limit) | 403 "maximum concurrent bot limit (1)" when bot already running |
| PASS | GET /recordings | 200, empty list |
| PASS | GET /recording-config | 200, returns {enabled: false, capture_modes: ["audio"]} |
| FAIL | PUT /recording-config | 500: `StaleDataError: UPDATE statement on table 'users' expected to update 1 row(s); 2 were matched` |
| DEGRADED | PUT /recording-config | All payloads return 500 due to duplicate user IDs in database |
| DEGRADED | Teams real meeting: lobby flow | Bot only appears in host lobby when meeting URL includes passcode (?p=...). Without passcode, bot enters wrong meeting context. |
| SURPRISING | POST /bots (Zoom) | 500: "ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET environment variables are required for Zoom platform" — creates meeting record before failing, leaving orphan DB row |
| SURPRISING | Users table | No PRIMARY KEY constraint on users.id (only btree index), allowing duplicate rows. This is the root cause of the recording-config 500. |
| SURPRISING | Teams muted track handling | Bot tries track.muted=false which fails (read-only property). Harmless but logs misleading error. |

## Bot Bug Fix Verification (2026-03-17)

### Fix 1: Google Meet alone-timeout (VERIFIED)
- Bot entered real Google Meet (qar-hfhb-iap) with host present
- Bot ran 3.5+ minutes without triggering alone-timeout
- Participant detection: 2 tiles (host + bot), 1 unique from central list
- Audio: 3 streams captured, 3 media elements found
- Bot stopped only when explicitly deleted via API

### Fix 2: Teams muted-tracks (VERIFIED)
- Bot entered real Teams meeting (9361440405892) with passcode
- Found 5 media elements, all with muted=true tracks
- Fix accepts muted tracks: connected 5 audio streams
- MediaRecorder started, audio routing active
- Bot did NOT exit after 30s (previous bug)
- Mock regression: all 3 speakers transcribed correctly

### Fix confidence scores
| Fix | Score | Evidence |
|-----|-------|----------|
| Google Meet alone-timeout | 95% | 3.5min run, no false timeout with host present |
| Teams muted-tracks | 95% | 5 muted tracks accepted, pipeline running, mock passed |

## Root Cause Chains

### PUT /recording-config 500 (existing)
`PUT /recording-config` -> `update_recording_config` -> `db.commit()` -> SQLAlchemy `StaleDataError` -> UPDATE matched 2 rows instead of 1 -> users table has duplicate IDs -> **users.id has no PRIMARY KEY or UNIQUE constraint**.

### Teams lobby passcode requirement (new finding)
Without passcode: `teams.live.com/meet/<id>` -> launcher -> `teams.live.com/v2/` (full app) -> pre-join timeout -> wrong meeting context.
With passcode: `teams.live.com/meet/<id>?p=<code>` -> launcher -> light-meetings -> "Continue on this browser" -> correct lobby -> host can admit.

## What was untested
- **Internal callbacks** — require a running bot container that calls back; can't simulate without mocking
- **Voice agent controls** (speak/chat/screen/avatar) — require active bot with meeting
- **Deferred transcription** — POST /meetings/{id}/transcribe returns 404 for nonexistent meeting (correct), but can't test with real recording
- **Webhook delivery** — logs show "No webhook URL configured" for test user; webhook runner logic works but actual HTTP delivery untested

## Previous findings (2026-03-16)
- All previous PASS results confirmed still passing
- Previous SURPRISING on POST /bots Zoom still reproduces identically
- Previous DEGRADED on curl-in-container still applies (no curl in bot-manager image)

---

# Bot Lifecycle Findings - 2026-03-17

## Test: Teams bot crash after admission

### Setup
- Meeting: https://teams.live.com/meet/9380435891213?p=TDTR5kxMos4ATtzbrw
- Bot ID: 8903, Container: vexa-bot-8903-455aa0d2
- Strategy: Pre-attached log tailing to capture crash output before container dies

### Result: NO CRASH OBSERVED

The Teams bot completed the full lifecycle successfully:
1. **Launch** - Bot created and container started
2. **Pre-join** - Navigated to Teams, found pre-join controls, configured virtual camera
3. **Join** - Clicked join, status changed to `joining`
4. **Admission** - Host (Dima) admitted the bot
5. **Active** - Status changed to `active`, post-join setup completed
6. **Running** - Stable for 6+ minutes with no errors

### What worked:
- PulseAudio + virtual microphone setup
- Redis connection and session management
- Browser navigation through Teams launcher flow
- Virtual camera injection via `getUserMedia` + `RTCPeerConnection` patching
- `replaceTrack` to inject canvas stream into 7 WebRTC video senders
- Per-speaker pipeline: VAD, ring buffer, speaker detection (Dmitry Grankin detected)
- Audio recording: MediaRecorder with `audio/webm;codecs=opus`
- Chat service + transcript injection
- Voice agent mode (TTS playback service)

### Minor observations:
- Teams silent auth frame returns `login_required` - expected for anonymous join, not an error
- `enumerateDevices` patching fires extremely frequently (spam-level logging)
- `Could not unmute track` warnings for MediaStreamTrack (has only a getter) - non-fatal
- 3 additional Google Meet bots (8904-8906) were spawned externally during test

### Conclusion
The "bots crashing after admission" issue was **not reproduced** in this test run. The bot remained stable through admission and beyond. Possible explanations:
1. The crash was intermittent and did not occur this time
2. A recent code change fixed the underlying issue
3. The crash requires specific conditions not present in this test (e.g., specific meeting type, number of participants, etc.)

### Next steps to reproduce if issue persists:
- Check bot-manager logs for historical crash patterns
- Look at `docker events` for OOMKilled or other container death reasons
- Test with org-hosted Teams meetings (not personal meetings)
- Test with multiple participants speaking simultaneously
