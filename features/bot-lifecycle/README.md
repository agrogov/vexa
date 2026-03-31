# Bot Lifecycle

## Why

Every feature depends on the bot reaching `active` state reliably. Transcription, recording, chat, voice agent — all start after `active`. If the bot falsely reports `active` while still in lobby, everything downstream produces zero results silently. This is the #1 reliability bottleneck in the system.

## What

Owns the state machine: `requested → joining → awaiting_admission → active → completed/failed`.

### Documentation
- [Bot Overview](../../docs/bot-overview.mdx)
- [Platforms: Google Meet](../../docs/platforms/google-meet.mdx)
- [Platforms: Microsoft Teams](../../docs/platforms/microsoft-teams.mdx)

## How

See `.claude/CLAUDE.md` for transition reliability table, state detection signals, and platform-specific knowledge sources.
