    # Add transcription_tier and new bot config fields to Kubernetes orchestrator

## PR Title

Add transcription_tier and new bot config arguments to Kubernetes orchestrator

## PR Description

The Kubernetes orchestrator's `start_bot_container()` and `_build_bot_pod()` are missing the new bot configuration arguments that all other orchestrators (docker, nomad, process) already support. This causes a runtime crash when bot-manager calls `start_bot_container(transcription_tier=...)`.

### Error

```
TypeError: start_bot_container() got an unexpected keyword argument 'transcription_tier'
```

### Changes (`services/bot-manager/app/orchestrators/kubernetes.py`)

- Add `transcription_tier`, `recording_enabled`, `transcribe_enabled`, `zoom_obf_token`, `voice_agent_enabled`, `default_avatar_url` parameters to `start_bot_container()` and `_build_bot_pod()`
- Pass `transcriptionTier`, `transcribeEnabled`, `obfToken`, `recordingEnabled`, `voiceAgentEnabled`, `defaultAvatarUrl` into the bot config JSON
- Make `bot_name` and `meeting_url` Optional to match other orchestrators
- Generate fallback bot name when none provided (`VexaBot-<hex>`)
- Filter null-valued keys from bot config before serializing (parity with other orchestrators)

### Files

| File | Change |
|------|--------|
| `services/bot-manager/app/orchestrators/kubernetes.py` | +35/-5 — add new bot config params |
| `services/vexa-bot/core/src/types.ts` | +4/-4 — move `teamsSpeaker` to end of BotConfig type |
| `services/vexa-bot/core/src/docker.ts` | +4/-4 — move `teamsSpeaker` to end of Zod schema |
