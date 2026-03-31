# Browser Control Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach next level |
|-------|-------|----------|-------------|---------------------|
| Browser builds and starts | 30 | Works in playwright-vnc-poc (44h uptime) | 2026-03-17 | Build from vexa context |
| CDP creates Google Meet | 90 | meet.new works, 5+ meetings created | 2026-03-17 | — |
| CDP creates Teams meeting | 80 | Meet sidebar → create link tested | 2026-03-17 | — |
| Lobby admission via CDP | 90 | Admit button clicks work, 4+ bots admitted | 2026-03-17 | — |
| Cookie persistence | 40 | Auth persisted across 5 Chrome restarts | 2026-03-17 | Test after container rebuild |
| 5 bots in one meeting | 0 | Not tested | — | Launch 5 bots, admit all |

**Overall: 55/100**

## Approach change (2026-03-17)

### Wrong approach: external audio injection
We spent significant time trying to inject audio into meetings via PulseAudio, fake-capture WAV files, and pipe-source. This led to investigating "SFU audio forwarding failure" — Google Meet's SFU appeared to not forward audio between two headless browsers.

**This was the wrong problem to solve.**

### Right approach: bot's built-in TTS
The bot already has a TTS pipeline: text → TTS service → PulseAudio → meeting audio. With `voice_agent_enabled: true`, the bot speaks in the meeting. No external audio injection needed.

The correct architecture:
- **Speaker bots** use TTS to speak in the meeting (built-in capability)
- **Listener bot** transcribes what speakers say (built-in capability)
- **Browser-control** just creates the meeting and admits the bots
- **tts-meeting** orchestrates the conversation script

Browser-control does NOT own audio. It owns meetings + admission.

## What we learned (keep)

1. `voice_agent_enabled: true` gives bot PulseAudio (removes /dev/null flag)
2. Bot has `tts_sink` — TTS audio plays through it into the meeting
3. Chrome `--use-file-for-fake-audio-capture` requires 48kHz stereo WAV (for host browser)
4. Admission false positives: bot reports admitted while in lobby. Verify from host People panel.
5. CDP: one Playwright connection at a time. Open, do work, close.
6. Google Meet `meet.new` auto-joins if signed in, sometimes needs "Join now" click
7. Google Meet free accounts have meeting time limits

## What we learned (discard)

- ~~SFU audio forwarding failure~~ — wrong problem. We don't need SFU to forward between headless browsers. Bots speak via TTS.
- ~~PulseAudio pipe-source injection~~ — unnecessary. Bot's TTS handles audio.
- ~~48kHz WAV resampling for bot~~ — unnecessary. TTS generates audio at the right format.
- ~~module-remap-source, virtual-source experiments~~ — all unnecessary.
