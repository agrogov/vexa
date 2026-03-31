# Browser Control

## Why

We can't reach 95% confidence because test meetings have no audio. The VNC browser has no microphone. Every real meeting test produces 0 transcription segments.

The fix: bring the playwright-vnc-poc browser infrastructure into Vexa. One browser hosts the meeting with auth + mic (plays speech via PulseAudio). Another browser is the Vexa bot that transcribes. Both controlled via CDP. Fully automated, no human needed.

This same infrastructure unlocks authenticated bots for users — they authenticate once, the bot reuses their cookies for every meeting. No lobby, no rejection, org-restricted meetings work.

## What

Three capabilities from one piece of infrastructure:

### 1. Create meetings (testing)
Take control of a browser with auth cookies. Navigate to meet.new or Teams Meet sidebar. Create a meeting. Play WAV audio through PulseAudio so there's actual speech for the other bot to transcribe.

### 2. Admit bots (testing + production)
When the attendance bot appears in the lobby, the host browser clicks admit via CDP. Automated — no human in the loop.

### 3. Authenticated bot join (production)
User authenticates their Google/Teams account via VNC URL. Cookies persist in DB. Bot reuses cookies for every meeting — joins as the user, skips lobby, accesses org-restricted meetings.

### Architecture

```
┌─────────────────────────────────────────────────┐
│ Host browser (creates meeting, plays audio)       │
│ ┌──────────┐ ┌───────────┐ ┌──────────────────┐ │
│ │ Chromium  │ │PulseAudio │ │ CDP controller   │ │
│ │ + cookies │ │ (WAV→mic) │ │ (create/admit)   │ │
│ └──────────┘ └───────────┘ └──────────────────┘ │
│      VNC (auth only)    CDP (automated control)   │
└───────────────────────────┬───────────────────────┘
                            │ meeting URL
                            ↓
┌───────────────────────────────────────────────────┐
│ Vexa bot (joins meeting, transcribes)              │
│ ┌──────────┐ ┌───────────┐ ┌──────────────────┐  │
│ │ Chromium  │ │ Audio     │ │ Per-speaker      │  │
│ │ (guest)   │ │ capture   │ │ transcription    │  │
│ └──────────┘ └───────────┘ └──────────────────┘  │
└───────────────────────────────────────────────────┘
```

### What exists (from playwright-vnc-poc)

| Component | Status | Location |
|-----------|--------|----------|
| Chromium in Docker + VNC + CDP | Working | playwright-vnc-poc/Dockerfile |
| PulseAudio (virtual mic/speaker) | Working | playwright-vnc-poc/start.sh |
| Cookie persistence (Docker volumes) | Working | docker-compose.yml volumes |
| Google Meet creation (meet.new) | Working | create-meeting.js |
| Teams meeting creation (Meet sidebar) | Working | tested 2026-03-17 via CDP |
| Lobby admission via CDP | Working | tested 2026-03-17 |
| Audio injection (WAV → PulseAudio → mic) | Exists in vexa-bot voice agent mode | services/vexa-bot TTS flow |
| Cookie export to JSON | Working | share-cookies.js |

### What needs building

| Task | Size | Description |
|------|------|-------------|
| Integrate browser Dockerfile into vexa | Small | Copy/adapt playwright-vnc-poc Dockerfile |
| WAV playback through PulseAudio | Small | `paplay` or `ffplay` to inject speech audio as mic input |
| CDP meeting creation library | Medium | Reusable functions: createGoogleMeet(), createTeamsMeeting(), admitFromLobby() |
| Bot-manager: host mode | Medium | Launch a "host" browser that creates + hosts a meeting, separate from the transcription bot |
| Cookie-to-DB pipeline | Medium | Export cookies → encrypt → store in users.data → restore on next container |
| API: auth URL endpoint | Small | POST /auth/browser → returns VNC URL for user to authenticate |
| Browser pool management | Medium | One persistent browser per user, lifecycle: start/stop/health/refresh |
| Auth session monitoring | Small | Detect expired cookies, notify user |

### Documentation
- [Bot Overview](../../docs/bot-overview.mdx)
- [Platforms: Google Meet](../../docs/platforms/google-meet.mdx)
- [Platforms: Microsoft Teams](../../docs/platforms/microsoft-teams.mdx)

## How

### Phase 1: Testing infrastructure (immediate)
Get the host browser into vexa so we can create meetings with audio.

```bash
# Build host browser image
docker build -f features/browser-control/Dockerfile.host -t vexa-host-browser .

# Run with PulseAudio + CDP
docker run -d --name vexa-host \
  -p 6080:6080 \  # VNC (for initial auth)
  -p 9222:9223 \  # CDP
  --shm-size 2g \
  -v host-cookies:/app/userdata \
  vexa-host-browser

# First time: user authenticates via VNC
# After: CDP creates meetings, plays audio, admits bots

# Play WAV as mic input
docker exec vexa-host paplay --device=virtual_mic /path/to/speech.wav
```

### Phase 2: Automated test flow
Two containers, fully automated:

```bash
# 1. Host browser creates meeting
meeting_url=$(node create-meeting.js)  # via CDP

# 2. Host plays speech audio
docker exec vexa-host paplay cache/full-messy/alice.wav &

# 3. Vexa bot joins and transcribes
curl -X POST /bots -d "{meeting_url: $meeting_url}"

# 4. Host admits bot from lobby
node admit-bot.js  # via CDP

# 5. Bot captures audio, transcribes
# 6. Verify: GET /transcripts returns segments with real speech content

# 7. Confidence: 95+ (real meeting, real audio, real transcription)
```

### Phase 3: Authenticated user bots (production)
Same browser, user-facing:
- User calls POST /auth/browser → gets VNC URL
- User authenticates Google/Teams account
- Cookies saved to DB
- Future meetings: bot uses stored cookies, joins as user
