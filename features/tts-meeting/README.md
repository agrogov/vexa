# TTS Meeting

## Why

To reach 95% confidence we need ground truth: known input → verified output. TTS generates any conversation dynamically — no pre-recorded files, no VNC audio injection, no PulseAudio hacks. The bot's own TTS pipeline speaks into the meeting. Another bot listens and transcribes. We compare against the source text.

## What

Scripted meeting conversations using TTS. Speaker bots say specific text at specific times. A listener bot transcribes. We verify transcription matches the script — keywords, speakers, language, timing.

No external audio injection needed. The bot's built-in TTS pipeline (text → TTS service → PulseAudio → meeting audio) does everything.

### Documentation
- [Interactive Bots](../../docs/interactive-bots.mdx)

## How

1. `bot-in-meeting` delivers N speaker bots + 1 listener bot in a real meeting
2. For each line in the script: POST text to TTS → bot speaks it in the meeting
3. Listener bot transcribes
4. Compare: transcribed text vs script. Keywords match? Speakers correct? Language detected?

See `.claude/CLAUDE.md` for conversation script format, TTS endpoint, and verification report format.
