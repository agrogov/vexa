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
- The supported runtime path for this checkpoint is currently
  `nemo_toolkit[asr] @ git+https://github.com/NVIDIA/NeMo.git@main`,
  matching the NVIDIA model card guidance.
- Nemotron inference uses the documented cache-aware streaming path:
  `CacheAwareStreamingAudioBuffer` feeds chunks into
  `conformer_stream_step(...)`.
- Backend selection happens at service startup, not per request.
- The HTTP request still requires the `model` form field for OpenAI
  compatibility.
- Nemotron-backed deployments accept the existing compatibility value
  `model=whisper-1`, and also accept truthful Nemotron model ids such as
  `nemotron-3.5-asr-streaming-0.6b`.
- If the request provides `language=en`, `de`, `fr`, etc., the service
  maps common 2-letter codes to Nemotron locale-style values such as
  `en-US`, `de-DE`, `fr-FR`. If omitted, Nemotron uses
  `NEMOTRON_TARGET_LANG_DEFAULT` (default `auto`).

### Nemotron streaming configuration

`NEMOTRON_ATT_CONTEXT_SIZE` controls the runtime latency/accuracy point.
It accepts comma or bracket syntax; the service default is `56,6`.

| Value | Right context | Chunk size |
|-------|---------------|------------|
| `56,0` | 0 frames | 80 ms |
| `56,1` | 1 frame | 160 ms |
| `56,3` | 3 frames | 320 ms |
| `56,6` | 6 frames | 560 ms |
| `56,13` | 13 frames | 1120 ms |

Chunk size is the current 80 ms frame plus right context. The first value
is left context and remains `56` for this model family.

### Nemotron phrase boosting

Optional phrase boosting uses NeMo GPU phrase boosting for RNNT greedy
decoding. Configure it with:

| Variable | Default | Description |
|----------|---------|-------------|
| `NEMOTRON_BOOSTING_PHRASES_FILE` | unset | Plain text file, one phrase per line |
| `NEMOTRON_BOOSTING_ALPHA` | `1.0` | Shallow-fusion weight for the boosting tree |
| `NEMOTRON_BOOSTING_CONTEXT_SCORE` | `1.0` | Per-token context graph score |
| `NEMOTRON_BOOSTING_DEPTH_SCALING` | `2.0` | Context graph depth scaling |

Example phrase file:

```text
vexa
meeting api
webhook delivery
```

## Practical recommendation

- Use **Whisper** for the existing Vexa bot deployment today.
- Use **Nemotron** when you want to run an alternate backend behind the
  same service contract and are prepared to install the NeMo runtime.
- Do not assume Nemotron is yet a drop-in replacement for every
  timestamp-sensitive bot flow; Whisper remains the safest path for that
  workload.
