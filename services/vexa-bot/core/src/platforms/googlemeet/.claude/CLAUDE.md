# Google Meet Platform Agent

> Shared protocol: [agents.md](../../../../../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
Google Meet bot integration. Playwright-based join flow, admission waiting, per-speaker audio capture, speaker identity via DOM correlation. **Owns the mock meeting page end-to-end.**

## What you know
- join.ts: goto → name input → "Ask to join" → waiting room → admitted. 5s settle wait after navigation.
- admission.ts: polls for admission, handles org-restricted blocks (unauthenticated guest).
- selectors.ts: DOM selectors for name input, join button, mic/camera toggles. Brittle — Google changes these.
- Per-speaker WebRTC tracks: each participant = separate audio stream via `<audio>`/`<video>` media elements.
- Speaker identity: voting/locking system (speaker-identity.ts) — DOM speaking indicators correlated with audio tracks, LOCK_THRESHOLD=3, LOCK_RATIO=0.7.
- ~7.8% join failure rate ("No active media elements found").

## Mock meeting page

You own the mock at `/home/dima/dev/vexa/features/realtime-transcription/mocks/`. It's served at `https://mock.dev.vexa.ai/google-meet.html` via nginx.

### Current state
- `meeting.html` has Google Meet DOM (selectors, admission flow, participant tiles, toolbar)
- Bot successfully joins, finds media elements, identifies speakers, captures audio
- Audio pipeline works end-to-end (GC bug fixed — see index.ts window.__vexaAudioStreams)
- **Problem**: oscillator sine waves don't produce recognizable speech → transcription returns empty text

### Audio generation tooling
- `generate_audio.py` — uses edge-tts + ffmpeg to synthesize real speech into WAV files
- `scenarios.py` — defines scenarios (full-messy, chaos-meeting, overlap, etc.) with 3 speakers (Alice/en, Bob/en, Carol/ru), timed utterances, overlaps, noise
- `cache/` — generated WAV files land here per scenario
- Dependencies: `pip install edge-tts numpy scipy`, `ffmpeg` must be available

### What needs to happen
1. Generate WAV files: `python generate_audio.py --scenario full-messy`
2. Update `meeting.html` to load WAV files into `<audio>` elements instead of oscillators
3. The `<audio>` elements must have `srcObject` as a `MediaStream` (not just `src=file.wav`) — the bot's ScriptProcessor checks for `el.srcObject instanceof MediaStream`
4. Approach: load WAV via fetch → decode to AudioBuffer → play through AudioContext → MediaStreamDestination → set as srcObject on `<audio>` element
5. Speaking simulation should match the scenario timing (utterance start_s offsets)
6. Verify: bot joins, transcription service returns non-empty text, segments appear in Redis/DB

### Gate (local)

**Bot joins mock → audio with recognizable speech reaches the transcription service endpoint.**

This is YOUR gate. You own everything up to and including the HTTP POST to the transcription service. What happens after (transcription result, Redis, DB) is downstream — not your problem.

Verify with bot logs:
```bash
# Launch bot
curl -s -X POST http://localhost:8056/bots \
  -H "X-API-Key: <token>" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"gate-test","meeting_url":"https://mock.dev.vexa.ai/meeting.html"}'

# Check that transcription requests are being made with speech audio
docker logs $(docker ps --filter name=bot -q | head -1) 2>&1 | grep "TranscriptionClient"
```

Pass = `[TranscriptionClient]` logs show HTTP 200 responses with non-empty text (not `"text":""`). Fail = empty text, no requests, or bot can't join.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../../../../../.claude/agents.md#docs-gate)) using those links as your page list.

**You are responsible for iterating until this works.** Generate audio, update the mock, test, fix, repeat.

### How to build/fix the mock
The mock must match real Google Meet DOM. Don't guess — research the real thing:
1. Ask the human for a real Google Meet URL
2. Join it with the bot's Playwright browser (or manually)
3. Inspect the actual DOM: selectors, class names, aria-labels, media element structure
4. Update the mock to match what you found
5. Test the bot against the updated mock

If selectors break, it's because Google changed their DOM. The fix is always: inspect real Meet → update mock → update selectors.ts if needed.

## Critical questions
- Does the bot get past admission? **Verify from host side, not bot side.** Bot has false-positive admission detection — reports "admitted" while still in lobby.
- Are per-speaker tracks discovered? (check media element count vs participant count)
- Do selectors still match current Google Meet DOM?
- Does speaker identity lock correctly with 3+ participants?

## Known bug: false positive admission (2026-03-17)
Bot uses UI indicators (Leave button, toolbar) to detect admission. But some are visible in lobby too. Bot reported "admitted" while host screenshot showed "Admit all?" dialog still open. The 3 audio elements found were local self-view, not remote audio — that's why 0 transcription segments.

**Reliable admission signal:** Remote audio arriving (maxVal > 0.005 in ScriptProcessor). If elements exist but all silent → bot is NOT admitted.

**Host-side verification:** After admitting, check People panel — bot should move from "Waiting to join" to "In the meeting."

## After every run
Update findings inline. Note selector breakages and join failure patterns.

