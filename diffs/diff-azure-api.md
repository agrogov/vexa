# Azure OpenAI Transcription API Integration

## PR Title

Add Azure OpenAI gpt-4o-transcribe support to transcription service

## PR Description

Adds the ability to route audio transcription requests to Azure OpenAI `gpt-4o-*-transcribe` model deployments, enabling the transcription service to run without a local Whisper model. This supports a remote-only deployment mode where no GPU is required.

### Summary

- Add Azure OpenAI transcription backend for `gpt-4o-*-transcribe` models
- Support remote-only mode that skips local model loading entirely
- Synthesize Whisper-compatible segment responses from Azure's simpler JSON output

### Test plan

- [ ] Deploy with `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` configured
- [ ] Send a transcription request with `model=gpt-4o-mini-transcribe` and verify Azure is called
- [ ] Verify response contains synthesized `segments` array compatible with downstream consumers
- [ ] Deploy with `REMOTE_TRANSCRIBER_ONLY=true` and confirm local model is not loaded
- [ ] Verify `/health` returns 200 when remote-only (no local model)
- [ ] Verify local Whisper models still work when Azure is not configured
- [ ] Send a request for a non-Azure model when `REMOTE_TRANSCRIBER_ONLY=true` and no local model -- expect 503

## Changes

All changes are in `services/transcription-service/main.py`.

### Azure OpenAI configuration

Three new environment variables control the Azure endpoint:

| Variable | Default | Description |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | _(empty)_ | Azure OpenAI resource URL (e.g. `https://<resource>.openai.azure.com`) |
| `AZURE_OPENAI_API_KEY` | _(empty)_ | API key for the Azure OpenAI resource |
| `AZURE_OPENAI_API_VERSION` | `2025-03-01-preview` | Azure API version string |
| `REMOTE_TRANSCRIBER_ONLY` | `false` | When `true`, skip local model loading entirely |

### Remote-only mode

- `_remote_enabled()` returns `True` when `REMOTE_TRANSCRIBER_ONLY` is set or when both `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` are configured.
- On startup, if remote is enabled the service skips loading the local faster-whisper model, avoiding GPU/memory requirements.
- The `/health` endpoint reports healthy when remote is enabled even without a local model, and includes a `remote_enabled` field in the response.

### Model routing

- `_use_azure_transcribe(model_name)` detects Azure-eligible models by checking if the name starts with `gpt-4o-` and contains `transcribe` (e.g. `gpt-4o-mini-transcribe`, `gpt-4o-transcribe`).
- The `/v1/audio/transcriptions` endpoint checks the requested model before falling through to local Whisper. If the model matches, the request is forwarded to Azure; otherwise, the local model is used.
- If no local model is loaded and the requested model is not remote-capable, a 503 is returned.

### Azure transcription proxy (`_transcribe_via_azure`)

- Builds a multipart POST request to the Azure OpenAI `/audio/transcriptions` deployment endpoint using `httpx`.
- Passes through `language`, `prompt`, `temperature`, and `timestamp_granularities` when provided.
- Forces `response_format=json` because Azure `gpt-4o-*-transcribe` deployments do not support `verbose_json`.
- Runs the synchronous `httpx` call in `asyncio.to_thread` to avoid blocking the event loop.

### Response normalization

Azure's `json` response format returns `{"text": "..."}` without segments. To maintain compatibility with downstream consumers (WhisperLive, transcription-collector, UI), the response is enriched with a synthesized `segments` array containing:

- A single segment spanning the full audio duration (computed via `soundfile`)
- All standard Whisper segment fields (`id`, `seek`, `start`, `end`, `tokens`, `temperature`, `avg_logprob`, `compression_ratio`, `no_speech_prob`, etc.)

This ensures the rest of the pipeline processes Azure results identically to local Whisper results.

### New dependency

- `httpx` -- used for the outbound HTTP call to Azure OpenAI (already present in the project, now imported in this module).
