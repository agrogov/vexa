# TTS Meeting Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|-------------|
| TTS service responds | 15/15 | /speak returns 202, Piper TTS synthesizes successfully with 3 voices (amy, danny, irina) | 2026-03-17 18:23 | DONE |
| Audio plays through bot | 15/15 | Unmute->TTS->play->mute cycle confirmed in logs for all utterances | 2026-03-17 18:23 | DONE |
| Listener hears speaker | 12/15 | Google Meet: Bob (8887) heard Alice and Carol. 19 CONFIRMED segments from 2 speakers. Per-speaker pipeline working for Google Meet with voice_agent bots. Teams: BLOCKED (no host admission after 3 attempts) | 2026-03-17 18:35 | Teams needs host admission automation |
| Keywords match | 7/15 | Google Meet 15-utterance script: 9 captured (some garbled), 6 MISSING entirely. "Bernetti's" instead of "kubernetes", "Poster Asky UL" instead of "PostgreSQL". ~55% keyword accuracy on captured segments | 2026-03-17 18:35 | Improve TTS voice clarity or use slower speech rate |
| Speaker attribution | 10/15 | Google Meet: 17 segments attributed to "Alice Test", 2 to "Carol Williams". Carol's early utterances (lines 2,4,6,8,10) all missing -- attributed to Alice or dropped. Host "Dmitriy Grankin" got 1 ghost segment | 2026-03-17 18:35 | Fix Carol speaker detection. Investigate why Carol's early lines are missing |
| Language detection | 0/5 | No Russian utterances in this script. All segments tagged "en" | 2026-03-17 18:35 | Test with Russian utterances |
| Multi-speaker | 8/15 | 2 speakers detected (Alice Test, Carol Williams) out of 2 expected. Carol only appeared for 2 of her 7 utterances. Most Carol lines missing or merged into Alice | 2026-03-17 18:35 | Fix Carol detection or add delay between speakers |
| Rapid switching | 3/5 | Alice->Carol->Alice transitions captured for lines 11-15 but earlier transitions (lines 1-10) lost Carol entirely | 2026-03-17 18:35 | Investigate timing between speaker switches |

**Overall: 70/100** — Major improvement from 30/100. Google Meet per-speaker pipeline now produces real transcriptions. Keyword accuracy ~55% on captured segments. 6 of 15 utterances MISSING (all Carol's early lines). Teams BLOCKED by lobby admission.

## Run 4 details (2026-03-17 18:23 UTC) — Google Meet + Teams dual-platform

### Google Meet validation (meeting raf-yeou-nib)

**Setup:** Alice (8885 speaker, amy voice), Bob (8887 listener), Carol (8888 speaker). 15-utterance deployment incident script.

**Bob's listener (8887) captured 19 CONFIRMED segments from 2 speakers (Alice Test, Carol Williams).**

#### Line-by-line comparison

| # | Speaker | Script (abbreviated) | Transcribed | Verdict |
|---|---------|---------------------|-------------|---------|
| 1 | Alice | "Good morning everyone. Let me start with the deployment incident from last Thursday. The kubernetes cluster ran out of memory..." | "Good morning everyone. Let me start with Bernetti's cluster ran memory and three pods got evicted from the production namespace." | MAJOR -- "kubernetes" -> "Bernetti's", missing "deployment incident from last Thursday" |
| 2 | Carol | "That sounds serious. Which services were affected?..." | NOTHING | MISSING |
| 3 | Alice | "Yes, the payment processing was down for twelve minutes..." | "Yes, processing was down for 12 minutes. We lost about 4,000 transactions during that window. The autoscaler recovered it eventually, but the SLA breach is confirmed." | MINOR -- "processing" vs "payment processing", "is confirmed" vs "has been confirmed" |
| 4 | Carol | "Twelve minutes of downtime on payments is a big deal..." | NOTHING | MISSING |
| 5 | Alice | "The root cause was the horizontal pod autoscaler..." | "The root cause was the horizontal pod autoscaler. It was capped at five replicas which was not enough for the Black Friday traffic spike..." | MINOR -- truncated "twenty replicas" |
| 6 | Carol | "I agree. We should also add cluster autoscaler..." | NOTHING | MISSING |
| 7 | Alice | "Good point. Let me also give you an update on the database migration..." | "Good point. Let me also give you an update on the database migration. We need to migrate from Poster Asky UL 12 to 16. The main risk is the JSON column re-indexing on the transactions table, which has 300 million rows." | MAJOR -- "PostgreSQL" -> "Poster Asky UL" |
| 8 | Carol | "Three hundred million rows. What is the estimated downtime..." | NOTHING | MISSING |
| 9 | Alice | "About forty five minutes for the full reindex..." | NOTHING | MISSING |
| 10 | Carol | "Can we do a blue green deployment instead?..." | NOTHING | MISSING |
| 11 | Alice | "That is actually a great idea. Let me prototype that approach this week." | "about four that is actually a great idea. Let me prototype that approach this week. We can compare both options at the" | MINOR -- garbled prefix "about four", extra trailing text |
| 12 | Carol | "Perfect. One more thing. The API gateway needs rate limiting..." | "Perfect one more thing the api gateway needs rate limiting right now. There is zero protection against abuse We should add slower" | MINOR -- truncated ending (missing "sliding window rate limiter before next release") |
| 13 | Alice | "Agreed. Let me summarize the action items..." | "Agreed. Let me summarize the action items. First, increase auto-scaling to 20 replicas. Second, add cluster autoscaler and memory alerts. Third, Prototype migration by Thursday fourth at rate limiting to the API" | MINOR -- "auto-scaling" vs "HPA", "fourth at" garbled |
| 14 | Carol | "No that covers everything. Good meeting. See you Thursday." | "where before the next release no that covers everything odmy see you thursday" | MAJOR -- "Good meeting" -> "odmy", extra prefix text |
| 15 | Alice | "Thanks Carol. Meeting adjourned." | "Thanks, Carol. Meeting adjourned." | EXACT |

#### Summary

```
=== GOOGLE MEET VALIDATION ===
Utterances sent: 15
Exact: 1 (line 15)
Minor: 5 (lines 3, 5, 11, 12, 13)
Major: 3 (lines 1, 7, 14)
MISSING: 6 (lines 2, 4, 6, 8, 9, 10 -- all Carol's early lines + Alice line 9)
Speaker attribution: 17/19 segments correctly attributed (Alice Test), 2/19 Carol Williams (correct but incomplete)
Accuracy: 60% (9/15 utterances captured, ~55% keyword accuracy on captured)
```

**Root cause of missing Carol lines:** Carol's first 5 utterances (lines 2, 4, 6, 8, 10) were all MISSING. Carol only appeared in the transcription starting at line 12. This suggests Carol's audio stream took ~100s to be recognized by the listener. The first Carol CONFIRMED segment appears at 498s (her line 12), while Alice segments start at 396s. Carol's speaker-2 stream was likely receiving audio but not being transcribed until the speaker identity mapping resolved.

### Teams validation (meeting 9363537812909)

**3 attempts, all BLOCKED:**
- Attempt 1: Alice (8890) removed_by_admin, Bob (8891) waiting room timeout
- Attempt 2: Alice (8892) waiting room timeout (5min), Bob (8893) waiting room timeout
- Attempt 3: Alice (8894) waiting room timeout, Bob (8895) waiting room timeout

**Root cause:** No host admitted the bots from the Teams lobby. The Teams meeting host was not available to click "Admit" during any of the 3 attempts. Each bot correctly reached the waiting room and sent the awaiting_admission callback, but was never admitted.

```
=== TEAMS VALIDATION ===
Utterances sent: 0
Exact: 0
Minor: 0
Major: 0
MISSING: N/A (no conversation ran)
Speaker attribution: N/A
Accuracy: N/A
Status: BLOCKED -- no host admission after 3 attempts (6 bots total)
```

## Run 3 details (2026-03-17 17:42 UTC)

### What was sent

26 utterances via /speak endpoint across 3 bots:
- Alice (meeting 8882, voice en_US-amy-medium): utterances #1,2,4,6,9,12,16,20,23,26
- Bob (meeting 8883, voice en_US-danny-low): utterances #3,5,8,11,13,15,21,24
- Carol (meeting 8884, voices en_US-amy-medium + ru_RU-irina-medium): utterances #7,10,14,17,18(Russian),19,22,25

All 26 returned HTTP 202 "Speak command sent". Bot logs confirm unmute->synthesize->play->mute cycle for each.

### Conversation script

1. Alice: "Good morning everyone. Welcome to our weekly engineering sync. I want to start today with a comprehensive overview of where we stand on the platform migration project. We have been working on this for the past three weeks and I think it is time to take stock of our progress and identify any remaining blockers."
2. Alice: "First, the good news. Our PostgreSQL 16 upgrade is complete. We successfully migrated three hundred million rows from the legacy database over the weekend. The new cluster is running on dedicated hardware with ninety nine point nine percent uptime SLA."
3. Bob: "That is great news Alice. What about the API response times? Are we seeing improvements?"
4. Alice: "Yes, average response time dropped from two hundred milliseconds to forty five milliseconds."
5. Bob: "Forty five? That is much better than expected."
6. Alice: "Exactly. The connection pooling changes made a huge difference."
7. Carol: "I agree with Bob. I also want to highlight that the new indexing strategy reduced our query execution time by seventy percent. We went from scanning the entire user table of fifty million rows to using a composite B-tree index."
8. Bob: "What is the estimated downtime for the next deployment window?"
9. Alice: "About forty five minutes. We are using blue-green deployment so there should be zero customer-facing impact."
10. Carol: "And the rollback plan? If something goes wrong can we revert in under ten minutes?"
11. Bob: "Yes. We have automated rollback scripts that switch the load balancer back to the old cluster in under three minutes."
12. Alice: "As Carol mentioned earlier, the indexing improvements are critical. Bob, can you clarify how the new indexes interact with the migration scripts?"
13. Bob: "Sure. The migration creates the indexes after the bulk data load. We tested this with a copy of production data and it took about ninety minutes for the full index rebuild."
14. Carol: "From a business perspective, the infrastructure cost went down by four point two million dollars annually. We consolidated twelve servers into four high-performance nodes."
15. Bob: "That is impressive cost savings."
16. Alice: "Yeah, absolutely."
17. Carol: "I agree completely."
18. Carol (Russian): "Давайте теперь обсудим результаты тестирования на русском языке. Все автоматические тесты прошли успешно. Мы проверили производительность системы под нагрузкой и результаты превосходные."
19. Carol: "So to summarize the testing results in English. All automated tests passed successfully and performance under load was excellent."
20. Alice: "OK, after that brief pause, let me move on to the timeline. We are targeting Friday March twenty first for the final deployment. The total project budget was eight point five million dollars and we are coming in under budget at seven point three million."
21. Bob: "One more thing. The Kubernetes cluster needs to be upgraded from version one point twenty seven to one point twenty nine before the deployment. I already have the terraform scripts ready."
22. Carol: "Bob, make sure to coordinate with the security team on the Kubernetes upgrade. They need to review the new network policies before we go live."
23. Alice: "Perfect. Let me summarize the action items. Bob will complete the Kubernetes upgrade by Wednesday. Carol will finalize the load testing report by Thursday. I will update the stakeholder presentation with the final numbers. Our next sync is Friday at ten AM Pacific time."
24. Bob: "Sounds good. I will send the Kubernetes upgrade plan to the security team today."
25. Carol: "Great meeting everyone. Thanks for the thorough discussion. See you Friday."
26. Alice: "Thanks everyone. Meeting adjourned."

### Line-by-line comparison

| # | Speaker | Sent | Transcribed | Match |
|---|---------|------|------------|-------|
| 1 | Alice | (30+ word monologue) | NOTHING | MISSING |
| 2 | Alice | PostgreSQL 16, 300M rows | NOTHING | MISSING |
| 3 | Bob | API response times | NOTHING | MISSING |
| 4 | Alice | 200ms to 45ms | NOTHING | MISSING |
| 5 | Bob | Forty five? | NOTHING | MISSING |
| 6 | Alice | connection pooling | NOTHING | MISSING |
| 7 | Carol | indexing strategy, 70%, 50M rows | NOTHING | MISSING |
| 8 | Bob | estimated downtime | NOTHING | MISSING |
| 9 | Alice | 45 min, blue-green | NOTHING | MISSING |
| 10 | Carol | rollback plan, 10 min | NOTHING | MISSING |
| 11 | Bob | rollback scripts, 3 min | NOTHING | MISSING |
| 12 | Alice | Carol mentioned, indexing | NOTHING | MISSING |
| 13 | Bob | indexes after bulk load, 90 min | NOTHING | MISSING |
| 14 | Carol | $4.2M, 12 servers to 4 | NOTHING | MISSING |
| 15 | Bob | impressive cost savings | NOTHING | MISSING |
| 16 | Alice | Yeah, absolutely | NOTHING | MISSING |
| 17 | Carol | I agree completely | NOTHING | MISSING |
| 18 | Carol | Russian paragraph | NOTHING | MISSING |
| 19 | Carol | testing results English summary | NOTHING | MISSING |
| 20 | Alice | March 21, $8.5M budget, $7.3M | NOTHING | MISSING |
| 21 | Bob | Kubernetes 1.27->1.29, terraform | NOTHING | MISSING |
| 22 | Carol | security team, network policies | NOTHING | MISSING |
| 23 | Alice | action items summary | NOTHING | MISSING |
| 24 | Bob | Kubernetes upgrade plan | NOTHING | MISSING |
| 25 | Carol | Great meeting, see you Friday | NOTHING | MISSING |
| 26 | Alice | Meeting adjourned | NOTHING | MISSING |

### Accuracy metrics

- **Total utterances sent**: 26
- **Exact matches**: 0
- **Minor errors**: 0
- **Major errors**: 0
- **Missing entirely**: 26 (100%)
- **Language correctly detected**: N/A (0 segments)
- **Speaker correctly attributed**: N/A (0 segments)
- **Transcription accuracy**: 0%

## Root cause analysis

### The break: browser ScriptProcessor -> Node.js callback

The per-speaker transcription pipeline has this flow:
1. Browser: ScriptProcessorNode captures audio from 3 MediaStream elements (remote participants)
2. Browser: If audio peak > 0.005, calls `__vexaPerSpeakerAudioData(index, Float32Array)`
3. Node.js: `handlePerSpeakerAudioData()` receives audio, feeds to VAD, accumulates, sends to transcription worker
4. Node.js: On result, `SegmentPublisher.publishSegment()` writes to Redis
5. Transcription-collector reads from Redis, writes to DB

**Step 2 never fires.** The audio from remote participants via Google Meet SFU arrives at the bot's Chrome browser but the peak amplitude in the ScriptProcessor buffer never exceeds 0.005. Therefore:
- `handlePerSpeakerAudioData` is never called (0 calls across all 3 bots)
- No NEW SPEAKER / SPEAKER ACTIVE events
- No VAD speech detection
- No transcription worker requests from the Node.js pipeline
- SegmentPublisher publishes session_start and session_end but 0 transcription segments
- Redis stream has 0 transcription messages for meetings 8882/8883/8884
- Transcription-collector reports "No active meetings found in Redis Set"
- DB has 0 transcription rows

### Evidence

- Bot logs show: `[PerSpeaker] Browser-side audio capture started with 3 streams` but NO subsequent `[NEW SPEAKER]` or `[SPEAKER ACTIVE]` or `[DRAFT]` or `[CONFIRMED]` messages
- Transcription-collector logs: `No active meetings found in Redis Set` (every 10s for entire session duration)
- Redis: `active_meetings` set does not exist. Only `meeting_session:*:start` keys for our UIDs. Zero `transcription` type messages in stream.
- DB: `SELECT COUNT(*) FROM transcriptions WHERE meeting_id IN (8882,8883,8884)` = 0
- Bot-manager exit: "Received 0 segments from collector for meeting 8882/8883/8884"

### Previous findings were inflated

The previous report (run 2) claimed 79/100 with "~85% keyword accuracy" and "All bots transcribe other bots' speech. CONFIRMED entries appear for all 10 utterances across 5 listener bots." This was incorrect. The "independent verification" section showed transcriptions from VexaBot containers, but those likely came from a different transcription pathway (possibly the old WebSocket-based WhisperLive client in the browser, not the per-speaker pipeline that writes to the DB).

The actual accuracy was 0% because zero segments were written to the database. The previous run's "evidence" was reading transcriptions from a different meeting session or from the browser console rather than from the DB.

## What worked

1. **TTS speak pipeline**: /speak endpoint -> bot-manager routes to correct bot -> bot unmutes -> Piper TTS synthesizes -> audio plays through tts_sink -> virtual_mic -> Chrome -> Google Meet SFU. Confirmed by bot logs showing unmute/mute cycle for all 26 utterances.
2. **Bot admission**: All 3 bots (Alice Johnson, Bob Smith, Carol Williams) joined meeting raf-yeou-nib with correct display names. Auto-admitted within 30 seconds.
3. **Multi-voice TTS**: Piper voices en_US-amy-medium (Alice), en_US-danny-low (Bob), ru_RU-irina-medium (Carol Russian) all synthesized successfully.
4. **Session lifecycle**: session_start and session_end published to Redis correctly for all 3 bot sessions.

## What didn't work

1. **Per-speaker audio callback never fires**: The bridge between browser ScriptProcessor and Node.js `handlePerSpeakerAudioData` is broken. Remote audio from SFU is below the 0.005 amplitude threshold.
2. **Zero transcriptions produced**: Despite 26 utterances and 11 minutes of active meeting time, 0 transcription segments entered the pipeline.
3. **Transcription-collector idle**: "No active meetings found in Redis Set" for the entire session duration. The Redis set `active_meetings` was never populated.

## To reach 90+

1. **Fix the audio threshold**: The 0.005 peak amplitude threshold in the browser ScriptProcessor (index.ts line 1393) filters out all remote SFU audio. Either:
   - Lower the threshold (e.g., 0.0001)
   - Normalize audio levels from remote streams
   - Add logging to track actual audio levels per stream to determine appropriate threshold
2. **Or use browser-side transcription**: The 229 transcription worker requests during the session suggest there IS a browser-side pathway (BrowserWhisperLiveService) that successfully captures and transcribes audio. Route those results to the SegmentPublisher instead of (or in addition to) the ScriptProcessor->Node.js path.
3. **Add audio level monitoring**: Log actual maxVal from ScriptProcessor periodically to diagnose threshold issues.

## Dependency status
- bot-in-meeting: READY (3 bots in raf-yeou-nib, all admitted)
- tts-service: WORKING (Piper TTS via /speak endpoint, 3 voices)
- transcription pipeline: BROKEN (per-speaker audio callback never fires, 0 segments published)
