# Hot Debug Skill

## Why

Bots are live browsers in real meetings. When something breaks, we need to debug FAST — not read logs after the container dies. Hot debug connects to the live bot and inspects what's happening in real time.

Meeting hosting (creating the meeting, joining as organizer, admitting bots from lobby) is handled by the **meeting-host** skill at `/home/dima/dev/vexa/skills/meeting-host`. Hot debug spawns it as a subprocess so you can hot-fix meeting-host bugs independently — edit `meeting-host/run.js`, re-run hot-debug, and the fix is live immediately.

## What

A debug loop that:
1. Spawns `meeting-host/run.js` to create a meeting + auto-admit (runs in background)
2. Launches speaker + listener bots via API
3. Waits for bots to be admitted and reach "active" status
4. Makes speaker bot talk via /speak
5. Checks listener bot transcription
6. Checks speaker indicator state via DOM inspection + screenshots
7. Reports PASS/FAIL with evidence
8. If FAIL — inspects DOM, audio state, WebRTC stats

Meeting-host handles the hard CDP work (meeting creation, organizer join, lobby admission). Hot debug focuses on bot behavior testing.

## How

### Quick test
```bash
# Full loop — spawns meeting-host, launches bots, speaks, observes
node run.js --platform teams

# Reuse existing meeting (meeting-host already running separately)
node run.js --platform teams --meeting-url <URL>

# Run N times (confidence ladder evidence)
node run.js --platform teams --runs 20

# Run forever
node run.js --platform teams --loop
```

### The loop
```
spawn_meeting_host()                    ← node /home/dima/dev/vexa/skills/meeting-host/run.js
  → parse MEETING URL from stdout
  → meeting-host keeps running (auto-admit forever)
stop_lingering_bots() →
launch_speaker() + launch_listener() →  ← 500ms gap (avoid 409)
wait_for_active() →                     ← poll 1s until bot status=active
screenshot(idle) →                      ← indicator should be OFF
speak(1 utterance) →
screenshot(speaking) →                  ← indicator should be ON
poll_silence() →                        ← indicator should be OFF again
stop_bots() →
kill_meeting_host() →
report(pass/fail, timing)
```

When `--meeting-url` is provided, meeting-host is NOT spawned — bots go directly to that meeting. The organizer must already be in and admitting.

### Fixing meeting-host bugs

Since meeting-host is spawned from source (`node /home/dima/dev/vexa/skills/meeting-host/run.js`), you can:
1. Run hot-debug, see it fail at the meeting creation step
2. Edit `meeting-host/run.js` directly
3. Re-run hot-debug — picks up the fix immediately, no rebuild needed

### Scripts
- `run.js` — the main debug loop (spawns meeting-host, launches bots, speaks, observes)
- `iterate.js` — minimal iteration loop (create → launch → admit → verify active)

### API tokens for testing
- Main (speaker): vxa_user_mZbCdNnQwmzU2rjyGcyCjj0is8Mx75ljtHgHsM2L
- Alice (listener): vxa_user_AsujJTFgXEmHEn0K7LyqX7oyReeWGJcf7a1CPgLI
- Bob: vxa_user_hj9O73sADXTpOPQHGX2iKDTySLmb9LNO9kUIYyNo
- Carol: vxa_user_xxixlEp0b93WLwdhNVvN6LadmxhblHP56Z2tFTtv

### What we learned
- Bot can't hear itself — need speaker + listener (two users, 409 constraint)
- PulseAudio tts_sink + virtual_mic both muted by default, unmuted during /speak
- Bot reaches lobby ~20-25s after launch
- Speaker name in transcript shows as UUID for guest bots
- 1500ms MIN_STATE_CHANGE_MS debounce in recording.ts filters ambient mic noise flicker
- API platform values: 'teams' and 'google_meet' (NOT 'ms_teams')

## Confidence Ladder

Two axes: **fast admission** (meeting created → both bots in meeting) and **observability** (screenshot + speaker state interpreted correctly).

| Level | Score | Gate | Threshold |
|-------|-------|------|-----------|
| 1 | 50 | `gate_lobby` | Bot reaches lobby (AWAITING_ADMISSION) within 30s |
| 2 | 70 | `gate_admit` | Both bots admitted within 40s of launch |
| 3 | 75 | `gate_speaker` | Screenshot + DOM correctly shows speaker ON during /speak and OFF at idle |
| 4 | 85 | `gate_loop` | Full loop completes (admit + speak), any timing |
| 5 | 95 | `gate_speed` | Loop completes under 60s, 3 consecutive passes |
| 6 | 99 | `gate_99` | Loop completes under 15s, 20 consecutive passes |

**Current: 85** — gates `gate_lobby` through `gate_loop` passed. 10+ consecutive runs pass with ~37s total. Refactoring to use meeting-host subprocess — need to re-validate after refactor.

## Speed targets

| Step | Target | How |
|------|--------|-----|
| Meeting-host spawn | <2s | Just `node run.js`, meeting-host handles CDP |
| Meeting creation | <10s | meeting-host creates via CDP |
| Bot reaches lobby | ~25s | Can't speed up (browser navigation) |
| Admission | <1s | meeting-host MutationObserver |
| Speak + transcribe | <15s | TTS 3s + transmission + Whisper 5s + confirmation |
| **Total iteration** | **<60s** | Code change to verified result |

**Never sleep to wait for something.** Use `waitForSelector`, `waitForFunction`, or poll with deadline.
