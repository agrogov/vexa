# Bot Lifecycle Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope

You own the bot's state machine: `requested → joining → awaiting_admission → active → completed/failed`. You know every transition, every failure mode, every false positive. Platform agents (googlemeet, msteams, zoom) provide platform-specific selectors and knowledge — you use it to make transitions reliable.

## Why

The bot's state machine is the foundation of everything. If the bot doesn't reliably reach `active`, nothing works — no transcription, no recording, no chat. A false positive on admission silently produces zero results. A premature `completed` kills an active meeting. Every confidence score in the system is capped by the reliability of these transitions.

## What

### State machine

```
requested → joining → awaiting_admission → active → completed
                 ↘                    ↗         ↘
                  (auto-admit, no lobby)     failed (timeout, rejection, crash)
```

### Transition reliability (2026-03-17)

| Transition | Confidence | Evidence | Failure modes |
|-----------|-----------|----------|---------------|
| requested → joining | 95 | API creates meeting + container spawns reliably | Container fails to start (image missing, port conflict) |
| joining → awaiting_admission | 80 | Bot navigates to URL, clicks "Ask to join" | Selector changes, page load timeout, captcha |
| awaiting_admission → active | **50** | **False positives.** Bot reports admitted while in lobby. UI indicators (Leave button, toolbar) visible pre-admission. | False positive admission detection is the #1 bug |
| active → completed | 90 | Graceful leave works, alone-timeout works | Meeting ends unexpectedly, container killed |
| any → failed | 85 | Timeout, rejection, crash detected | Silent failures (bot thinks it's active but isn't) |

### State detection signals

| Signal | Reliability | Notes |
|--------|-------------|-------|
| Leave button visible | 60 | Visible in lobby too — false positive for admission |
| Toolbar buttons visible | 60 | Same problem — pre-admission UI |
| `[data-participant-id]` tiles | 70 | Bot's own tile counts, host may not appear in central list |
| Remote audio flowing (maxVal > 0.005) | **95** | Definitive — if audio arrives, bot IS in the meeting |
| Host People panel shows "In the meeting" | **90** | External verification — most reliable admission signal |
| `NEW SPEAKER` events in bot logs | **95** | Proves audio pipeline is working end-to-end |

**Best practice:** Use remote audio as the definitive admission signal. If UI says admitted but no audio after 15s → re-verify from host side.

### Platform-specific knowledge sources

| Platform | Agent | Selectors | Admission flow |
|----------|-------|-----------|---------------|
| Google Meet | `services/vexa-bot/core/src/platforms/googlemeet/.claude/CLAUDE.md` | selectors.ts | Ask to join → lobby → host admits → active |
| MS Teams | `services/vexa-bot/core/src/platforms/msteams/.claude/CLAUDE.md` | selectors.ts | Continue → Join now → lobby → host admits → active |
| Zoom | `services/vexa-bot/core/src/platforms/zoom/.claude/CLAUDE.md` | SDK callbacks | SDK join → waiting room → host admits → active |

### Critical knowledge (learned 2026-03-17)

- **`voice_agent_enabled: true` required for real meetings.** Without it, bot Chrome uses `--use-file-for-fake-audio-capture=/dev/null`. Google's SFU classifies as "no audio" and forwards 0 packets. Bot hears nothing.
- **Alone-timeout counts bot as participant.** Fixed: exclude `data-self-name` tile from count, use `=== 0` threshold.
- **Google Meet waiting room selectors have false positives.** `[role="progressbar"]` and `[aria-label*="loading"]` match in-meeting elements. Removed.
- **Teams muted tracks are valid.** `track.muted=true` is normal when nobody speaks. Don't filter.

## Gate (local)

Every state transition works reliably on both mock and real meetings:

| Check | Score | To reach 90+ |
|-------|-------|-------------|
| requested → joining (Google Meet mock) | 90 | — |
| requested → joining (Google Meet real) | 95 | — |
| requested → joining (Teams mock) | 85 | — |
| joining → awaiting_admission (Google Meet) | 80 | Test with different meeting types |
| awaiting_admission → active (Google Meet) | 50 | Fix false positive, verify with remote audio |
| awaiting_admission → active (Teams) | 85 | Tested with real lobby admission via CDP |
| active → completed (both platforms) | 90 | — |
| State detection: admission by remote audio | 0 | Implement audio-based admission verification |

**Overall: 72/100** — bottleneck is admission false positive at 50.

## Dependencies
- browser-control: [findings](../browser-control/tests/findings.md) — provides meeting environments
- googlemeet agent: [findings](../../services/vexa-bot/core/src/platforms/googlemeet/tests/findings.md) — platform selectors
- msteams agent: [findings](../../services/vexa-bot/core/src/platforms/msteams/tests/findings.md) — platform selectors
