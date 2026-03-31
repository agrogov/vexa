# Zoom Realtime Transcription (Browser-Based)

## Why

Zoom currently uses a proprietary SDK for bot integration (`services/vexa-bot/core/src/platforms/zoom/`). This requires native binaries, a Zoom Marketplace app, self-hosting, and a completely separate codebase from Google Meet and Teams. The SDK approach cannot be tested with the same mock infrastructure and does not share the browser-based audio capture pipeline.

The browser-based approach aligns Zoom with Google Meet and Teams on the same architecture:
- Same audio capture: Playwright browser + ScriptProcessor per media element
- Same speaker identity: voting/locking via DOM speaking indicators
- Same transcription pipeline: WAV -> transcription-service -> Redis -> Postgres
- Same testing: mock HTML pages with synthetic audio
- Same codebase: one platform strategy pattern, three implementations

No SDK dependency. No native binaries. No Zoom Marketplace app requirement for the bot itself.

## What

### Browser-Based Join

Playwright navigates to `zoom.us/wc/join/{meeting_id}` -- the Zoom web client. This is a fully functional Zoom client that runs in the browser, supporting audio, video, screen sharing, and chat. The bot joins as a browser participant.

### Audio Capture

Same pattern as Google Meet and Teams:

```
Participant A: <audio/video element> -> AudioContext_A -> ScriptProcessor_A
Participant B: <audio/video element> -> AudioContext_B -> ScriptProcessor_B
```

Each ScriptProcessor calls `__vexaPerSpeakerAudioData(index, data)` with isolated per-speaker audio at 16kHz mono.

### Speaker Identity

Same voting/locking pattern:
1. Detect which participant tile shows "speaking" indicator (Zoom-specific selectors TBD)
2. Correlate with which audio track has non-silent data
3. Vote: track N -> speaker name
4. Lock after 3 votes at 70% ratio

### Key Differences from SDK Approach

| Aspect | SDK (legacy) | Browser (new) |
|--------|-------------|---------------|
| Join method | Native SDK binary | Playwright -> zoom.us/wc/join/{id} |
| Audio capture | SDK audio callback | ScriptProcessor per media element |
| Speaker identity | SDK participant events | DOM speaking indicators + voting |
| Dependencies | Zoom SDK binaries, Marketplace app | Chromium only |
| Testing | SDK mocking (complex) | HTML mock page (same as Meet/Teams) |
| Hosting | Self-hosted only | Any deployment |
| Codebase | Separate platform strategies | Shared with Meet/Teams |

### Pipeline

```
zoom.us/wc/join/{id}
  -> Playwright browser joins as guest
  -> ScriptProcessor captures per-speaker audio
  -> handlePerSpeakerAudioData() (Node-side)
  -> SpeakerIdentity voting/locking
  -> TranscriptionClient.transcribe() -> transcription-service
  -> SegmentPublisher -> Redis transcription_segments
  -> transcription-collector -> Postgres
  -> api-gateway -> WebSocket/REST delivery
```

## How

**Not implemented yet -- scaffold only.**

### What needs to be built

1. **Zoom web client selectors** -- DOM analysis of zoom.us/wc/join/ to find:
   - Media elements (audio/video per participant)
   - Participant name elements
   - Speaking indicator classes/elements
   - Join flow selectors (name input, join button, waiting room)
   - Leave button / meeting-ended detection

2. **Zoom platform strategy** -- `platforms/zoom/` browser-based strategies:
   - `join.ts`: navigate to zoom.us/wc/join/{id}, enter name, click join
   - `admission.ts`: detect waiting room, detect admitted state
   - `recording.ts`: speaking detection via Zoom-specific selectors
   - `selectors.ts`: all Zoom web client DOM selectors

3. **Zoom mock page** -- `features/realtime-transcription/mocks/zoom.html`:
   - Simulates Zoom web client DOM structure
   - 3 speakers with synthetic audio (same as Meet mock)
   - Speaking indicators matching real Zoom DOM

4. **Integration** -- wire Zoom browser-based join into bot-manager as an alternative to SDK join

### Open questions

- Does Zoom web client provide separate audio elements per participant, or is it a single mixed stream?
- What are the Zoom web client speaking indicator class names?
- Does Zoom web client require CAPTCHA or additional verification for guest join?
- How does the waiting room work in the web client vs SDK?

## Out of scope

- Zoom Events (webinars, large meetings with panelist/attendee roles)
- Authenticated-only meetings (require Zoom account to join)
- Zoom SDK integration (legacy, handled by `services/vexa-bot/core/src/platforms/zoom/`)
- Breakout rooms
- End-to-end encrypted meetings (no web client support)
