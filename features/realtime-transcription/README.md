# Realtime Transcription

## Why

This is the #1 product feature. Users need live, speaker-attributed transcripts during meetings -- not after. A bot joins the meeting, captures per-speaker audio, transcribes it in real-time, and delivers segments to clients as they happen. Every other feature (summaries, action items, search) depends on this pipeline producing accurate, timely, speaker-labeled segments.

## What

### Full Pipeline

```
Bot joins meeting
  -> per-speaker audio capture (platform-specific)
  -> speaker identity resolution (voting/locking)
  -> VAD filtering (Silero, silence threshold 0.005)
  -> SpeakerStreamManager buffering (confirmation-based)
  -> TranscriptionClient.transcribe() (HTTP POST WAV multipart to transcription-service)
  -> confirmation (2 consecutive fuzzy matches)
  -> SegmentPublisher: Redis XADD to `transcription_segments` stream + PUBLISH to pub/sub
  -> transcription-collector consumes stream
  -> speaker mapping + Redis Hash (mutable, live segments)
  -> background task: Redis Hash -> Postgres (immutable, after 30s threshold)
  -> WebSocket delivery (live, from Redis pub/sub)
  -> REST delivery (historical, from Postgres + Redis Hash merge)
```

### Platform Architecture Difference

| Platform | Audio Model | Speaker Identity |
|----------|------------|-----------------|
| **Google Meet** | Per-element audio streams. Each participant = separate `<audio>` element with its own MediaStream srcObject. Clean single-voice audio per track. | Class mutations (`Oaajhc` = speaking, `gjg47c` = silence) + MutationObserver + 500ms polling fallback. Voting/locking: correlate speaking indicator with audio track. |
| **MS Teams** | ONE mixed audio stream. Single `<audio>` element with RTCPeerConnection stream containing all participants mixed together. | DOM `voice-level-stream-outline` + `vdi-frame-occlusion` class detection. Audio chunks routed by speaker NAME (not index) based on who DOM says is currently speaking. |

Google Meet gives isolated per-speaker audio -- no diarization needed, overlapping speech handled naturally. Teams gives mixed audio that must be routed by DOM signals -- overlapping speech goes to all active speakers.

### Key Constants

| Constant | Value | Source |
|----------|-------|--------|
| Sample rate | 16000 Hz | `index.ts:1337` `TARGET_SAMPLE_RATE` |
| ScriptProcessor buffer | 4096 samples | `index.ts:1338` `BUFFER_SIZE` |
| Silence threshold | 0.005 (max amplitude) | `index.ts:1387` |
| Speaker lock votes | 3 | `speaker-identity.ts:30` `LOCK_THRESHOLD` |
| Speaker lock ratio | 70% | `speaker-identity.ts:32` `LOCK_RATIO` |
| Min audio before submit | 2s | `index.ts:1020` `minAudioDuration` |
| Submit interval | 2s | `index.ts:1021` `submitInterval` |
| Confirm threshold | 2 consecutive matches | `index.ts:1022` `confirmThreshold` |
| Max buffer (wall-clock hard cap) | 10s | `index.ts:1023` `maxBufferDuration` |
| Immutability threshold | 30s | `transcription-collector/config.py:20` `IMMUTABILITY_THRESHOLD` |
| Background task interval | 10s | `transcription-collector/config.py:19` `BACKGROUND_TASK_INTERVAL` |
| Speaker detection polling | 500ms | `googlemeet/recording.ts:584` `setInterval` |
| State machine debounce | 200ms | `msteams/recording.ts:425` `MIN_STATE_CHANGE_MS` |

### Data Flow Diagram

```
 BROWSER (Playwright page.evaluate)                NODE.JS (vexa-bot process)
 ================================                  ===========================

 Google Meet:                                      handlePerSpeakerAudioData(index, data)
   <audio> per participant                            |
     -> AudioContext(16kHz)                           +-> resolveSpeakerName(page, index, 'googlemeet')
     -> ScriptProcessor(4096)                         |     query __vexaGetAllParticipantNames()
     -> silence check (>0.005)                        |     speaking.length === 1 -> recordTrackVote()
     -> __vexaPerSpeakerAudioData(i, data) --------->|     LOCK_THRESHOLD=3, LOCK_RATIO=0.7
                                                      |
 Teams:                                            handleTeamsAudioData(name, data)
   <audio> single mixed stream                        |
     -> AudioContext(16kHz)                           +-> speakerId = `teams-${name}`
     -> ScriptProcessor(4096)                         |   (name known from DOM, no voting needed)
     -> silence check (>0.005)                        |
     -> DOM speakingStates lookup                     v
     -> __vexaTeamsAudioData(name, data) ----------> SpeakerStreamManager
                                                      |
                                                      +-> feedAudio(speakerId, Float32Array)
                                                      +-> trySubmit() every 2s
                                                      |     audioDuration >= 2s? -> submitBuffer()
                                                      |     wallClock >= 10s? -> force flush
                                                      |
                                                      +-> onSegmentReady -> TranscriptionClient
                                                      |     .transcribe(audioBuffer, language)
                                                      |     HTTP POST multipart/form-data WAV
                                                      |     -> transcription-service (Whisper)
                                                      |     <- { text, language, language_probability }
                                                      |
                                                      +-> handleTranscriptionResult()
                                                      |     fuzzy match first 80% of shorter string
                                                      |     confirmCount >= 2? -> emit
                                                      |
                                                      +-> onSegmentConfirmed
                                                            |
                                                            v
                                                      SegmentPublisher
                                                        XADD transcription_segments { payload: JSON }
                                                        PUBLISH meeting:{id}:transcription (flat JSON)
                                                            |
                                                            v
                                                  transcription-collector
                                                    XREADGROUP on transcription_segments
                                                    -> speaker mapping
                                                    -> HSET meeting:{id}:segments (Redis Hash, mutable)
                                                    -> PUBLISH for WebSocket subscribers
                                                            |
                                                     +------+------+
                                                     |             |
                                                     v             v
                                              Background task   api-gateway
                                              (every 10s)        WebSocket
                                              check updated_at    -> client (live)
                                              > 30s? immutable
                                              INSERT Postgres
                                                     |
                                                     v
                                              api-gateway REST
                                              GET /transcripts/{meeting_id}
                                              merges Redis Hash + Postgres
                                                -> client (historical)
```

### Components

| Component | Role | Key file |
|-----------|------|----------|
| **vexa-bot** | Joins meeting, captures per-speaker audio, runs speaker identity, buffers, transcribes | `services/vexa-bot/core/src/index.ts` |
| **speaker-identity** | Track-to-speaker voting/locking (Google Meet) and DOM traversal (Teams) | `services/vexa-bot/core/src/services/speaker-identity.ts` |
| **speaker-streams** | Per-speaker buffering with confirmation-based segment emission | `services/vexa-bot/core/src/services/speaker-streams.ts` |
| **segment-publisher** | Redis XADD + PUBLISH for segments and speaker events | `services/vexa-bot/core/src/services/segment-publisher.ts` |
| **transcription-client** | HTTP POST WAV multipart to transcription-service | `services/vexa-bot/core/src/services/transcription-client.ts` |
| **transcription-service** | Whisper inference on audio chunks | `services/transcription-service/main.py` |
| **transcription-collector** | Consumes Redis stream, maps speakers, writes Redis Hash + Postgres | `services/transcription-collector/main.py` |
| **api-gateway** | WebSocket (live via Redis pub/sub) + REST (historical from Postgres + Redis Hash) | `services/api-gateway/` |

### Key Behaviors

- **Per-speaker isolation (Google Meet):** Each participant has a separate `<audio>` element. The bot creates one AudioContext + ScriptProcessor per element. Audio is pre-separated -- no diarization needed.
- **Mixed stream routing (Teams):** One audio element, one ScriptProcessor. Browser-side DOM detection determines who is speaking. Audio chunks are routed to the active speaker's buffer by name.
- **Speaker identity locking:** Votes accumulate when exactly one speaker indicator is active while audio arrives on a track. After 3 votes with 70% ratio, the mapping locks permanently. One-name-per-track, one-track-per-name enforced.
- **Confirmation-based emission:** Segments are NOT published on first transcription. The buffer resubmits every 2s. When the first 80% of the transcript matches across 2 consecutive submissions, the segment is confirmed and published. This prevents hallucination segments.
- **Hard cap:** If wall-clock time exceeds 10s regardless of audio duration, the buffer force-flushes. Prevents mega-segments from accumulating during intermittent speech.
- **GC prevention:** `window.__vexaAudioStreams` holds persistent references to AudioContext/ScriptProcessor/source nodes to prevent garbage collection (classic Web Audio API GC bug).
- **Mutable then immutable:** Segments live in Redis Hash (mutable) for 30s. During this window, speaker names and text can be updated. After 30s, the background task writes them to Postgres (immutable) and removes from Redis.
- **Dual delivery:** Live clients receive segments via WebSocket (Redis pub/sub). Historical clients fetch via REST (merged Redis Hash + Postgres).
- **Language detection:** Auto-detected per speaker on first chunk. Results with probability < 0.3 are discarded. Explicit language setting overrides auto-detection.

## How

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Create a bot for a 3-speaker mock meeting (Google Meet mock at `mock.dev.vexa.ai/google-meet.html`)
3. Connect to WS: `wscat -c ws://localhost:8056/ws -H "X-API-Key: <token>"`
4. Verify live segments arrive with speaker names (Alice, Bob, Carol)
5. After meeting ends, verify `GET /transcripts/{meeting_id}` returns all segments with correct speaker attribution
6. Compare WS delivery to REST -- same segments, same speakers

### Platform-Specific Docs

- [Google Meet flow](google-meet/README.md) -- per-element audio, class-based speaker detection
- [MS Teams flow](ms-teams/README.md) -- mixed stream, DOM-based speaker routing

### Documentation Pages

- [Per-Speaker Audio Architecture](../../docs/per-speaker-audio.mdx)
- [Speaker Events](../../docs/speaker-events.mdx)
- [WebSocket API](../../docs/websocket.mdx)
- [Concepts](../../docs/concepts.mdx)

### State Detection Reliability

Confidence is capped by state detection accuracy. If the bot doesn't know its state, no pipeline fix matters.

| State | Current reliability | Why | Caps confidence at |
|-------|-------------------|-----|------------------|
| In lobby | ~80% | Waiting room text selectors mostly work | 80 |
| Admitted | **~50%** | False positives — UI indicators (Leave button, toolbar) visible in lobby too | **50** |
| Hearing remote audio | ~95% | maxVal > 0.005 is reliable WHEN actually admitted | 95 |
| Speaker identified | ~90% (mock) | Voting/locking works on mock, untested on real | 90 |
| Alone in meeting | ~70% | Participant counting excludes bot but may miss host | 70 |

**Admission is the bottleneck.** Everything downstream depends on being actually admitted. False positive admission silently produces zero results — bot captures silence from local self-view, not remote audio.

**Reliable admission signal:** Remote audio arriving (maxVal > 0.005). If audio elements exist but all silent for >10s → bot is NOT admitted.

**Verify from both sides:** Bot detects admission AND host confirms bot is in "In the meeting" section of People panel.

### Known Limitations

- **Admission false positives (CRITICAL):** Bot reports "admitted" while still in lobby. UI indicators aren't specific enough. See google-meet/CLAUDE.md for details.
- First few seconds of a new speaker may show as empty until speaker identity locks (3 votes needed)
- Teams: first ~1.3s of each speaker turn misattributed due to 200ms debounce + 1s DOM signal lag. Ring buffer (BUFFER_PROPOSAL.md) mitigates this.
- Teams mixed audio means overlapping speech is duplicated to all active speakers' buffers
- Language detection with probability < 0.3 discards the segment entirely (false negatives possible for rare languages)
- Whisper inference adds 1-3s latency per submission on top of the 2s submit interval
- Google Meet obfuscated class names (`Oaajhc`, `gjg47c`) may change with Meet UI updates -- selectors.ts must be updated
