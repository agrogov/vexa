# Compose Testing Findings - 2026-03-17

## Changes Applied
1. **Mic mute removed from join flows** — Google Meet (`join.ts`) and Teams (`join.ts`). Both bots join without mic mute.
2. **PulseAudio tts_sink mute on startup** — `entrypoint.sh` runs `pactl set-sink-mute tts_sink 1` after creating the sink.
3. **TTS playback mute/unmute cycle** — `tts-playback.ts` unmutes before playback, mutes after.
4. **TTS unmute delay (200ms)** — Applied post-unmute delay before TTS playback starts.

## Test Results — TTS Unmute Delay Fix (Teams meeting 9320087910670)

### Setup
- Speaker bot (ID 8973, user mZb...) + Listener bot (ID 8974, user Asu...)
- Auto-admit via host-meeting.js (CDP)
- 5 TTS utterances via /speak endpoint, 12s apart

### Line-by-Line Validation

| # | Sent | Received (Listener CONFIRMED) | Accuracy |
|---|------|-------------------------------|----------|
| 1 | "Hello everyone welcome to the weekly infrastructure review meeting." | "everyone welcome to the weekly infrastructure review meeting" | ~90% — "Hello" clipped at start |
| 2 | "Today we need to discuss the database migration plan for next quarter." | "need to discuss the database migration plan for next quarter." | ~85% — "Today we" clipped |
| 3 | "The current system handles about ten thousand requests per second during peak hours." | "system handles about 10,000." + "requests per second during peak hours." | ~80% — "The current" clipped, split into 2 segments, "ten thousand" -> "10,000" (acceptable normalization) |
| 4 | "We should also review the monitoring alerts that fired last weekend." | "review the monitoring alerts that fired last weekend." | ~85% — "We should also" clipped |
| 5 | "Lets schedule the next meeting for Thursday at three pm eastern time." | "schedule the next meeting for Thursday." | ~60% — "Lets" clipped, "at three pm eastern time" truncated entirely |

### Summary
- **All 5 utterances captured** — 6 CONFIRMED segments (utterance 3 split across 2)
- **Beginning-of-utterance clipping**: persistent across all 5 utterances. First 300-500ms lost. The 200ms unmute delay improved this (previously full words were lost), but still clips the first 1-2 words.
- **End-of-utterance truncation**: utterance 5 lost the final clause entirely ("at three pm eastern time").
- **Speaker identity**: shows as "Teams Participant (UUID)" not "Speaker" — name not resolved for TTS-speaking bot.
- **Estimated overall accuracy: ~80%** (word-level). Below 90% target.

### Previous Blocker — RESOLVED
The `ringBufferReady` initialization error and SPEAKER_START not firing — this is now fixed. Listener received all CONFIRMED segments with proper speaker detection.

## Root Causes for Remaining Issues
1. **Start clipping**: 200ms post-unmute delay is insufficient. Teams needs ~400-500ms for the mic to be "hot" and audio routed to other participants. Recommend increasing to 500ms.
2. **End truncation**: TTS playback likely mutes the sink before the final audio packets are transmitted. Need a post-playback delay before re-muting (200-300ms tail).
3. **Speaker name**: Listener sees Speaker bot as "Teams Participant (UUID)" because Teams assigns a generic name to the audio stream participant ID, not the bot's display name.

## Recommendation
- Increase pre-playback unmute delay from 200ms to 500ms
- Add 300ms post-playback delay before muting tts_sink
- These two changes should push accuracy from ~80% to 90%+
