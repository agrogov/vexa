# MS Teams Realtime Transcription Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 99 |
|-------|-------|----------|-------------|-------------|
| Create Teams meeting | 95 | Fully automated via CDP (run.js): Meet sidebar → Create meeting link → join as organizer. Multiple meetings created: 9383926870133, 9351292554180, 9349463533815 | 2026-03-18 | -- |
| Bot joins real meeting | 95 | Multiple real meetings tested. Bot navigates via light-meetings (with ?p= passcode), pre-join, Join now. Meeting IDs 8977, 9042, 9044 confirmed | 2026-03-18 | -- |
| Admission (auto-admit) | 99 | MutationObserver in organizer page catches Admit button the instant it appears. Both bots admitted in ~20s. Confirmed across run7 and latest runs (meetings 9351292554180, 9349463533815). Polling (200ms backup) as safety net | 2026-03-18 | -- |
| Lobby bypass | N/A | **Platform limitation**: Teams consumer (live.com) always puts anonymous/unauthenticated users in lobby regardless of "Who can bypass lobby" setting. "Everyone" in consumer Teams excludes users with zero credentials. Auto-admit is the correct solution | 2026-03-18 | Not achievable — platform policy |
| Audio capture (mixed stream) | 90 | Real meeting: bot found 5 media elements, connected all streams. 4 speakers transcribed. `findMediaElements` filters by `!el.paused` + audioTracks, NOT by muted | 2026-03-17 | -- |
| Speaker detection (voice-level) | 85 | Real meeting: 4 speakers via `voice-level-stream-outline` + `vdi-frame-occlusion`. Ghost speaker issue: departed participant keeps firing SPEAKER_START | 2026-03-17 | Fix ghost speaker |
| Audio routed per speaker | 80 | 4 speakers routed in real meeting. Bleeding: consecutive sentences bleed across speakers due to DOM detection lag (architectural) | 2026-03-17 | Accept as known limitation |
| Audio reaches TX service | 95 | 16 confirmed segments across 4 speakers. Non-empty text for all. Language detection works | 2026-03-17 | -- |
| WS delivery | 90 | `transcript.mutable` messages received ~26s after /speak. Channel: `tc:meeting:{id}:mutable` | 2026-03-17 | -- |
| REST /transcripts | 95 | 16 segments, 4 speakers. GET /transcripts/teams/{id} works. Also confirmed 2 segments in latest run | 2026-03-18 | -- |
| WS/REST consistency | 80 | Same pipeline source. WS=drafts+confirmed, REST=confirmed+dedup. Structural consistency, content equivalence not spot-checked | 2026-03-17 | Spot-check one segment end-to-end |

**Overall: 90/100** — Gate passes. Full automated loop works. Admission now reliable via MutationObserver. Three known gaps prevent 99:
1. **Ghost speaker** (open bug): departed participant's DOM state persists, generates silent audio → wastes transcription API calls
2. **Attribution bleeding** (~25% of segments): mixed-audio architecture mis-attributes at speaker transitions — architectural limit
3. **WS segment content unverified**: `transcript.mutable` events confirmed arriving, but content never cross-checked against REST

**Gate: PASS** — Full automated loop: create meeting → launch bots → auto-admit via MutationObserver (~20s) → TTS speak → segments in REST.

## Hot-debug end-to-end real meeting test (2026-03-17 19:35)

**Meeting:** 9382317484566
**Bots:** 8977 (listener, main token), 8979 (Alice listener), 8980 (Bob speaker, TTS), 8981 (Carol speaker)
**Result:** PASS — full pipeline proven end-to-end with 4 real speakers

### Audio capture breakthrough
`findMediaElements` filters by `!el.paused + audioTracks.length > 0` (NOT by `muted`). Bot connected all 5 media elements (2 unmuted mainAudio, 3 muted — connected regardless). Previous "muted tracks" failure was due to silent meeting (elements paused, not just muted).

### Speakers detected in real meeting
- "Dmitry Grankin" (organizer, real mic) — 5 segments
- "Alice Johnson (Guest)" (TTS bot) — 3 segments
- "Bob Smith (Guest)" (TTS bot) — 3 segments
- "Listener (Guest)" (listener bot) — 5 segments

### Full transcript (meeting 9382317484566)
```
[Dmitry Grankin          ] All right, see you. Ha! Good evening.
[Listener (Guest)        ] Good morning. Deployment update. The Kubernetes cluster migration is on track for
[Dmitry Grankin          ] deployment on track for Friday.
[Bob Smith (Guest)       ] I finished the database backup scripts yesterday we are ready to migrate whenever you give
[Listener (Guest)        ] whenever you give the green light. Great work, Bob.
[Alice Johnson (Guest)   ] for Friday. Bob, what about the monitoring data?
[Dmitry Grankin          ] Great work, Bob. What about the monitoring dashboards? Are those ready for the new
[Listener (Guest)        ] about the monitoring dashboards. Are those ready for the new cluster?
[Alice Johnson (Guest)   ] Are those ready for the new cluster?
[Listener (Guest)        ] Flashboards are configured. I added alerts for CPE.
[Bob Smith (Guest)       ] added alerts for CPU memory and disk usage on all nodes.
[Dmitry Grankin          ] Cluster, perfect.
[Listener (Guest)        ] Perfect. Let's proceed with the migration on Friday morning at 9 a.m.
[Alice Johnson (Guest)   ] I will send the calendar invite today.
[Dmitry Grankin          ] Sounds good. I will be on standby in case anything goes wrong during the migration. See you Friday.
[Bob Smith (Guest)       ] See you Friday.
```

### Transcript quality assessment
- **Text accuracy: ~90%** — 2 word errors in 16 segments: "Flashboards" (→ "Dashboards"), "CPE" (→ "CPU"). Both in the same Listener bot segment, suggesting audio path quality issue for that bot.
- **Speaker attribution: ~75%** — Mixed-audio architecture causes bleeding. The single mixed stream is carved by DOM signals (voice-level-stream-outline). When speaker changes mid-sentence, the boundary attribution can mis-assign. E.g. "Listener (Guest)" transcribes lines that belong to Alice/Bob. Root cause: DOM detection lag + mixed audio = sentences split at wrong boundaries.
- **Ghost speaker**: After Dmitry left the meeting, his per-speaker stream continued sending silent audio chunks to TranscriptionClient. Empty results (5+ empty results observed). Wastes API calls, not a data accuracy issue.

### WS live delivery confirmed
- Subscribed WS before /speak trigger
- `transcript.mutable` messages received at ~26.5s, 28.5s, 30.5s, 32.4s after subscription
- WS channel: `tc:meeting:{id}:mutable` (collector publishes after stream processing)
- Live delivery latency: ~25-30s (TTS synthesis + audio playback + transcription + collector)

### Collector processing
- Stream consumer processes XADD entries from bots
- Publishes change-only segments to `tc:meeting:{id}:mutable`
- REST merges Redis hash (mutable/recent) + Postgres (immutable/30s+)
- WS delivers `transcript.mutable` (includes drafts), REST delivers confirmed+deduplicated segments

## TTS dual-bot test (2026-03-17 18:23)

**Meeting:** 9363537812909
**Goal:** Launch Alice (speaker) + Bob (listener) on Teams, run 15-utterance conversation
**Result:** BLOCKED -- 3 attempts, all failed due to no host admission

| Attempt | Alice bot | Bob bot | Outcome |
|---------|-----------|---------|---------|
| 1 | 8890 (removed_by_admin) | 8891 (timeout) | Alice rejected, Bob expired |
| 2 | 8892 (timeout) | 8893 (timeout) | Both expired after 5min in waiting room |
| 3 | 8894 (timeout) | 8895 (timeout) | Both expired after 5min in waiting room |

**Root cause:** The Teams meeting host was not available to admit bots from the lobby. All 6 bots correctly reached the waiting room (AWAITING_ADMISSION callback sent), but none were admitted. Attempt 1 had Alice explicitly removed by admin.

**To unblock:** Either automate admission via CDP (as done in earlier tests with browser-1), or have a human host admit bots. The previous successful Teams test (bot 8889, meeting 9363537812909) was admitted by a human host.

## Real meeting test (2026-03-17 10:48)

**Meeting:** 9383926870133 (Vexa Bot E2E Test)
**URL:** `https://teams.live.com/meet/9383926870133?p=3M0pEks0lEe8EiJqWi`
**Bot ID:** 8803

### Automated flow (all via CDP):
1. Connected to browser-1 (CDP 9222, Teams session Dmitry Grankin)
2. Navigated to Meet sidebar -> clicked "Create a meeting link"
3. Filled title "Vexa Bot E2E Test" -> clicked "Create and copy link"
4. Navigated to meeting URL -> clicked "Join now" as organizer
5. Bot launched via POST /bots API
6. Bot navigated to meeting, set name "VexaBot-f5ff91", clicked Join now
7. Organizer's page showed lobby notification: "VexaBot-f5ff91 (Guest) - Waiting in the lobby"
8. Clicked "Admit" button via CDP -> bot entered meeting
9. Bot detected admission via hangup-button
10. WS received: awaiting_admission -> active -> failed

### Bot behavior in real meeting:
- Found 5 media elements (all with srcObject, MediaStream, 1 audio track each)
- All 5 audio tracks: `enabled` status unclear, `muted=true`
- After 10 retries (30s), bot exited with `post_join_setup_error`
- Bot clicked hangup button and left cleanly

### WS events received:
```
[WS 10:49:08] subscribed
[WS 10:49:22] meeting.status: awaiting_admission
[WS 10:49:42] meeting.status: active
[WS 10:50:17] meeting.status: failed
```

## WS 403 investigation (2026-03-17 10:44)

**Root cause:** The previous "WS 403" was NOT an auth issue. The api-gateway's `/ws` endpoint accepts the connection first (`ws.accept()`), then authenticates. The actual issue was either:
1. Wrong payload format for subscribe (needs `{action:"subscribe", meetings:[{platform:"teams", native_id:"<13-digit>"}]}`)
2. Or the 403 was from a different layer (e.g., reverse proxy)

**Fix:** Use correct header (`x-api-key`) and correct subscribe payload format. WS connects and subscribes successfully.

## Mock fixes applied (2026-03-17)

1. **Removed audio element clone** — `audioContainer.appendChild(mixedAudioEl.cloneNode(false))` was causing `document.querySelector('audio')` to find the clone (no srcObject) before the real element, breaking per-speaker audio routing. Fixed by removing the clone.

2. **Added ARIA participants panel** — Added hidden `[role="menuitem"]` elements with `<img>` children matching `collectAriaParticipants()` expectations. Without this, the bot thought it was alone (participant count = 0) and would leave after 120s.

## Known architecture risks

1. **Mixed audio duplication** — all speakers mixed in one stream, routed by DOM detection. Detection lag -> wrong attribution.
2. **200ms debounce** — `MIN_STATE_CHANGE_MS` delays speaker state changes.
3. **No per-speaker isolation** — unlike Google Meet, no separate audio streams.
4. **vdi-frame-occlusion** — Teams-internal class, could change with updates.
5. **RTCPeerConnection hook** — complex, intercepts WebRTC. Fragile if Teams changes RTC setup.
6. **Mock uses AudioContext WAV playback** — real Teams uses RTCPeerConnection remote tracks. The mock's `MediaStreamAudioDestinationNode` is found directly by `findMediaElements`; real Teams would need the RTC hook to inject audio elements.
7. **Muted audio tracks** — Teams delivers audio via 5 media elements with initially-muted tracks. The bot's `findMediaElements` filter (`track.enabled && !track.muted`) rejects all elements when nobody is speaking. The bot needs to either accept muted tracks or wait for `track.onunmute` events.

## Learned (2026-03-17)

- Browser-1 (port 6080/9222) has the Teams session (Dmitry Grankin), NOT browser-2
- Playwright connectOverCDP may timeout on heavy sessions -- raw CDP fallback needed
- Guest join via link works without auth, needs organizer to admit from lobby
- Meeting link format: `https://teams.live.com/meet/<ID>?p=<PASSWORD>`
- Teams has no `teams.new` shortcut -- use Meet sidebar -> "Create a meeting link"
- Mock audio element must be the first `<audio>` in DOM order, or `setupPerSpeakerAudioRouting` fails
- Bot's `collectAriaParticipants()` needs `[role="menuitem"]` with `img`/`[role="img"]` children -- mock must provide this or bot thinks it's alone
- `native_meeting_id` for Teams must be 10-15 digit numeric or 16-char hex hash
- VAD (Silero) not available in bot container -- all audio sent to transcription (no silence filtering)
- Language detection works for both English and Russian speech in mock WAV files
- WS endpoint accepts first then authenticates -- no 403 on connect, errors come as JSON messages
- Subscribe payload: `{action:"subscribe", meetings:[{platform:"teams", native_id:"<ID>"}]}`
- Real Teams has 5 media elements with srcObject MediaStreams, each with 1 audio track — muted=true for remote tracks, but `findMediaElements` doesn't filter by muted (filters by `!el.paused + audioTracks.length > 0`). All elements connected regardless of muted state
- Bot lobby admission automated: MutationObserver in organizer page catches Admit button instantly (~20s after bot launch). Backup: 200ms poll
- CDP-based Admit button click works reliably — `button:has-text("Admit")` or querySelectorAll('button') for text-contains-Admit
- **Lobby bypass is impossible for anonymous users on Teams consumer**: "Who can bypass lobby → Everyone" does NOT apply to zero-credential browser sessions. Bot always goes to lobby. Auto-admit via MutationObserver is the only solution
- MutationObserver must be installed in active meeting view (NOT on Hold/People sidebar) to catch the transient Admit notification
- Two bots admitted sequentially in the same observer callback: both admitted within 2s of each other
- Meeting coords encoded in URL as base64 JSON with meetingUrl, meetingCode, passcode
- Share link on Meet page triggers navigation — use the decoded URL from coords instead

## Test matrix for 99 confidence

| Scenario | Tested | Result |
|----------|--------|--------|
| Mock meeting (3 speakers, WAV audio) | Yes | PASS -- full pipeline end-to-end, 3 speakers, 8+ segments in REST API |
| Real meeting (automated create+join+bot+admit) | Yes | PASS -- join+admission+audio+transcription+WS all work |
| Real meeting (4 participants, 3 TTS bots + organizer) | Yes | PASS -- meeting 9382317484566, 16 segments, 4 speakers |
| Real meeting (organizer admits from lobby) | Yes (automated) | PASS -- CDP clicked Admit, bot detected hangup-button |
| Real meeting (guest join via link) | Yes (manual) | PASS (browser-2 joined as guest) |
| Real meeting (5+ participants) | No | -- |
| Real meeting (screen sharing active) | No | -- |
| Different meeting links | Yes | PASS -- 9381841545597, 9383926870133, 9382317484566 all work |
| WS live transcription delivery | Yes | PASS -- `transcript.mutable` messages received at T+26.5s after /speak trigger |
| WS segment content | No | transcript.mutable confirmed by type, content not logged (wrong type check in test) |
| WS/REST consistency | Partial | Same source pipeline; WS=drafts+confirmed, REST=confirmed+dedup |
| Personal meeting (`teams.live.com`) | Yes | PASS -- all real tests on teams.live.com |
| Enterprise meeting (`teams.microsoft.com`) | No | -- |
| Cold-start audio (silent meeting) | No | Untested -- when bot joins before any speakers, elements may be paused |
| Government (`gov.teams.microsoft.us`) | No | -- |
