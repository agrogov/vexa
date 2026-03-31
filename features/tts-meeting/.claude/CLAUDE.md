# TTS Meeting Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope

You orchestrate scripted meeting conversations using TTS. You ask `bot-in-meeting` for speaker bots and a listener bot, then script what each speaker says and when. You verify the listener's transcription matches what was said.

You don't know how bots get into meetings — that's bot-in-meeting's job. You own the conversation script and the verification.

## Why

To reach confidence 95+ on realtime transcription, we need to verify against known input. Pre-recorded WAVs are static. TTS lets us generate any conversation dynamically — different languages, speakers, speeds, overlaps — and verify the transcription matches the source text exactly.

This is the ground truth engine: we know what was said → we check what was transcribed → we measure accuracy.

## What

### Input: conversation script

```python
script = [
    {"speaker": "alice", "text": "Good morning, let me start with the product update", "at": 0},
    {"speaker": "bob", "text": "The backend needs a complete overhaul of the database", "at": 8},
    {"speaker": "carol", "text": "Давайте обсудим результаты тестирования", "at": 15, "language": "ru"},
    {"speaker": "alice", "text": "Great point Carol, any blockers?", "at": 22},
]
```

### Process

```
CRITICAL: A bot CANNOT hear itself. The /speak endpoint mutes mic during
capture. A SEPARATE listener bot (different user) MUST be in the meeting.

Minimum: 2 users, 2 bots. Speaker bot speaks, listener bot transcribes.
For 3 speakers: 4 users (Alice, Bob, Carol as speakers + Dave as listener).
409 uniqueness = 1 bot per user per meeting.

1. Request from bot-in-meeting:
   - N speaker bots (alice, bob, carol) each on a different user
   - 1 listener bot on yet another user
   - All in same meeting, all with voice_agent_enabled:true and bot_name set

2. For each line in script:
   - POST /bots/{platform}/{meeting_id}/speak with speaker's API key
   - Include voice parameter for different Piper voices
   - Wait 8-10s between lines (TTS generation + playback time)

3. Wait 60s for transcription to complete

4. Verify (MANUALLY, word by word):
   - GET /transcripts → segments with speaker names
   - Compare transcribed text against script LINE BY LINE
   - Mark each: ✅ exact, ⚠️ minor error, ❌ major error, 🚫 MISSING
   - Check speaker attribution: Alice's words attributed to "Alice Johnson"
   - Check language detection: Carol's Russian detected as "ru"
   - Check dashboard shows live transcripts
   - Check timing: segments arrive in script order
```

### Output: verification report

```
Script: 4 utterances (alice, bob, carol, alice)
Transcribed: 4 segments
Speaker accuracy: 4/4 correct (100%)
Keyword match: 18/20 keywords found (90%)
Language detection: ru detected for Carol (correct)
Timing: all segments in order
GATE: PASS at 95
```

### TTS service

Running at port 8002 inside compose stack. Endpoint:
```
POST http://tts-service:8002/synthesize
Content-Type: application/json
{"text": "Hello world", "voice": "en-US-JennyNeural"}
→ audio/wav response
```

Voices (from scenarios.py):
- Alice: `en-US-JennyNeural`
- Bob: `en-US-GuyNeural`
- Carol: `ru-RU-SvetlanaNeural`

Note: TTS service may use OpenAI API (needs OPENAI_API_KEY) or edge-tts. Check what's configured.

### Playing audio through bot

Each speaker bot has PulseAudio with `tts_sink`:
```bash
# Send audio to speaker bot
docker exec $SPEAKER_CONTAINER paplay --device=tts_sink /tmp/utterance.wav
```

Or pipe directly:
```bash
curl -s http://tts-service:8002/synthesize -d '{"text":"hello"}' | \
  docker exec -i $SPEAKER_CONTAINER paplay --device=tts_sink --raw --rate=16000 --channels=1
```

## Gate (local)

Scripted conversation → listener transcribes → keywords match → speakers correct.

| Check | Score | To reach 90+ |
|-------|-------|-------------|
| TTS service responds | 0 | POST /synthesize returns audio |
| Audio plays through bot tts_sink | 0 | paplay works, tts_sink RUNNING |
| Listener hears speaker (SFU forwards) | 0 | NEW SPEAKER events in listener logs |
| Transcription matches keywords | 0 | 80%+ keyword match against script |
| Speaker attribution correct | 0 | Each utterance attributed to correct speaker |
| Language detection correct | 0 | Russian detected as "ru" |
| Multi-speaker conversation | 0 | 3+ speakers, all attributed correctly |
| Rapid switching | 0 | A→B→A with <1s gaps, attribution holds |

**Overall: 0/100** — Not implemented.

## Dependencies

- **bot-in-meeting**: [findings](../bot-in-meeting/tests/findings.md) — delivers N bots in a meeting. MUST be READY before we start.
- **tts-service**: running in compose stack, port 8002

## Scenarios

Reuse from `features/realtime-transcription/mocks/scenarios.py`:
- `full-messy`: 3 speakers, overlaps, pauses, Russian, noise
- `rapid-overlap`: fast switching, interruptions, interjections
- `multilingual`: English + Russian in same meeting
