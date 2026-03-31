# Bot Lifecycle Findings

## Confidence Table

| Transition | Platform | Score | Evidence | Last checked | To reach 90+ |
|-----------|----------|-------|----------|-------------|-------------|
| requested → joining | Google Meet | 95 | API + container spawn works, 10+ tests | 2026-03-17 | — |
| requested → joining | Teams | 90 | API works, mock + real tested, TTS env propagation verified | 2026-03-17 | — |
| joining → awaiting_admission | Google Meet | 80 | Bot navigates, clicks Ask to join. 3 real meetings. | 2026-03-17 | Test different meeting types |
| joining → awaiting_admission | Teams | 85 | Continue → Join now flow works on mock + real. Mic mute uses keyboard fallback. | 2026-03-17 | Verify mic actually muted from host side |
| awaiting_admission → active | Google Meet | 50 | **FALSE POSITIVE.** Bot reports admitted while in lobby. UI indicators visible pre-admission. Host screenshot confirmed. | 2026-03-17 | Implement audio-based verification |
| awaiting_admission → active | Teams | 85 | Real lobby admission via CDP works. Host clicked admit, bot entered. | 2026-03-17 | Pending admission by host for current test |
| active (audio flowing) | Google Meet | 30 | SFU forwards 0 packets when bot has /dev/null audio. Need voice_agent_enabled:true. Unverified. | 2026-03-17 | Test with voice_agent_enabled:true |
| active (audio flowing) | Teams | 60 | Muted tracks accepted after fix. Real meeting: pipeline started but no transcription content yet. | 2026-03-17 | Test with active speakers |
| active → completed | Both | 90 | Graceful leave, alone-timeout (fixed: checks speaker events), API delete all work | 2026-03-17 | — |
| TTS env propagation | Teams | 90 | ttsEnabled=true in BOT_CONFIG, TTS_SERVICE_URL=http://tts-service:8002 in container env. Verified via docker inspect. | 2026-03-17 | Verify TTS actually speaks in meeting |

**Overall: 74/100** — Bottleneck: Google Meet admission false positive (50) and audio forwarding (30).

## Bugs found and fixed (2026-03-17)

1. **False-positive waiting room selectors** — `[role="progressbar"]`, `[aria-label*="loading"]` matched in-meeting elements
2. **Admission logic not definitive** — required `admissionFound && !lobbyVisible`. Fixed: Leave button = definitive
3. **Alone-timeout counted bot** — excluded `data-self-name` tile, threshold `=== 0`
4. **Teams muted tracks rejected** — removed `!track.muted` filter
5. **VAD model path wrong** — added correct Docker image path
6. **GC killed ScriptProcessor** — persist refs on `window.__vexaAudioStreams`
7. **Pre-join mic mute clicked device dropdown** — `button[aria-label*="Mic"]` matched "Selected microphone: VirtualMicrophone, open microphone options". Fixed: removed broad selectors, added label safety filter (reject "selected"/"options"/"open"), added Ctrl+Shift+M keyboard fallback.
8. **TTS_SERVICE_URL not reaching bot container** — bot-manager Docker image was stale (missing `tts_enabled` parameter in `start_bot_container`). Rebuilt bot-manager image. Now correctly passes `ttsEnabled` in BOT_CONFIG and `TTS_SERVICE_URL` as container env var when `tts_enabled=true`.
9. **Alone-timeout with speaker events** — recording.ts now tracks `__vexaSpeakerEventCount` and checks it in addition to participant count. Bot is "alone" only if participant count is 0 AND no speaker events received.

## Active test (2026-03-17 16:46 UTC)

**Meeting:** Teams 9380435891213
**Bots:**
- Alice Speaker (meeting 8925): tts_enabled=true, TTS_SERVICE_URL verified in container env
- Bob Listener (meeting 8926): standard listener mode

**Status:** Both bots in waiting room, awaiting host admission.

**Pending verification:**
1. Mic is actually muted on join (host must confirm no noise from bot)
2. TTS /speak command works after admission
3. Alone-timeout doesn't trigger with silent host (>2min)
4. Bob transcribes Alice's speech

## Root cause: SFU audio forwarding (OPEN)

Google Meet SFU does not forward audio to bot when Chrome has `--use-file-for-fake-audio-capture=/dev/null`. Host sends 185K packets, bot receives 0. Fix: `voice_agent_enabled: true` uses PulseAudio instead. **UNVERIFIED** — needs testing.
