# MS Teams Realtime Transcription

## Why

Teams is the second most important platform. Its audio architecture is fundamentally different from Google Meet: ONE mixed audio stream containing all participants, with speaker identity determined from DOM signals. This makes speaker attribution harder and overlapping speech lossy.

## What

### Single Mixed Audio Stream

Teams provides a single `<audio>` element whose `srcObject` is a MediaStream from an RTCPeerConnection. This stream contains ALL participants' audio mixed together. There are no per-speaker audio elements.

```
All participants -> single RTCPeerConnection -> single <audio> element -> one mixed MediaStream
```

The bot hooks this single stream with one AudioContext + ScriptProcessor, then routes audio chunks to speaker buffers based on who the DOM says is currently speaking.

### Audio Routing Architecture

**File:** `services/vexa-bot/core/src/platforms/msteams/recording.ts` lines 832-893

```
Single <audio> element
  -> AudioContext({ sampleRate: 16000 })
  -> ScriptProcessor(4096, 1, 1)
  -> silence check (maxVal > 0.005)
  -> lookup speakingStates map (populated by MutationObserver)
  -> for each active speaker NAME:
       __vexaTeamsAudioData(name, Array.from(data))
```

Key difference from Google Meet: audio is routed by speaker **NAME** (string), not by element **index** (number). The callback signature is `__vexaTeamsAudioData(name: string, data: number[])`.

**Consequence:** If 2 speakers are active simultaneously, the same audio chunk is sent to BOTH speaker buffers. There is no way to separate overlapping speech from a mixed stream.

### Speaker Detection

**File:** `services/vexa-bot/core/src/platforms/msteams/recording.ts` lines 440-620

Teams speaker detection uses a completely different signal than Google Meet:

#### Primary Signal: `voice-level-stream-outline`

```typescript
// From teamsSpeakingIndicators (selectors.ts:212-214)
'[data-tid="voice-level-stream-outline"]'
```

The `voice-level-stream-outline` element exists inside participant video tiles. The bot checks whether this element (or any of its ancestors) has the `vdi-frame-occlusion` class:

```
vdi-frame-occlusion class PRESENT  -> participant IS speaking
vdi-frame-occlusion class ABSENT   -> participant is NOT speaking
```

**File:** `recording.ts` lines 478-500 (`TeamsSpeakingDetector.detectSpeakingState`)

```typescript
detectSpeakingState(element: HTMLElement): { isSpeaking: boolean; hasSignal: boolean } {
  const voiceOutline = element.querySelector('[data-tid="voice-level-stream-outline"]');
  if (!voiceOutline) return { isSpeaking: false, hasSignal: false };

  // Walk up parent chain checking for vdi-frame-occlusion
  let current = voiceOutline;
  while (current) {
    if (current.classList.contains('vdi-frame-occlusion')) {
      return { isSpeaking: true, hasSignal: true };
    }
    current = current.parentElement;
  }
  return { isSpeaking: false, hasSignal: true };
}
```

#### State Machine

**File:** `recording.ts` lines 423-460 (`SpeakerStateMachine`)

```
MIN_STATE_CHANGE_MS = 200ms (debounce)

States: 'speaking' | 'silent' | 'unknown'
Transitions only occur after 200ms to prevent flickering.
If signal disappears (hasSignal=false), state becomes 'unknown'.
```

#### MutationObserver

The bot observes each participant tile for class attribute changes:

```typescript
observer.observe(voiceOutline, {
  attributes: true,
  attributeFilter: ['class'],
  subtree: true
});
```

On mutation, the `TeamsSpeakingDetector.detectSpeakingState()` is called, the state machine is updated, and `speakingStates` map is refreshed.

#### Participant Discovery

Participant tiles found via `teamsParticipantSelectors`:
- `[data-tid*="participant"]`
- `[data-tid*="video-tile"]` / `[data-tid*="videoTile"]`
- `[data-tid*="roster"]` / `[data-tid*="roster-item"]`

A participant is only observed if it has the `voice-level-stream-outline` signal element. No signal = no observation (no fallback detection).

### Audio Routing by Speaker Name

**File:** `recording.ts` lines 837-890

When the ScriptProcessor fires with non-silent audio:

1. Check `speakingStates` map for all entries where `state === 'speaking'`
2. Get name from `ParticipantRegistry` (cached DOM name extraction)
3. Filter out bot's own name
4. For each active speaker name: `__vexaTeamsAudioData(name, audioArray)`

**Node-side handler** (`index.ts:1268`):

```typescript
async function handleTeamsAudioData(speakerName: string, audioDataArray: number[]): Promise<void> {
  const speakerId = `teams-${speakerName.replace(/\s+/g, '_')}`;
  // Name is already known from DOM -- no voting/locking needed
  if (!speakerManager.hasSpeaker(speakerId)) {
    speakerManager.addSpeaker(speakerId, speakerName);
    segmentPublisher.publishSpeakerEvent({ speaker: speakerName, type: 'joined', timestamp: Date.now() });
  }
  // ... feed audio to buffer
}
```

No voting/locking for Teams -- the speaker name comes directly from DOM detection, so the name is known immediately.

### Name Extraction

**File:** `recording.ts` lines 368-410 (`ParticipantRegistry.extractName`)

Priority order:
1. `[data-tid*="display-name"]`, `[data-tid*="participant-name"]` descendants
2. `.participant-name`, `.display-name`, `.user-name`, `.roster-item-name` descendants
3. `span[title]` descendants
4. `.ms-Persona-primaryText` descendants
5. `aria-label` containing "name" pattern
6. Fallback: `Teams Participant ({data-acc-element-id})`

Forbidden substrings filtered: `more_vert`, `mic_off`, `mic`, `videocam`, `camera`, `share`, `chat`, `participant`, `user`.

### Key Selectors (from `selectors.ts`)

| Selector | Purpose | Constant |
|----------|---------|----------|
| `[data-tid="voice-level-stream-outline"]` | Primary speaking signal | `teamsSpeakingIndicators`, `teamsVoiceLevelSelectors` |
| `.vdi-frame-occlusion` | Speaking = present, silent = absent | `teamsOcclusionSelectors` |
| `button[id="hangup-button"]` | Primary leave/hangup button | `teamsPrimaryHangupButtonSelector` |
| `button[data-tid="hangup-main-btn"]` | Alternative hangup button | `teamsPrimaryLeaveButtonSelectors` |
| `div[class*="___2u340f0"]` | Name div class pattern | `teamsNameSelectors` |
| `[data-tid*="video-tile"]` | Participant video tile | `teamsParticipantSelectors` |
| `[role="menuitem"]` with `img` descendant | Roster participant (for counting) | inline in `collectAriaParticipants()` |

Full selector lists: `services/vexa-bot/core/src/platforms/msteams/selectors.ts`

### Critical Differences from Google Meet

| Aspect | Google Meet | MS Teams |
|--------|-----------|----------|
| Audio streams | Per-element (N streams for N participants) | Single mixed stream |
| Audio callback | `__vexaPerSpeakerAudioData(index, data)` | `__vexaTeamsAudioData(name, data)` |
| Speaker identity | Voting/locking (3 votes, 70% ratio) | Direct from DOM (name known immediately) |
| Overlapping speech | Handled naturally (separate streams) | Audio duplicated to all active speakers |
| Speaking detection | Class mutations (`Oaajhc`/`gjg47c`) + indicators | `voice-level-stream-outline` + `vdi-frame-occlusion` |
| Browser | Chromium | MS Edge (required, fallback to Chromium) |
| Media warm-up | Not needed | Required before pre-join |

### No Mock Meeting Yet

There is no Teams mock meeting equivalent to `mock.dev.vexa.ai/google-meet.html`. Testing requires a real Teams meeting or building a Teams mock that simulates:
- Single mixed audio element with `srcObject` MediaStream
- `[data-tid="voice-level-stream-outline"]` elements in participant tiles
- `vdi-frame-occlusion` class toggling for speaking state

### Out of scope
- Org-only meetings (authenticated users only) — bot joins as anonymous guest, gets rejected
- Teams Live Events / Webinars — different URL format, untested

## How

### File Map

| File | Purpose |
|------|---------|
| `services/vexa-bot/core/src/platforms/msteams/recording.ts` | Browser-side: speaker detection, audio routing, participant counting |
| `services/vexa-bot/core/src/platforms/msteams/selectors.ts` | All Teams DOM selectors |
| `services/vexa-bot/core/src/index.ts:1268-1295` | `handleTeamsAudioData()` -- Node-side handler |
| `services/vexa-bot/core/src/index.ts:1309-1322` | Teams audio callback exposure |
| `services/vexa-bot/core/src/services/speaker-identity.ts:191-302` | `resolveTeamsSpeakerName()` -- DOM traversal + voting/locking (used for fallback) |
