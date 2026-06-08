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

## Failing DoD: `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT` (post-review correctness)

- Classification: regression
- Bound check:
  - Approved in `tests3/releases/260607-nemotron-asr/plan-approval.yaml`
  - Registry entry: `tests3/registry.yaml` `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`
- Expected:
  - The release should add Nemotron without misleading request semantics, without
    request cross-talk under concurrency, and with a working registry proof for the
    Nemotron path.
- Actual:
  - Independent review found four post-validate defects:
    - backend choice is still per-worker, not per-request, even though `model` values
      imply request-time choice
    - `set_inference_prompt(target_lang)` mutates shared model state and is race-prone
      under concurrent requests
    - `tests3/checks/scripts/transcription-nemotron-backend-compat.sh` is stale and
      no longer matches the implementation
    - Nemotron transcript text currently leaks `<en-US>` control tokens into API output
- Root cause:
  - The current implementation optimized for functional green validation first, but
    still relies on global backend/model state and compatibility aliases that hide
    request semantics.
  - The registry check was not updated after the final NeMo integration shape changed.
- Touched commits:
  - `e315ed1c` through `f14e3e3e`
- Evidence:
  - `NemotronBackend.accepted_models()` accepts `whisper-1` while `_build_backend()`
    still selects one backend for the whole worker
  - `set_inference_prompt()` is called on a shared global model immediately before
    inference
  - live validation returned transcript text with `<en-US>` markers
- Next-fix target:
  - Make request semantics explicit and correct:
    - stop aliasing `whisper-1` onto Nemotron
    - serialize Nemotron inference or otherwise eliminate prompt-state races
    - update the Nemotron registry proof script to the current code path
    - strip prompt/control tags from Nemotron response text

Human decision:
- `fix this first: TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`

## Failing DoD: `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT` (manifest as primary audio)

- Classification: regression
- Bound check:
  - Approved in `tests3/releases/260607-nemotron-asr/plan-approval.yaml`
  - Registry entry: `tests3/registry.yaml` `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`
- Expected:
  - The Nemotron request returns `200 OK` with prompt metadata preserved into the
    Lhotse prompt dataset.
- Actual:
  - Startup is healthy and `set_inference_prompt('auto')` is logged, but the live
    request still returns `500` with:
    - `Unknown prompt key: 'None'`
- Root cause:
  - Passing raw audio files as the primary `audio` argument causes NeMo to build its
    temporary manifest without the prompt fields this model needs.
  - The prompt-aware dataset still reads `cut.supervisions[0].language == None`.
  - To preserve `target_lang`, the primary `audio` argument likely needs to be a
    manifest path whose entries include `target_lang`.
- Touched commits:
  - `13f24ba1` `fix(transcription-service): pass Nemotron audio positionally`
- Evidence:
  - Container logs show `Inference prompt set to 'auto' (index 101)`.
  - The following stack still fails in `audio_to_text_lhotse_prompt_index.py`
    on `cut.supervisions[0].language`.
- Next-fix target:
  - Restore the temp manifest entry with `target_lang`, but pass the manifest path
    as the primary `audio` argument to `transcribe(...)` instead of using the
    unsupported `manifest_filepath=` keyword path.

Human decision:
- `fix this first: TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`

## Failing DoD: `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT` (positional audio arg)

- Classification: regression
- Bound check:
  - Approved in `tests3/releases/260607-nemotron-asr/plan-approval.yaml`
  - Registry entry: `tests3/registry.yaml` `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`
- Expected:
  - The latest Nemotron backend returns `200 OK` for the repo WAV through
    `/v1/audio/transcriptions`.
- Actual:
  - Startup is healthy, but the live request still returns `500`.
  - Latest observed error:
    - `EncDecRNNTBPEModelWithPrompt.transcribe() missing 1 required positional argument: 'audio'`
- Root cause:
  - Passing `paths2audio_files=[...]` by keyword is still not satisfying the
    prompt-model transcribe signature in the installed NeMo runtime.
  - The next likely compatible shape is the positional audio argument
    `transcribe([wav_path], ...)`, with `set_inference_prompt(target_lang)` already set.
- Touched commits:
  - `5692f72f` `fix(transcription-service): use NeMo audio transcribe path`
- Evidence:
  - `/health` is `200 OK`.
  - The failure occurs at the transcribe call boundary before inference work starts.
- Next-fix target:
  - Pass the audio list as the first positional argument to `transcribe`,
    retain the explicit inference prompt, and rerun the live request.

Human decision:
- `fix this first: TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`

## Failing DoD: `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT` (transcribe entrypoint)

- Classification: regression
- Bound check:
  - Approved in `tests3/releases/260607-nemotron-asr/plan-approval.yaml`
  - Registry entry: `tests3/registry.yaml` `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`
- Expected:
  - The prompt-aware Nemotron backend accepts the repo WAV and returns `200 OK`
    through the normal `/v1/audio/transcriptions` contract.
- Actual:
  - Startup is healthy and the closed-manifest bug is gone, but the live request
    still returns `500`.
  - Latest observed error:
    - `EncDecRNNTBPEModelWithPrompt.transcribe() missing 1 required positional argument: 'audio'`
- Root cause:
  - The service calls `transcribe(manifest_filepath=...)` without supplying the
    primary audio argument expected by the NeMo transcribe API.
  - NeMo docs show the supported call shape as
    `transcribe(paths2audio_files=[...], target_lang=...)` for prompt-aware models.
- Touched commits:
  - `41268abd` `fix(transcription-service): set Nemotron inference prompt`
  - `1d548420` `fix(transcription-service): reopen Nemotron manifest path`
- Evidence:
  - `/health` is `200 OK`.
  - The request reaches the transcribe call and fails immediately on signature mismatch.
- Next-fix target:
  - Switch the Nemotron transcription call back to `paths2audio_files=[wav_path]`
    while keeping the explicit `set_inference_prompt(target_lang)` step.

Human decision:
- `fix this first: TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`

## Failing DoD: `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT` (manifest lifecycle)

- Classification: regression
- Bound check:
  - Approved in `tests3/releases/260607-nemotron-asr/plan-approval.yaml`
  - Registry entry: `tests3/registry.yaml` `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`
- Expected:
  - With `TRANSCRIPTION_BACKEND=nemotron`, a request to `/v1/audio/transcriptions`
    using the repo WAV returns `200 OK` after the prompt-aware manifest path is applied.
- Actual:
  - Startup is healthy and the previous `Unknown prompt key: 'None'` failure is gone,
    but the live transcription request still returns `500`.
  - Latest observed error:
    - `ValueError: I/O operation on closed file.`
- Root cause:
  - The new manifest-writing path in `services/transcription-service/main.py`
    writes JSON to `tmp_manifest` after the `NamedTemporaryFile(...)` context has
    already closed the handle.
  - This is a local file-lifecycle bug in the service adapter, not a NeMo runtime
    incompatibility.
- Touched commits:
  - `41268abd` `fix(transcription-service): set Nemotron inference prompt`
- Evidence:
  - `/health` is `200 OK`.
  - The request now reaches the manifest path and no longer fails with a `None`
    prompt key.
  - Container logs show the exception at `json.dump(..., tmp_manifest)`.
- Next-fix target:
  - Keep the temporary manifest file open while writing, or reopen the path before
    `json.dump`, then rerun the same Nemotron validation request.

Human decision:
- `fix this first: TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`

## Failing DoD: `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT` (runtime integration)

- Classification: regression
- Bound check:
  - Approved in `tests3/releases/260607-nemotron-asr/plan-approval.yaml`
  - Registry entry: `tests3/registry.yaml` `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`
- Expected:
  - Nemotron-backed `/v1/audio/transcriptions` accepts the repo WAV and returns `200 OK`
    on the same service contract used by Whisper callers.
- Actual:
  - Startup is healthy and the model restores on GPU, but live inference still fails in
    NeMo internals with prompt-shape errors.
  - Latest observed error:
    - `Sizes of tensors must match except in dimension 2. Expected size 76 but got size 74`
- Root cause:
  - The current service is forcing Nemotron through generic `transcribe()` paths that do
    not match the model family's supported runtime path.
  - Primary-source review shows NVIDIA recommends NeMo from `main` plus the cache-aware
    streaming / manifest workflow for this checkpoint, not the generic wrapper path.
- Touched commits:
  - `72cb42d6` `fix(transcription-service): restore Nemotron prompt checkpoint`
  - `8e52a3d6` `fix(transcription-service): map Nemotron prompt field correctly`
  - `d606d67b` `fix(transcription-service): pass Nemotron language via manifest`
  - `fcef2e0d` `fix(transcription-service): use tensor path for Nemotron prompts`
  - `cb31a8fb` `fix(transcription-service): drive Nemotron through manifest path`
  - `4af53222` `fix(transcription-service): trim Nemotron prompt mismatch`
- Evidence:
  - Whisper still succeeds on the same image and service contract.
  - Nemotron build, GPU runtime, and startup are good; failure is isolated to inference path.
- Next-fix target:
  - Replace the Nemotron runtime dependency with NeMo from `main` and rework the backend
    to use the supported prompt-aware/cache-aware path instead of layered service-side shims.

Human decision:
- `fix this first: TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`

## Failing DoD: `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT` (follow-up)

- Classification: regression
- Bound check:
  - Approved in `tests3/releases/260607-nemotron-asr/plan-approval.yaml`
  - Registry entry: `tests3/registry.yaml` `TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`
- Expected:
  - The Nemotron backend uses the model's documented cache-aware streaming inference
    path, not generic offline `transcribe(...)`, and exposes the documented latency
    knob with `[56,6]` as the service default.
  - Operators can optionally configure NeMo GPU phrase boosting for domain terms
    without changing callers or touching non-transcription services.
- Actual:
  - The current branch validates functional Nemotron transcription but still drives
    the model through `model.transcribe(manifest_path, ...)`.
  - There is no `att_context_size` config surface and no word-boosting config surface.
- Root cause:
  - The first integration targeted OpenAI-compatible service behavior and startup
    compatibility. NVIDIA's model card and NeMo example show that true streaming
    behavior requires `set_default_att_context_size(...)` and the cache-aware
    `conformer_stream_step(...)` loop.
- Next-fix target:
  - Rework `services/transcription-service` Nemotron inference to use NeMo's
    cache-aware streaming path.
  - Add `NEMOTRON_ATT_CONTEXT_SIZE=56,6` as the default env-controlled latency knob.
  - Add optional phrase-boosting env vars for NeMo GPU-PB / RNNT greedy decoding,
    document usage, and validate the Docker runtime.

Human decision:
- `fix this first: TRANSCRIPTION_NEMOTRON_BACKEND_COMPAT`

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
