# Retroactive Audio Attribution — Design Proposal

## Problem

Teams mixes all participants' audio into one stream. The bot routes audio chunks to speaker buffers based on DOM speaking indicators (`vdi-frame-occlusion` class). But:

1. **DOM signal is ~1s late** — the speaking class appears about 1 second after the person starts talking (it's reactive, has natural latency)
2. **300ms debounce** — the bot waits 300ms before acting on state changes to prevent flicker
3. **Result:** the first ~1.3s of every speaker turn is either lost or attributed to the previous speaker

This causes "eaten first seconds" in transcripts — the beginning of what someone says is missing or attached to the wrong person.

## Current architecture

```
Mixed audio chunk arrives (every 256ms at 4096 samples / 16kHz)
    ↓
Who is speaking RIGHT NOW? (check DOM state)
    ↓
Route chunk to that speaker's buffer → transcription
```

Problem: "right now" in the DOM is ~1s behind "right now" in the audio.

## Proposed architecture

```
Mixed audio chunk arrives
    ↓
Write to shared ring buffer (keeps last ~3s of audio)
    ↓
Speaker signal arrives from DOM (1s later)
    ↓
Go BACK in the ring buffer, claim audio from [signal_time - lookback] to now
    ↓
Copy claimed audio to speaker's transcription buffer
```

The audio is never lost — it sits in the ring buffer until a speaker signal claims it.

## Parameters to tune

| Parameter | Suggested value | Why |
|-----------|----------------|-----|
| Ring buffer duration | 3 seconds | Covers 1s DOM latency + 300ms debounce + safety margin |
| Lookback on speaker start | 1.5 seconds | DOM signal is ~1s late, grab 0.5s extra for safety |
| Forward hold on speaker end | 500ms | Keep attributing for 500ms after signal disappears (handles breath pauses) |
| Overlap handling | Duplicate | When 2 speakers active, both get the same audio chunk (transcription service handles mixed speech) |

## What changes

**`recording.ts` — the `setupPerSpeakerAudioRouting` function:**

Currently (line ~856):
```typescript
processor.onaudioprocess = (e) => {
  const data = e.inputBuffer.getChannelData(0);
  for (const name of activeSpeakerNames) {
    __vexaTeamsAudioData(name, Array.from(data));  // route immediately
  }
};
```

Proposed:
```typescript
// Shared ring buffer (circular, ~3s at 16kHz)
const RING_BUFFER_SAMPLES = 16000 * 3;  // 48000 samples
const ringBuffer = new Float32Array(RING_BUFFER_SAMPLES);
let writePos = 0;

processor.onaudioprocess = (e) => {
  const data = e.inputBuffer.getChannelData(0);
  // Write to ring buffer (wrap around)
  for (let i = 0; i < data.length; i++) {
    ringBuffer[(writePos + i) % RING_BUFFER_SAMPLES] = data[i];
  }
  writePos = (writePos + data.length) % RING_BUFFER_SAMPLES;

  // Still route to active speakers (for current-moment audio)
  for (const name of activeSpeakerNames) {
    __vexaTeamsAudioData(name, Array.from(data));
  }
};

// When a NEW speaker is detected (state change from silent → speaking):
function onSpeakerStart(name: string, signalTime: number) {
  // Claim audio from [signalTime - lookback] in the ring buffer
  const lookbackSamples = Math.floor(1.5 * 16000);  // 1.5s
  const startPos = (writePos - lookbackSamples + RING_BUFFER_SAMPLES) % RING_BUFFER_SAMPLES;

  // Extract lookback audio and send to speaker
  const lookbackAudio = new Float32Array(lookbackSamples);
  for (let i = 0; i < lookbackSamples; i++) {
    lookbackAudio[i] = ringBuffer[(startPos + i) % RING_BUFFER_SAMPLES];
  }
  __vexaTeamsAudioData(name, Array.from(lookbackAudio));
}
```

## Impact

- **Fixes "eaten first seconds"** — the first 1-1.3s of every speaker turn is recovered from the ring buffer
- **No extra memory** — ring buffer is ~192KB (48000 * 4 bytes), negligible
- **No extra latency** — current audio still routed immediately, lookback is additional
- **Slight duplicate audio** — the lookback chunk overlaps with what was already routed. The SpeakerStreamManager's confirmation logic (fuzzy match) handles this — the overlapping transcription will confirm faster, not produce duplicates.

## Not affected

- Google Meet (per-element streams, no routing needed)
- The rest of the pipeline (SpeakerStreamManager, TranscriptionClient, SegmentPublisher — all unchanged)
- Mock meetings (simulated DOM signals are instant, no latency)

## Testing

Can only be validated on **real Teams meetings** with active speakers. The mock has instant DOM signals so the lookback provides no benefit there. Need to:
1. Implement the ring buffer
2. Test on real Teams meeting with conversation
3. Compare first-second transcription quality before/after
4. Measure: does the lookback audio produce meaningful transcription that was previously missing?

## Priority

Medium — this is a quality improvement, not a pipeline fix. The pipeline works end-to-end. This makes Teams transcription more complete.
