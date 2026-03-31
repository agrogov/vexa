# Google Meet Realtime Transcription

## Why

Google Meet provides the cleanest audio pipeline of any supported platform. Each participant gets a separate `<audio>` element with its own MediaStream -- no diarization needed, no mixed audio, no cross-talk. This is the reference implementation for the per-speaker transcription pipeline.

## What

### Per-Element Audio Streams

Google Meet renders one `<audio>` (or `<video>`) DOM element per participant. Each element's `srcObject` is a `MediaStream` with that participant's audio track. The bot creates one `AudioContext` + `ScriptProcessor` per element, producing isolated per-speaker audio.

```
Participant A: <audio srcObject=MediaStream_A> -> AudioContext_A -> ScriptProcessor_A
Participant B: <audio srcObject=MediaStream_B> -> AudioContext_B -> ScriptProcessor_B
Participant C: <audio srcObject=MediaStream_C> -> AudioContext_C -> ScriptProcessor_C
```

Each ScriptProcessor calls `__vexaPerSpeakerAudioData(index, data)` where `index` is the element's position in the DOM-discovered media element list.

### Audio Capture Setup

**File:** `services/vexa-bot/core/src/index.ts` lines 1335-1406 (`startPerSpeakerAudioCapture`)

1. `page.evaluate()` runs inside the browser context
2. Discovers active media elements: `document.querySelectorAll('audio, video')` filtered by `!el.paused && el.srcObject instanceof MediaStream && srcObject.getAudioTracks().length > 0`
3. Retries up to 10 times with 2s delay (20s total wait)
4. For each element:
   - `new AudioContext({ sampleRate: 16000 })` -- 16kHz mono
   - `ctx.createScriptProcessor(4096, 1, 1)` -- 4096 sample buffer
   - `processor.onaudioprocess`: check max amplitude > 0.005, then call `__vexaPerSpeakerAudioData(i, Array.from(data))`
5. References stored on `window.__vexaAudioStreams` to prevent GC

### Speaker Identity Resolution

**Files:**
- `services/vexa-bot/core/src/services/speaker-identity.ts` -- voting/locking logic
- `services/vexa-bot/core/src/platforms/googlemeet/recording.ts` -- browser-side speaker detection

The bot needs to map audio track index -> participant name. Google Meet doesn't expose this mapping directly. The bot infers it by correlating:

1. **Which track has audio** (ScriptProcessor fires with non-silent data)
2. **Which participant's DOM tile shows "speaking"** (class mutations + indicator elements)

#### Speaking Detection (browser-side, in `recording.ts`)

Two detection methods run in parallel:

**Primary: MutationObserver on class attribute changes**
- Observes all elements within `[data-participant-id]` containers
- Watches for `attributeFilter: ['class']` with `subtree: true`
- On mutation, checks for speaking classes and indicators

**Fallback: 500ms polling interval**
- `setInterval(() => { ... }, 500)` at `recording.ts:584`
- Scans all participant tiles for speaking indicators
- Catches cases where class mutations don't fire (e.g., CSS animations)

#### Speaking Class Names (`selectors.ts`)

```typescript
// Speaking (from googleSpeakingClassNames)
'Oaajhc'  // Primary Google Meet speaking animation class
'HX2H7'   // Alternative speaking class
'wEsLMd'  // Another speaking indicator
'OgVli'   // Additional speaking class

// Silence (from googleSilenceClassNames)
'gjg47c'  // Primary Google Meet silence class
```

These are obfuscated Google Meet class names that change with UI updates. The selectors also include generic fallbacks (`speaking`, `active-speaker`, `silent`, `muted`, etc.).

#### Speaking Indicators (`selectors.ts`)

```typescript
// From googleSpeakingIndicators
'.Oaajhc'  // Speaking animation class
'.HX2H7'   // Alternative speaking class
'.wEsLMd'  // Another speaking indicator
'.OgVli'   // Additional speaking class
```

#### Detection Logic

```
hasSpeakingIndicator(container):
  check googleSpeakingIndicators selectors for visible elements

inferSpeakingFromClasses(container, classList):
  speakingClasses.some(cls => classList.contains(cls)) OR descendant has speaking class
  silenceClasses.some(cls => classList.contains(cls))
  Speaking wins over silence

isCurrentlySpeaking = indicatorSpeaking OR classInference.speaking
```

#### Voting/Locking (Node-side, in `speaker-identity.ts`)

When `handlePerSpeakerAudioData(index, data)` fires:

1. Call `resolveSpeakerName(page, index, 'googlemeet', botName)`
2. `resolveGoogleMeetSpeakerName()` calls `queryBrowserState(page)` which calls `__vexaGetAllParticipantNames()` in the browser
3. Returns `{ names: Record<string, string>, speaking: string[] }`
4. If exactly 1 speaker is active (`speaking.length === 1`):
   - `recordTrackVote(trackIndex, speakerName)`
   - Increments vote count for that track->name pair
5. After `LOCK_THRESHOLD=3` votes with `LOCK_RATIO=0.7` (70% of total votes):
   - Mapping locks permanently: `lockedMappings.set(trackIndex, name)`
   - Never re-evaluated
6. Constraints: one-name-per-track, one-track-per-name. If name is taken by another track, vote is skipped.

#### Name Resolution (`recording.ts`)

Participant names extracted from DOM tiles in priority order:
1. `span.notranslate` -- primary Meet name element
2. Google name selectors from `googleNameSelectors` (`.zWGUib`, `.cS7aqe.N2K3jd`, `.XWGOtd`, etc.)
3. `[data-self-name]` attribute
4. `aria-label` on container
5. `[data-tooltip]` on descendants
6. Fallback: `Google Participant ({data-participant-id})`

Junk names are filtered: `Google Participant (spaces/...)`, `Google Participant (devices/...)`.

### GC Prevention

**Critical:** Web Audio API ScriptProcessor nodes are garbage collected if no JavaScript reference holds them. The bot stores all references on `window.__vexaAudioStreams`:

```typescript
(window as any).__vexaAudioStreams.push({ ctx, source, processor });
```

Without this, audio capture silently stops within seconds.

### Key Selectors (from `selectors.ts`)

| Selector | Purpose | File reference |
|----------|---------|---------------|
| `[data-participant-id]` | Primary participant tile selector | `googleParticipantSelectors` |
| `span.notranslate` | Participant name text | `googleNameSelectors` |
| `.Oaajhc` | Speaking animation class | `googleSpeakingIndicators` |
| `.gjg47c` | Silence class | `googleSilenceClassNames` |
| `button[aria-label="Leave call"]` | Primary leave button (also used for "still in meeting" detection) | `googleLeaveSelectors` |
| `button[aria-label^="People"]` | People panel button (clicked to stabilize DOM) | `googlePeopleButtonSelectors` |
| `[jsname="BOHaEe"]` | Meeting container | `googleMeetingContainerSelectors` |

Full selector lists: `services/vexa-bot/core/src/platforms/googlemeet/selectors.ts`

### Mock Meeting

Test mock at `mock.dev.vexa.ai/google-meet.html` -- 3 speakers (Alice, Bob, Carol) with Edge TTS-generated audio. Used for automated testing without real Google Meet accounts.

### Out of scope
- Domain-restricted meetings (org-only) — bot joins as unauthenticated guest, gets rejected
- Google Classroom meetings — untested, likely same as standard

## How

### File Map

| File | Purpose |
|------|---------|
| `services/vexa-bot/core/src/index.ts:1302-1406` | `startPerSpeakerAudioCapture()` -- browser-side AudioContext/ScriptProcessor setup |
| `services/vexa-bot/core/src/index.ts:1095-1200` | `handlePerSpeakerAudioData()` -- Node-side audio handler, speaker resolution, VAD, buffer feed |
| `services/vexa-bot/core/src/services/speaker-identity.ts` | Track->speaker voting/locking, browser state queries |
| `services/vexa-bot/core/src/services/speaker-streams.ts` | `SpeakerStreamManager` -- per-speaker buffering with confirmation |
| `services/vexa-bot/core/src/services/transcription-client.ts` | HTTP POST WAV to transcription-service |
| `services/vexa-bot/core/src/services/segment-publisher.ts` | Redis XADD + PUBLISH for confirmed segments |
| `services/vexa-bot/core/src/platforms/googlemeet/recording.ts` | Browser-side speaker detection, MutationObserver, participant counting |
| `services/vexa-bot/core/src/platforms/googlemeet/selectors.ts` | All Google Meet DOM selectors (speaking classes, name selectors, indicators) |
