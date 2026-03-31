# Current — Bot Defaults & Platform Confidence

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Why

Bots must be slim, silent, and always TTS-ready. Both Google Meet and Teams must transcribe reliably. This is the shipping gate.

## Bot defaults (the spec)

| Behavior | Default | Notes |
|----------|---------|-------|
| **Mic** | ON but silent | PulseAudio tts_sink muted (gain=0). No noise. |
| **Camera** | OFF | No virtual camera, no avatar, no canvas stream |
| **Incoming video** | OFF | Video block script on Google Meet. Skipped on Teams (breaks audio). |
| **Outgoing video** | OFF | No video track sent |
| **PulseAudio** | Always running | tts_sink muted by default. Every bot is TTS-ready. |
| **TTS** | Always available | /speak unmutes tts_sink → plays → re-mutes. No flag needed. |
| **Transcription** | ON | Per-speaker pipeline always active |
| **Recording** | ON | MediaRecorder always active |
| **Speaker metadata** | ON | Speaker events always recorded |

**No `tts_enabled` flag needed.** Every bot can speak. PulseAudio is always there, just silent.

**`voice_agent_enabled` is still needed** for Teams admission detection (tangled in browser init). TODO: decouple.

## API

```
POST /bots
{
  "platform": "google_meet" | "teams",
  "native_meeting_id": "xxx",
  "meeting_url": "https://...",        // Required for Teams (includes passcode)
  "bot_name": "Alice Johnson",         // Display name in meeting
  "voice_agent_enabled": true,         // Needed for Teams. TODO: remove.
  "language": "en"                     // Optional, auto-detected
}
```

Speak: `POST /bots/{platform}/{meeting_id}/speak {"text":"...", "voice":"en_US-amy-medium"}`

## Confidence

| Check | Google Meet | Teams |
|-------|-----------|-------|
| Bot joins + admitted | 95 | 90 |
| Bot silent when idle | 90 | 90 (tts_sink muted) |
| No camera/video | 95 | 95 |
| Human speaks → transcribed | 92 | 87 |
| TTS speaks → other bot transcribes | 92 | 87 |
| Speaker attribution | 90 | 85 |
| /speak works | 95 | 90 |
| Bot stays alive 5+ min | 95 | 90 |
| **Overall** | **92** | **87** |

## To reach 90 on Teams

1. Fix start clipping (200ms delay added, needs retest with rebuilt bots)
2. Fix cross-utterance bleed (VAD/segmentation boundary)
3. Harden auto-admit for Teams (People panel, not "Admit" text button)

## To reach 95 on both

1. Multiple meetings with different URLs
2. Different participant counts
3. Russian language detection
4. Manual validation on 10+ utterances per platform
5. Dashboard shows live transcripts

## Debug with hot-debug skill

See `skills/hot-debug/.claude/CLAUDE.md` — fast iteration loop (<90s per cycle). Reuse meetings, poll don't sleep, Docker layer cache.
