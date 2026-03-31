# Browser Control Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope

You deliver a **running bot container that is already in a real meeting** with audio flowing. One agent, one container, no handoffs mid-process. The platform agent receives a ready-to-go environment and only checks transcription output.

You own everything up to "bot is admitted and hearing audio." After that, the platform agent takes over to verify transcription.

## What you deliver

A single sequential process — no decoupling, no inter-agent communication:

```
1. Start host browser (auth cookies + PulseAudio)
2. Create meeting
3. Resample + inject audio (48kHz stereo WAV required)
4. Launch bot with voice_agent_enabled: true
5. Wait for bot in lobby (poll host People panel)
6. Admit bot (click Admit from host side)
7. Verify from host: bot in "In the meeting" section
8. Verify from bot: NEW SPEAKER events in logs (audio flowing)
9. Output: READY meeting_id=X bot_container=Y
```

Steps 1-9 are ONE agent, sequential. If any step fails, stop and diagnose. Don't hand off a broken state.

## Critical knowledge (learned 2026-03-17)

### Bot MUST use `voice_agent_enabled: true`
Without it, bot Chrome launches with `--use-file-for-fake-audio-capture=/dev/null`. Google's SFU classifies this as "no audio participant" and forwards 0 inbound audio packets. Bot hears nothing. Transcription produces 0 segments.

```bash
curl -s -X POST http://localhost:8056/bots \
  -H "X-API-Key: <token>" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"xxx","voice_agent_enabled":true}'
```

### Chrome fake audio requires 48kHz stereo WAV
`--use-file-for-fake-audio-capture` silently produces silence with 16kHz mono. Always resample:
```bash
ffmpeg -i alice.wav -ar 48000 -ac 2 /tmp/alice-48k.wav
docker cp /tmp/alice-48k.wav playwright-vnc-poc-browser-1-1:/tmp/
```

### Admission false positives
Bot reports "admitted" while still in lobby. UI indicators (Leave button, toolbar) are visible pre-admission. **Always verify from host side** — check People panel for bot in "In the meeting" section, not "Waiting to join."

### Verify audio from bot side
After admission, check bot logs for `[🔊 NEW SPEAKER]` events. If no NEW SPEAKER within 15s of admission, audio is NOT flowing — either bot isn't really admitted, or SFU isn't forwarding.

## Infrastructure

Host browser at `/home/dima/dev/playwright-vnc-poc/`:
- **Browser-1**: CDP localhost:9222, VNC localhost:6080 — Google + Teams auth
- **Browser-2**: CDP localhost:9224, VNC localhost:6081
- **Browser-3**: CDP localhost:9226, VNC localhost:6082 — reserved for Zoom
- PulseAudio with `virtual_mic` sink, `pipe-source` for audio injection
- Playwright at `/home/dima/dev/playwright-vnc-poc/node_modules/`

CDP scripts at `/home/dima/dev/vexa/features/browser-control/scripts/`

## Gate (local)

You output `READY meeting_id=X bot_container=Y` — meaning:
- Meeting exists and host is in it
- Audio is playing through host mic
- Bot is admitted (verified from host side)
- Bot is receiving audio (verified from bot logs: NEW SPEAKER events)

PASS = all 4 verified. FAIL = any one missing.

You do NOT verify transcription content — that's the platform agent's gate.

## Confidence ladder

| Level | Gate |
|-------|------|
| 0 | Not integrated |
| 30 | Browser builds and starts |
| 50 | CDP creates meeting, host joins |
| 60 | Audio plays through fake capture (48kHz stereo) |
| 70 | Bot launched with voice_agent_enabled:true, reaches lobby |
| 80 | Bot admitted (verified from host), audio flowing (NEW SPEAKER in logs) |
| 85 | Same for Teams |
| 90 | Full flow runs 3 times consecutively without failure |
| 95 | Cookie persistence, works after container restart |
| 99 | 10+ cycles across both platforms, zero failures |

## Critical findings
Save to `tests/findings.md`.
