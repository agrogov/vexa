# Triage Log — 260607-nemotron-asr

## Failing DoD: `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`

- Classification: regression
- Bound check:
  - Approved in `tests3/releases/260607-nemotron-asr/plan-approval.yaml`
  - Registry entry: `tests3/registry.yaml` `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`
- Expected:
  - With `TRANSCRIPTION_BACKEND=nemotron`, `transcription-service` starts successfully, reaches healthy state, and accepts `/v1/audio/transcriptions` requests with `model=whisper-1` for backward-compatible callers.
- Actual:
  - The image builds, but the service crashes during startup before `/health` becomes healthy.
  - Remote validate on `DOCKER_HOST=ssh://root@10.10.10.2` failed with:
    - `No module named 'nemo.collections.asr.models.rnnt_bpe_models_prompt'`
    - `TypeError: Can't instantiate abstract class ASRModel with abstract methods setup_training_data, setup_validation_data`
- Root cause:
  - The current Nemotron loader in `services/transcription-service/main.py:343-351` uses `nemo_asr.models.ASRModel.from_pretrained(model_name=NEMOTRON_MODEL_NAME)`.
  - That runtime path does not match the serialized class/runtime expectations of `nvidia/nemotron-3.5-asr-streaming-0.6b` under the currently installed NeMo package set, so model restoration fails before the API starts.
- Touched commits:
  - `e315ed1c` `feat(transcription-service): add nemotron backend option`
  - `ac5bf4ee` `fix(transcription-service): make Nemotron images build outside corporate registry`
  - `5e3b5d30` `fix(transcription-service): bootstrap Nemotron image dependencies`
- Evidence:
  - Runtime container launched successfully with GPU support using image `vexa-transcription:nemotron-override-fix`.
  - Failure happens after process start and before readiness, so this is not a Docker build issue anymore; it is a Nemotron runtime integration issue.
- Next-fix target:
  - Replace the current generic `ASRModel.from_pretrained(...)` path with the Nemotron-compatible NeMo load/inference path required by this model, and lock the corresponding NeMo dependency/runtime version in the image.

Human decision:
- `fix this first: TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`

## Failing DoD: `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT` (follow-up)

- Classification: regression
- Bound check:
  - Approved in `tests3/releases/260607-nemotron-asr/plan-approval.yaml`
  - Registry entry: `tests3/registry.yaml` `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`
- Expected:
  - With `TRANSCRIPTION_BACKEND=nemotron`, a request to `/v1/audio/transcriptions`
    using a valid WAV and compatibility `model=whisper-1` returns `200 OK`.
- Actual:
  - Startup and `/health` now succeed, but the transcription request returns `500`.
  - Observed response:
    - `Unknown prompt key: 'None'. Available prompts: [...]`
- Root cause:
  - The Nemotron prompt-conditioned model requires a non-null prompt key.
  - The current service request mapping still reaches NeMo with a missing prompt
    value when callers omit or supply `language`, so inference fails before GPU
    work starts.
- Touched commits:
  - `72cb42d6` `fix(transcription-service): restore Nemotron prompt checkpoint`
- Evidence:
  - Model restored successfully and occupies ~5.1 GiB on GPU 0.
  - `/health` returns `200 OK`.
  - The first real `/v1/audio/transcriptions` request fails before inference with
    prompt-key validation.
- Next-fix target:
  - Normalize request language for Nemotron so the backend always passes a valid
    prompt key such as `auto` when the caller omits language, and verify a real
    transcription request completes.

Human decision:
- `fix this first: TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`
