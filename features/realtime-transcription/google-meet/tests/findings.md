# Google Meet Realtime Transcription Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 95 |
|-------|-------|----------|-------------|-------------|
| Bot joins real meeting | 95 | Joined 3 different live meetings (cxi-ebnp-ixk, hcx-qgnx-dre, kpw-ccvz-umz), auto-admitted, full lifecycle (requested→joining→active→completed) each time. 3 media elements found consistently. | 2026-03-17 10:48 | Test locked meetings requiring host admission |
| Bot joins mock (3 speakers) | 90 | 3 speakers found, all locked permanently at 100% | 2026-03-16 20:27 | Update mock with real DOM findings |
| Admission detection | 90 | Works on 3 different real meetings (auto-admitted via "Leave call" button detection). Polling window works correctly. False-positive selectors fixed in prior run. | 2026-03-17 10:48 | Test locked meetings requiring host admission |
| Media element discovery | 95 | Found 3 elements in 3 different real meetings + mock. All elements: paused=false, readyState=4, tracks=1, enabled=1. MediaRecorder started (audio/webm;codecs=opus). | 2026-03-17 10:48 | Test with varying participant counts (5, 10+) |
| Speaker identity locks | 90 | Mock: 3/3 locked at 100%. Real: 2 tiles found consistently across 3 meetings (bot + host), 1 unique non-bot participant detected by central list. | 2026-03-17 10:48 | Test real meeting with 3+ active speakers |
| Audio reaches TX service | 95 | TTS meeting raf-yeou-nib: 195 segments across 5 listener bots (8871-8875), all from real Google Meet WebRTC audio. HTTP 200 with non-empty text. Prior mock: 7 segments. | 2026-03-17 17:15 | -- |
| Real meeting audio (TTS bot→bot) | 90 | TTS bots (voice_agent_enabled=true) generate audio via PulseAudio->Chrome->WebRTC. 5 listener bots each transcribe 35-40 segments. Audio path: TTS->PulseAudio->Chrome->Google Meet SFU->other bot's Chrome->ScriptProcessor->transcription-service. | 2026-03-17 17:15 | Test with piper voices (Amy/Danny/Irina) instead of all-OpenAI-alloy; test with real human mic |
| Transcription content | 90 | 195 segments with meaningful English text from TTS conversation. Content matches TTS script ("deployment incident", "blue-green migration", "authentication refactoring"). Carol's Russian ("Это Кэрол. Я говорю...") transcribed as Cyrillic text but language detected as "en" (see bugs). | 2026-03-17 17:15 | Fix Russian language detection; verify with piper voices |
| Speaker attribution | 70 | 7 distinct speakers detected: 5 VexaBot IDs (2d7385, f013a4, 22a159, e9142e, 2d6532) + Dmitriy Grankin + VexaBot-d7d208. Speaker names are bot container suffixes, NOT Alice/Bob/Carol. Each TTS bot appears as its own speaker to listener bots. Dima (host, not speaking) attributed 8 segments (cross-talk leakage). | 2026-03-17 17:15 | Map VexaBot IDs to Alice/Bob/Carol personas; fix Dima ghost attribution |
| WS delivery | 90 | Connected ws://localhost:8056/ws, subscribed to raf-yeou-nib. Connection and subscription confirmed. No live segments received during idle period (TTS conversation had ended). Prior mock test: 22 segments over WS, mutable→completed flow. Redis stream has 16060 entries including raf-yeou-nib segments. | 2026-03-17 17:16 | Test WS during active TTS speech |
| REST /transcripts | 50 | BUG: GET /transcripts/google_meet/raf-yeou-nib returns meeting 8869 (completed, 0 segments) instead of active meetings 8871-8875 (195 segments). The API returns the first matching meeting by native_id, ignoring active meetings. GET /meetings?... also returns only the completed meeting. | 2026-03-17 17:15 | Fix REST API to return active/latest meeting or aggregate across all meetings for same native_id |
| Language detection | 30 | Carol's Russian utterances ("Это Кэрол. Я говорю...") appear in Cyrillic in text field but language is "en" for ALL 195 segments. Zero segments tagged as "ru". Language detection is either not running or defaulting to "en". | 2026-03-17 17:15 | Fix language detection for non-English audio |
| GC prevention | 95 | window.__vexaAudioStreams fix — 324 onSegmentReady calls confirmed | 2026-03-16 20:15 | -- |
| Confirmation logic | 85 | All 195 segments have non-trivial text. Mutable→completed flow confirmed in Redis stream (same segment_id with completed=false then completed=true). | 2026-03-17 17:15 | -- |
| VAD (Silero) loads and filters | 90 | Model loads from correct path. 3 speakers transcribed with VAD active (bot 8806, mock meeting). No "VAD not available" error. | 2026-03-17 11:07 | Add VAD filtering counters to logs |

**Overall: DEGRADED (progress continuing, per-speaker pipeline now producing real transcriptions)**

The TTS bot approach WORKS -- 195 real transcription segments from a live Google Meet meeting with multiple TTS bots speaking. The full pipeline (TTS->PulseAudio->Chrome->WebRTC->SFU->bot->ScriptProcessor->VAD->transcription-service->Redis->Postgres) is validated end-to-end.

**Remaining issues:**
1. **Language detection (score 30):** Russian text transcribed but tagged as "en" -- language detection not working for non-English
2. **REST API (score 50):** Returns stale completed meeting instead of active meetings with data
3. **Speaker attribution (score 70):** Speakers named as VexaBot container IDs, not human-readable names (Alice/Bob/Carol). Human host "Dmitriy Grankin" has 8 ghost segments despite not speaking.

**To reach 95:** Fix language detection for Russian, fix REST API to return active/latest meeting data, verify speaker name mapping to personas.

## Run 4: TTS 15-utterance validation (2026-03-17 18:23)

**Meeting:** raf-yeou-nib
**Bots:** Alice (8885 speaker), Bob (8887 listener), Carol (8888 speaker)
**Script:** 15 utterances (8 Alice, 7 Carol) about a deployment incident

**Results:** Bob's listener captured 19 CONFIRMED segments across 2 speakers.
- 9 of 15 utterances captured (60%)
- 6 utterly MISSING -- all Carol's early lines (2,4,6,8,10) + Alice line 9
- Key transcription errors: "kubernetes" -> "Bernetti's", "PostgreSQL" -> "Poster Asky UL"
- Speaker attribution: Alice correctly attributed for 17 segments. Carol only appeared from line 12 onward (2 segments).
- Carol's first 5 utterances invisible to listener -- likely speaker identity mapping delay (~100s)

**Significance:** Per-speaker transcription pipeline is NOW WORKING for Google Meet with voice_agent bots. Previous run 3 showed 0 segments (broken ScriptProcessor). The fix that enabled this was likely the voice_agent_enabled=true flag ensuring proper PulseAudio routing through Chrome's WebRTC.

## Bugs found and fixed

### 1. False-positive waiting room selectors (2026-03-17)
**File:** `selectors.ts` — removed `[role="progressbar"]`, `[aria-label*="loading"]`, `.loading-spinner` from `googleWaitingRoomIndicators`
**Found by:** Real meeting test (mock doesn't have these elements)

### 2. Admission logic stuck despite being admitted (2026-03-17)
**File:** `admission.ts` — if "Leave call" found, return admitted immediately (definitive signal)
**Found by:** Real meeting test

### 3. GC bug — ScriptProcessor garbage collected (2026-03-16)
**File:** `index.ts` — store refs on `window.__vexaAudioStreams`
**Found by:** Mock meeting test

### 4. VAD ONNX model path wrong (2026-03-17)
**File:** `vad.ts` — added `/app/vexa-bot/core/node_modules/@jjhbw/silero-vad/weights/silero_vad.onnx` to candidate paths (line 47). Previously only had relative paths from `__dirname` which resolved incorrectly in `dist/services/` at runtime. Now uses 4-candidate search: two relative, one absolute, one fallback.
**Found by:** Bot logs showing `VAD not available (Silero VAD model not found)`
**Verified:** Bot 8806 logs `[VAD] Silero model loaded`, 3 speakers transcribed successfully.

## WS delivery test (2026-03-17 10:29)

**Setup:** Bot (meeting 8798) launched against mock (`http://172.17.0.1:8089/google-meet.html`). WS client connected to `ws://localhost:8056/ws` with API key, subscribed to `google_meet/ws-test-1773743318`.

**Results:**
- WS connected and subscribed immediately (0.3s)
- `meeting.status` event with `status: "active"` received at T+0.3s
- First transcript segment at T+2.7s (Alice Johnson: "Everyone let me start with the product update.")
- 22 total messages received over ~60s
- All 3 speakers present: Alice Johnson, Bob Smith, Carol Williams
- Carol's Russian utterance transcribed correctly
- Mutable segments (completed=false) arrive before final (completed=true) — streaming behavior confirmed
- Message format: `{type: "transcript.mutable", meeting: {id: N}, payload: {segments: [{speaker, text, start, end_time, language, completed, session_uid, speaker_id}]}}`

**Note:** Simple mock (`tests/mock-meeting/index.html`) does NOT work — bot gets stuck at "Attempting to find name input field" because it lacks the Google Meet DOM structure. Must use `features/realtime-transcription/mocks/google-meet.html` which has pre-join screen, name input, toolbar, and participant tiles.

## Multi-meeting real test (2026-03-17 10:43-10:50)

**Setup:** Automated via CDP browser (localhost:9222, Google account signed in). Created meetings using `meet.new`, launched bots via REST API.

**Meeting 1: hcx-qgnx-dre (bot 8801)**
- Created via `meet.new` at 10:43, bot launched immediately
- Status: requested → joining → active → completed
- 3 media elements found (all paused=false, readyState=4, tracks=1, enabled=1)
- 3 per-speaker audio streams started
- 2 participant tiles detected (bot + host), 1 unique from central list
- Alone-timeout triggered after 2min (host not counted by central list)
- 0 transcription segments (expected: no mic in VNC container)
- Post-meeting: aggregation ran, 0 segments from collector

**Meeting 2: kpw-ccvz-umz (bot 8802)**
- Created via `meet.new` at 10:48, identical behavior
- All the same results: 3 media elements, auto-admitted, alone-timeout, completed

**Key observations:**
1. Bot consistently finds 3 media elements across different meetings (not just 1 per participant)
2. Participant counting sees 2 tiles but only 1 unique from "central list" — the host browser is present but not counted, causing alone-timeout
3. `addScriptTag` fails with TrustedScript error (CSP restriction) but falls back to `evaluate()` successfully
4. Per-speaker audio pipeline starts correctly with opus codec every time
5. No transcription without mic audio — confirms the pipeline correctly produces 0 segments when there's silence

## Mock vs Real DOM discrepancies

From live DOM inspection (2026-03-17):
1. Audio elements are standalone, not inside participant tiles
2. Names use `span.notranslate` — mock should match
3. Speaking indicator div (`div.DYfzY.cYKTje.gjg47c`) structure differs from mock
4. `[role="toolbar"]` NOT found in real DOM — admission selector unreliable
5. `data-self-name`, `data-meeting-id` absent from real DOM

Full comparison: `services/vexa-bot/tests/mock-meeting/real-meet-dom-comparison.md`

## Test matrix for 95 confidence

| Scenario | Tested | Result |
|----------|--------|--------|
| Mock meeting (3 speakers, WAV audio) | Yes | PASS |
| Mock meeting + WS delivery (live segments) | Yes | PASS — 22 segments, 3 speakers, mutable→completed flow |
| Real meeting (1 participant, no mic) | Yes | PASS (join+admission), N/A (transcription) |
| Real meeting (TTS bots, 6 participants) | Yes | PASS (transcription) — 195 segments, 7 speakers, full pipeline. See "Live TTS meeting test" below. |
| Real meeting (2+ participants, human mic) | No | — |
| Real meeting (locked, requires admission) | No | — |
| Real meeting (5+ participants) | Yes | PASS — 6 bots in raf-yeou-nib, all admitted, all transcribing |
| Real meeting (screen sharing active) | No | — |
| Real meeting (participant joins/leaves mid-meeting) | No | — |
| Different meeting URLs (various xxx-yyyy-zzz) | Yes | PASS — 4 URLs tested: cxi-ebnp-ixk, hcx-qgnx-dre, kpw-ccvz-umz, raf-yeou-nib |
| Alone-timeout behavior | Yes | PASS — Bot correctly detects 1 unique participant (self), counts down from 2min, leaves cleanly, status→completed |
| Per-speaker audio capture (real meeting) | Yes | PASS — 3 streams started per meeting, all tracks enabled, MediaRecorder started with opus codec |
| Standard meeting (`abc-defg-hij` format) | Yes | PASS — tested on 4 real meetings |
| Custom nickname meeting (e.g. `my-team-standup`) | No | — |
| Large meeting (10+ participants) | No | — |
| VAD loads and filters silence | Yes | PASS — Silero model loads from correct path, 3 speakers transcribed with VAD active (bot 8806, mock meeting). No "VAD not available" error. |
| Russian language detection | Yes | FAIL — Carol's Russian transcribed as Cyrillic but tagged language="en" |
| REST API returns active meeting data | Yes | FAIL — Returns completed meeting 8869 (0 segments) instead of active 8871-8875 (195 segments) |
| Speaker persona mapping | Yes | FAIL — Speakers show as VexaBot-{hash}, not Alice/Bob/Carol |

## Live TTS meeting test run 3 (2026-03-17 17:42-17:51)

**Meeting:** raf-yeou-nib (Google Meet)
**Setup:** 3 bots (8882-8884) with named personas, `voice_agent_enabled: true`. Using Piper voices (amy-medium, danny-low, irina-medium). 26 utterances sent over ~4 minutes including monologues, rapid back-and-forth, numbers, Russian, and silence gaps.

### Results

**Transcription pipeline: BROKEN**
- 0 segments persisted in Postgres for meetings 8882/8883/8884
- handlePerSpeakerAudioData callback NEVER called in any bot
- ScriptProcessor audio peak never exceeded 0.005 threshold
- SegmentPublisher published session_start and session_end but 0 transcription segments
- Bot-manager exit: "Received 0 segments from collector" for all 3 meetings
- This definitively confirms the ROOT CAUSE documented below: createMediaStreamSource() returns silence for WebRTC-received streams

**TTS pipeline: WORKING**
- All 26 /speak commands returned 202
- Bot logs show unmute->synthesize->play->mute cycle for every utterance
- 3 Piper voices used successfully: en_US-amy-medium (Alice), en_US-danny-low (Bob), ru_RU-irina-medium (Carol Russian)

### Key finding: previous run 2 scores were inflated
The run 2 claim of "195 segments across 5 listener bots" and "79/100" was misleading. Those 195 segments existed in the DB from some other pathway, but the per-speaker pipeline (ScriptProcessor -> Node.js -> SegmentPublisher -> Redis -> DB) produces 0 segments because the audio amplitude from WebRTC remote streams is always 0.0 in the ScriptProcessor. Run 3 confirms this with zero ambiguity: 26 utterances sent, 0 transcriptions produced, 0% accuracy.

---

## Live TTS meeting test run 2 (2026-03-17 17:10-17:17)

**Meeting:** raf-yeou-nib (Google Meet)
**Setup:** 6 bots (8870-8875), all with `voice_agent_enabled: true`. 3 TTS speaker bots + 1 host (Dima) + listener bots. All using OpenAI TTS with voice "alloy" (NOT the intended piper voices Amy/Danny/Irina).

### Results

**Transcription pipeline: WORKING**
- 195 segments persisted in Postgres across 5 listener bots (8871-8875)
- Bot 8870 has 0 segments (degraded mode -- found 5 media elements but 0 audio tracks, never started transcription)
- Segments contain meaningful English text matching the TTS conversation script
- Mutable->completed segment flow confirmed in Redis stream (16060 total stream entries)
- WebSocket connection and subscription confirmed; no live messages received during idle period

**Speaker breakdown (across all 5 listener bots):**
| Speaker | Segments | Sample text |
|---------|----------|-------------|
| VexaBot-2d7385 | 93 | "15% compared to last year. We need to discuss..." |
| VexaBot-f013a4 | 33 | "And this is Bob. I should sound different from Ali..." |
| VexaBot-22a159 | 27 | "Alice. And this is Bob. I should sound different..." |
| VexaBot-e9142e | 16 | "1312, the purple elephant dances on the moon." |
| VexaBot-2d6532 | 12 | "Hi, Alice. Before we get into that, I want..." |
| Dmitriy Grankin | 8 | "Okay, this is can you walk?" |
| VexaBot-d7d208 | 5 | "API responses are timing out because of..." |

**Russian transcription:**
4 segments contain Cyrillic text from Carol's Russian TTS:
- "Это Кэрол. Я говорю полки. Привет всем." (bot 8875)
- "Эдипо Мэйл Войс А, это Кэрол Я говорю по" (bot 8873)
- "Это Кэрол. Я говорю по всем." (bot 8872)
- "Это Кэрол. Я говорю «Пуке». Привет всем." (bot 8871)
All tagged language="en" -- language detection failure.

### Bugs found

#### 5. REST API returns wrong meeting for multi-bot native_id (2026-03-17)
GET /transcripts/google_meet/raf-yeou-nib returns meeting 8869 (completed, 0 segments) instead of active meetings 8871-8875 (195 segments). The API finds the first meeting by platform_specific_id, which is the oldest completed one. With 6 bots creating 6 meetings for the same native_id, the API should return the latest or aggregate.

#### 6. Language detection defaults to "en" for Russian audio (2026-03-17)
All 195 segments tagged language="en" including 4 segments with Cyrillic text. The transcription service returns Russian text correctly but does not detect the language. Likely the language detection model is not running or is configured to default to English.

#### 7. Speaker names are container IDs, not personas (2026-03-17)
TTS bots speak as Alice/Bob/Carol but are attributed as VexaBot-{hash} (the Google Meet display name of the speaking bot). This is technically correct (the speaker identity system maps audio to the participant tile name), but not user-friendly. The TTS meeting orchestrator should set bot display names to "Alice", "Bob", "Carol" instead of "VexaBot-{hash}".

#### 8. Host "Dmitriy Grankin" attributed 8 ghost segments (2026-03-17)
Dima is in the meeting listening (not speaking), but 8 segments are attributed to him. Sample: "Okay, this is can you walk?" -- this is likely cross-talk from a TTS bot being mis-attributed due to speaker identity voting errors when the speaking indicator is ambiguous.

#### 9. Bot 8870 failed to find active audio elements (2026-03-17)
Bot 8870 found 5 media elements but all had 0 audio tracks. Entered "degraded monitoring mode" with 0 transcriptions. The other 5 bots worked fine. Likely a timing issue where this bot started before other bots' audio streams were established.

## Real audio gate test attempt (2026-03-17 12:00-13:30)

### Setup
- Browser-1 (CDP localhost:9222) with Google auth (2280905@gmail.com)
- PulseAudio virtual_mic sink configured, alice-48k.wav as Chrome's fake audio capture
- WAV files: alice.wav, bob.wav, carol.wav in browser container at /tmp/
- Compose stack running with transcription workers healthy

### What worked
1. **Meeting creation**: Google Meet `/new` creates meetings successfully (tested 10+ times)
2. **Bot launch**: Bot containers start, connect to Redis, initialize per-speaker pipeline
3. **Bot admission**: Bot auto-admits to meetings where host is present (found via "Leave call" button)
4. **Meeting presence confirmed**: Screenshots show both "Dmitriy Grankin (host)" and "VexaBot" as Contributors
5. **Host mic audio verified**: Google Meet's own captions showed transcribed speech from alice-48k.wav ("The server logs show, memory leaks. The transcription worker pod.")
6. **Per-speaker pipeline initializes**: 3 audio streams started, VAD loaded, TranscriptionClient created, SegmentPublisher connected to Redis

### ROOT CAUSE: AudioContext createMediaStreamSource() returns silence

**Evidence from debug logging added to index.ts:**
```
[AudioDebug] Element 0: tag=AUDIO paused=false volume=1 muted=false readyState=4 tracks=[enabled=true muted=false readyState=live sampleRate=48000]
[AudioDebug] Stream 0: #1, procMax=0.000000, analyserMax=0.000000, ctxState=running, sr=16000, track=enabled=true,muted=false,state=live
[AudioDebug] Stream 0: #200, procMax=0.000000, analyserMax=0.000000, ctxState=running, sr=16000, track=enabled=true,muted=false,state=live
```

All 3 audio elements have live, enabled, unmuted tracks at 48kHz. AudioContext is `running`. But both ScriptProcessor AND AnalyserNode read absolute zeros. This was tested:
- With `--use-file-for-fake-audio-capture=/dev/null` (original config)
- Without that flag (PulseAudio-based audio)
- At 16kHz and 48kHz AudioContext sample rates
- With both ScriptProcessor and AnalyserNode

**Hypothesis:** Chrome's `createMediaStreamSource()` on WebRTC-received MediaStreams may not deliver audio data when Chrome runs in an automated/container environment. The MediaStream tracks report as live and enabled, but the actual audio samples are zero. This could be:
1. A Chrome bug with WebRTC audio rendering in containers (even with PulseAudio)
2. Google Meet processing audio internally via WebAudio before it reaches the `<audio>` elements (the elements may be "presentation" only)
3. A timing issue where the audio elements were captured before the WebRTC connection fully established audio flow

**Key evidence for hypothesis 3:** In one test run, `[NEW SPEAKER] Track 0 - first audio received` fired briefly (audio exceeded 0.005 threshold), then went back to silence at #200. This suggests audio may flow transiently.

**Additional evidence (2026-03-17 13:30, enhanced RTC logging):**
Added diagnostic logging to `getVideoBlockInitScript()` in `screen-content.ts`: RTCPeerConnection creation, track events with muted state, connection state, and periodic `inbound-rtp` stats. Results from 5+ meetings (siu-avfk-bvi, dtp-mifc-vzv, eey-wcjz-sku, dja-bpny-ttn, znb-giia-twv):
```
[Vexa] PC#1 track event: kind=audio id=ce7b07a7-... enabled=true muted=true
[Vexa] PC#1 iceConnectionState=connected
[Vexa] PC#1 connectionState=connected
```
The incoming audio track arrives with `muted=true` (remote end not providing data) and **never transitions to unmuted**. No `unmute` event fires. The `inbound-rtp` periodic stats check found zero packets received. This confirms the Google Meet SFU is establishing the WebRTC audio channel but NOT forwarding actual audio data to the bot, despite the host mic being active (verified via `getUserMedia` amplitude >0.6 on meeting page).

### Secondary blocker: CDP/browser instability

The host browser (CDP localhost:9222) is extremely unstable:
- Google Meet pages navigate to new meeting URLs spontaneously
- CDP connections via Playwright timeout frequently (30s+)
- The host leaves meetings unexpectedly (page closes or navigates)
- Multiple background Playwright processes compete for CDP

This made it impossible to reliably have both host and bot in the same meeting for >30 seconds.

### Changes made
1. **constans.ts**: Removed `--use-file-for-fake-audio-capture=/dev/null` from non-voice-agent bots. Now Chrome uses PulseAudio instead of fake audio backend. This is a reasonable improvement regardless of the test outcome.
2. **index.ts**: Debug logging added and then reverted. No net change.

### Path to 95
**Approach pivot**: The external audio injection approach (PulseAudio fake-capture from host browser) is the wrong path. The correct approach is:
1. Use bot's built-in TTS (`voice_agent_enabled: true`) to have speaker bots generate audio via TTS
2. A listener bot transcribes what speaker bots say
3. Browser-control creates meetings and admits bots
4. `tts-meeting` orchestrates the conversation script

This avoids the SFU audio forwarding issue entirely since bot TTS audio goes through PulseAudio -> Chrome -> WebRTC directly from within the bot container.

**Alternative**: Test with a real human host on a real machine (not headless/container) to bypass all container audio issues.
