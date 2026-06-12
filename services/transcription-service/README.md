# Transcription Service

## Why

GPU inference is expensive, stateful, and hardware-specific. You don't want every service that needs transcription to manage its own model, CUDA runtime, and GPU memory. The transcription service isolates all of that behind a standard OpenAI-compatible API — separation of concerns.

Any client that speaks the OpenAI Whisper API can use it. The bot pipeline uses it for real-time meeting transcription. But it's a standalone, general-purpose service — not tied to Vexa. Send audio, get text back.

Under the hood: a selectable ASR backend behind an Nginx load balancer.
Whisper remains the default compatibility path. Nemotron can be enabled
per service instance. Add workers to scale. GPU or CPU. One API
endpoint, one docker-compose command.

### Documentation
- [Concepts](../../docs/concepts.mdx)

## What

- **OpenAI Whisper API compatible** (`/v1/audio/transcriptions`) -- works with any client that speaks the OpenAI audio API.
- **Selectable backend** -- choose `whisper` or `nemotron` at startup with `TRANSCRIPTION_BACKEND`.
- **Load-balanced** -- Nginx distributes requests across workers using least-connections.
- **Backpressure-aware** -- configurable fail-fast mode returns 503 when busy, letting callers buffer and retry.
- **GPU and CPU** -- same codebase, different docker-compose files.

Ships with one worker. Add more by uncommenting worker definitions in `docker-compose.yml` and `nginx.conf`. Each worker needs one GPU.

## How

### Run

```bash
# Copy and edit environment
cp .env.example .env
# Edit .env -- see docs/models.md for model/compute guidance

# Start (GPU)
docker compose up -d

# Start (CPU)
docker compose -f docker-compose.cpu.yml up -d

# Watch logs until the backend reports ready
docker compose logs -f
```

The service listens on the port mapped in `docker-compose.yml` (default 8083:80).

The Dockerfiles default to the Infobip registry and install the Infobip Root CA
unconditionally for prod deployment behind corporate SSL inspection:

- GPU: `docker.ib-ci.com/nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04`
- CPU: `docker.ib-ci.com/python:3.12-slim`

### Test

```bash
# Health check
curl http://localhost:8083/health

# Transcribe a file
curl -X POST http://localhost:8083/v1/audio/transcriptions \
  -H "X-API-Key: $API_TOKEN" \
  -F "file=@tests/test_audio.wav" \
  -F "model=whisper-1" \
  -F "response_format=verbose_json"

# Smoke test (service must be running)
bash tests/test_hot.sh --verify

# Stress test
bash tests/test_stress.sh

# Unit tests
pytest tests/ -v
```

### Configure

All configuration is via environment variables. Copy `.env.example` and adjust.

**Key variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSCRIPTION_BACKEND` | `whisper` | Backend for this service instance: `whisper` or `nemotron` |
| `MODEL_SIZE` | `large-v3-turbo` | Whisper model (see [docs/models.md](docs/models.md)) |
| `NEMOTRON_MODEL_NAME` | `nvidia/nemotron-3.5-asr-streaming-0.6b` | NeMo model to load when `TRANSCRIPTION_BACKEND=nemotron` |
| `NEMOTRON_TARGET_LANG_DEFAULT` | `auto` | Default Nemotron target language when the request omits `language` |
| `NEMOTRON_ATT_CONTEXT_SIZE` | `56,6` | Nemotron cache-aware streaming latency mode. Accepts `56,0`, `56,1`, `56,3`, `56,6`, or `56,13` |
| `NEMOTRON_BOOSTING_PHRASES_FILE` | (none) | Optional NeMo GPU phrase-boosting phrase list, one phrase per line |
| `NEMOTRON_BOOSTING_ALPHA` | `1.0` | Phrase-boosting shallow-fusion weight when `NEMOTRON_BOOSTING_PHRASES_FILE` is set |
| `NEMOTRON_BOOSTING_CONTEXT_SCORE` | `1.0` | Per-token context graph score for phrase boosting |
| `NEMOTRON_BOOSTING_DEPTH_SCALING` | `2.0` | Context graph depth scaling for phrase boosting |
| `WHISPER_HOTWORDS_FILE` | (none) | Optional Whisper hotwords phrase list, one phrase per line. Loaded once at startup and passed as `hotwords=` to faster-whisper. |
| `DEVICE` | `cuda` | `cuda` or `cpu` |
| `COMPUTE_TYPE` | `int8` | `int8`, `float16`, or `float32` |
| `CPU_THREADS` | `0` (auto) | CPU threads when `DEVICE=cpu` |
| `API_TOKEN` | (none) | Bearer token for authentication |
| `MAX_CONCURRENT_TRANSCRIPTIONS` | `2` | Concurrent model calls per worker |
| `FAIL_FAST_WHEN_BUSY` | `true` | Return 503 immediately when busy |
| `BUSY_RETRY_AFTER_S` | `1` | Retry-After header value (seconds) |
| `REPETITION_PENALTY` | `1.1` | Penalize repeated tokens (>1.0 = penalize) |
| `NO_REPEAT_NGRAM_SIZE` | `3` | Hard-block any N-word phrase from repeating |
| `VAD_MAX_SPEECH_DURATION_S` | `15.0` | Max segment length before forced split. Lower = shorter segments = faster pipeline confirmation |
| `VAD_MIN_SILENCE_DURATION_MS` | `160` | Min silence to trigger segment split |

These can be overridden per-request via form fields `max_speech_duration_s` and `min_silence_duration_ms`.

Full list with quality/VAD tuning parameters: `.env.example`.

### Backend selection

The service now supports two backend modes:

- `TRANSCRIPTION_BACKEND=whisper`
  - current/default behavior
  - uses `faster-whisper`
  - preserves the existing bot-safe path, including
    `model=whisper-1` and word timestamps
- `TRANSCRIPTION_BACKEND=nemotron`
  - uses NVIDIA NeMo from `NVIDIA/NeMo@main` with
    `nvidia/nemotron-3.5-asr-streaming-0.6b`
  - runs Nemotron through NeMo's cache-aware streaming path using
    `CacheAwareStreamingAudioBuffer` and `conformer_stream_step`
  - defaults to `NEMOTRON_ATT_CONTEXT_SIZE=56,6`, a 560 ms streaming
    chunk; override it with one of the supported right-context values
  - keeps the same HTTP endpoint and top-level response envelope
  - accepts `model=whisper-1` for compatibility with existing callers,
    and also accepts Nemotron model ids such as
    `nemotron-3.5-asr-streaming-0.6b`
  - requires `git` in the image because the supported runtime is
    installed from the NeMo GitHub repository rather than a released
    `nemo_toolkit` wheel
  - runs on Python 3.12 in the service image; current NeMo cache-aware
    streaming utilities do not parse under Python 3.10

Unknown `model` values are rejected with 400.

### Nemotron streaming latency

Nemotron's latency/accuracy operating point is controlled by
`NEMOTRON_ATT_CONTEXT_SIZE`, a pair of 80 ms-frame counts:

| Value | Chunk size |
|-------|------------|
| `56,0` | 80 ms |
| `56,1` | 160 ms |
| `56,3` | 320 ms |
| `56,6` | 560 ms |
| `56,13` | 1120 ms |

The service default is `56,6`, matching a middle-ground 560 ms chunk.
Use bracket syntax (`[56,6]`) or comma syntax (`56,6`); malformed values
fall back to `56,6`.

### Nemotron phrase boosting

Nemotron uses NeMo RNNT greedy decoding. Optional word or phrase boosting
uses NeMo GPU phrase boosting (GPU-PB), not Flashlight CTC boost files.
Create a plain text file with one phrase per line:

```text
vexa
meeting api
nemotron
```

Mount the file into the container and set:

```bash
TRANSCRIPTION_BACKEND=nemotron
NEMOTRON_BOOSTING_PHRASES_FILE=/app/config/boosting_phrases.txt
NEMOTRON_BOOSTING_ALPHA=1.0
NEMOTRON_BOOSTING_CONTEXT_SCORE=1.0
NEMOTRON_BOOSTING_DEPTH_SCALING=2.0
```

Increase `NEMOTRON_BOOSTING_ALPHA` if phrases are still missed; lower it
if the decoder over-inserts boosted terms.

### Whisper hotwords

The Whisper backend supports faster-whisper's `hotwords=` decoding bias.
Create a plain text file with one phrase per line (the same file format
as Nemotron's phrase list can be reused):

```text
Infobip
WhatsApp Business API
CPaaS
```

Mount the file into the container and set:

```bash
TRANSCRIPTION_BACKEND=whisper
WHISPER_HOTWORDS_FILE=/app/boosting/phrases.txt
```

The file is read once at startup, joined into a single space-separated
string, and passed as `hotwords=` on every `model.transcribe()` call.
The `/health` endpoint reports `hotwords_file` when active.

### Response format

The `/v1/audio/transcriptions` endpoint returns JSON with:

```json
{
  "text": "transcribed text",
  "language": "en",
  "language_probability": 0.98,
  "duration": 5.2,
  "segments": [{"start": 0.0, "end": 5.2, "text": "transcribed text"}]
}
```

- `language_probability` -- confidence (0.0-1.0) of the detected language. The bot uses this to decide whether to lock language detection or keep auto-detecting.
- `segments` -- segment-level timing for the transcription.

### Word-level timestamps

Request `timestamp_granularities=word` to get per-word timing in the response:

```bash
curl -X POST http://localhost:8083/v1/audio/transcriptions \
  -H "X-API-Key: $API_TOKEN" \
  -F "file=@audio.wav" \
  -F "model=whisper-1" \
  -F "response_format=verbose_json" \
  -F "timestamp_granularities=word"
```

Response segments include a `words` array:

```json
{
  "segments": [{
    "start": 0.0, "end": 3.76,
    "text": " Hello everyone, this is a test.",
    "words": [
      {"word": " Hello", "start": 0.0, "end": 0.44, "probability": 0.91},
      {"word": " everyone,", "start": 0.44, "end": 0.98, "probability": 0.78},
      {"word": " this", "start": 1.52, "end": 2.06, "probability": 0.98}
    ]
  }]
}
```

Used by the bot pipeline for speaker attribution on Teams' single-channel mixed audio: caption says "Alice spoke 10.0s-15.2s" → match word timestamps → attribute those words to Alice.

Default (`timestamp_granularities=segment`) returns no `words` array — no performance impact.

Whisper remains the supported backend for the current bot path that
expects word timestamps. Nemotron responses are normalized into the same
top-level JSON envelope, but word-level timestamp parity depends on the
installed NeMo runtime and model support.

### Scale

To add or remove workers, edit `docker-compose.yml` (add/uncomment worker service definitions) and `nginx.conf` (add/uncomment upstream entries), then restart:

```bash
docker compose up -d
```

### Troubleshoot

```bash
# Check all logs
docker compose logs

# Check a specific worker
docker compose logs transcription-worker-1

# Check load balancer status
curl http://localhost:8083/lb-status

# Verify GPU is visible
docker compose exec transcription-worker-1 nvidia-smi

# Test nginx config
docker compose exec transcription-api nginx -t
```

**Common issues:**
- **GPU not available** -- use `docker-compose.cpu.yml` instead.
- **Out of memory** -- switch to a smaller model (see [docs/models.md](docs/models.md)).
- **Port conflict** -- change the host port in `docker-compose.yml`.

### Known limitations

| Area | Status | Detail |
|------|--------|--------|
| **Certainty** | HIGH | API and config well documented |
| **Single GPU capacity** | Known | Single GPU on BBB handles ~2 concurrent meetings. Beyond that, queuing increases and LIFO skipping kicks in. |
| **Whisper hallucination on silence (bug #24)** | Known | When audio contains silence or very low-level noise, Whisper can hallucinate content (e.g., phantom "fema.gov" segment). Mitigation: bot-side hallucination filter in `core/src/services/hallucinations/`. New patterns should be added to the filter list. Also: `REPETITION_PENALTY=1.1` and `NO_REPEAT_NGRAM_SIZE=3` help reduce repetitive hallucinations. |
| **Naming mismatch: TRANSCRIBER_URL vs TRANSCRIPTION_SERVICE_URL** | Fixed | Standardized on `TRANSCRIPTION_SERVICE_URL` and `TRANSCRIPTION_SERVICE_TOKEN` everywhere. Old names (`TRANSCRIBER_URL`, `TRANSCRIBER_API_KEY`) accepted as backward-compat aliases in lite entrypoint. |

## Integration with Vexa

Set these in the Vexa gateway environment:

```bash
TRANSCRIPTION_SERVICE_URL=http://localhost:8083/v1/audio/transcriptions
TRANSCRIPTION_SERVICE_TOKEN=<same value as API_TOKEN above>
```

## Public Docs

- [Concepts](https://docs.vexa.ai/concepts)
- [Recording & Storage](https://docs.vexa.ai/recording-storage)

## DoD

| # | Check | Weight | Ceiling | Status | Evidence | Last checked | Tests |
|---|-------|--------|---------|--------|----------|--------------|-------|
| 1 | `GET /health` returns 200 (Nginx + at least one worker up) | 15 | ceiling | untested | — | — | — |
| 2 | `POST /v1/audio/transcriptions` returns transcript JSON for valid audio file | 30 | ceiling | untested | — | — | — |
| 3 | Model loaded successfully on worker startup (logs confirm) | 20 | ceiling | untested | — | — | — |
| 4 | Backpressure: returns 503 with Retry-After when all workers busy (`FAIL_FAST_WHEN_BUSY=true`) | 15 | — | untested | — | — | — |
| 5 | Nginx load balancer distributes across configured workers (`GET /lb-status`) | 10 | — | untested | — | — | — |
| 6 | `API_TOKEN` set and unauthenticated requests rejected | 10 | — | untested | — | — | — |

Confidence: 55 (3/6 items pass: TRANSCRIPTION_UP health check, POST /v1/audio/transcriptions works via realtime-transcription feature + compose test-transcription, TRANSCRIPTION_TOKEN_VALID auth check. -20: backpressure 503 untested. -15: load balancer status untested. -10: model startup only implied.)

## License

Apache-2.0
