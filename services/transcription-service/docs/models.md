# Transcription Backend Guide

## Backend choice

`services/transcription-service` now supports two startup-time backends:

| Backend | Env | Runtime | Best for |
|---------|-----|---------|----------|
| Whisper | `TRANSCRIPTION_BACKEND=whisper` | `faster-whisper` | Current Vexa bot path, word timestamps, lowest migration risk |
| Nemotron | `TRANSCRIPTION_BACKEND=nemotron` | NeMo ASR | Alternate NVIDIA ASR backend behind the same HTTP API |

Whisper remains the default and the compatibility path for existing
callers that send `model=whisper-1`.

## Whisper model selection

| Model | GPU VRAM (INT8) | CPU RAM (INT8) | Quality | Speed | Multilingual |
|-------|-----------------|----------------|---------|-------|--------------|
| **large-v3-turbo** | ~2.1 GB | ~6-8 GB | Excellent | Very Fast | Yes |
| **medium** | ~1-1.5 GB | ~2-4 GB | Very Good | Fast | Yes |
| **small** | ~0.5-1 GB | ~1-2 GB | Good | Very Fast | Yes |
| **base** | ~150 MB | ~300-600 MB | Good | Extremely Fast | Yes |
| **tiny** | ~75 MB | ~150-300 MB | Basic | Fastest | Yes |

All Whisper models are multilingual (99+ languages).

### Recommended Whisper default

- **Model**: `large-v3-turbo`
- **Compute**: `int8`
- **Why**: good quality / latency / VRAM balance for the current bot path

## Nemotron backend

Default Nemotron model:

- `NEMOTRON_MODEL_NAME=nvidia/nemotron-3.5-asr-streaming-0.6b`

Notes:

- The service integrates Nemotron through **NeMo ASR**, not
  `faster-whisper`.
- Backend selection happens at service startup, not per request.
- The HTTP request still requires the `model` form field for OpenAI
  compatibility.
- `model=whisper-1` remains accepted even on a Nemotron-backed
  deployment so existing callers can keep working unchanged.
- If the request provides `language=en`, `de`, `fr`, etc., the service
  maps common 2-letter codes to Nemotron locale-style values such as
  `en-US`, `de-DE`, `fr-FR`. If omitted, Nemotron uses
  `NEMOTRON_TARGET_LANG_DEFAULT` (default `auto`).

## Practical recommendation

- Use **Whisper** for the existing Vexa bot deployment today.
- Use **Nemotron** when you want to run an alternate backend behind the
  same service contract and are prepared to install the NeMo runtime.
- Do not assume Nemotron is yet a drop-in replacement for every
  timestamp-sensitive bot flow; Whisper remains the safest path for that
  workload.
