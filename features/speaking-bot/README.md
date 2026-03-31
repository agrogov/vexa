# Speaking Bot

## Why

Bots need to speak in meetings — answering questions, providing summaries, or giving instructions. Text-to-speech enables voice interaction between the bot and meeting participants.

## What

This feature converts text to speech and plays it into the meeting audio so participants hear the bot speaking.

### Documentation
- [Interactive Bots](../../docs/interactive-bots.mdx)
- [Interactive Bots API](../../docs/api/interactive-bots.mdx)

### Components

- **tts-service**: converts text to audio (text-to-speech)
- **vexa-bot**: plays generated audio into the meeting via PulseAudio virtual mic
- **bot-manager**: relays speak commands from API to bot
- **api-gateway**: exposes the speak endpoint

### Data flow

```
client → api-gateway → bot-manager → vexa-bot → tts-service (text→audio)
                                          ↓
                                    vexa-bot (plays audio)
                                          ↓
                                    PulseAudio virtual mic
                                          ↓
                                    meeting audio output
```

### Key behaviors

- POST speak command with text triggers TTS generation
- tts-service converts text to audio
- Bot plays audio into meeting via PulseAudio virtual microphone
- Meeting participants hear the bot speaking
- Speak commands are queued (not overlapping)

## How

This is a cross-service feature. Testing requires the full compose stack with tts-service and a mock meeting.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Start a bot in a mock meeting
3. Send speak command: `POST /bots/{id}/speak` with `{"text": "Hello everyone"}`
4. Verify tts-service generates audio (check service logs)
5. Verify PulseAudio virtual mic receives audio output

### Known limitations

- Audio quality depends on TTS model and network latency
- No voice selection or customization documented
- PulseAudio virtual mic setup is container-specific
