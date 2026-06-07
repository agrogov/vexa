# Groom — 260607 (Nemotron ASR alongside Whisper)

| field        | value |
|--------------|-------|
| release_id   | `260607-nemotron-asr` |
| stage        | `groom` |
| entered_at   | `2026-06-07T16:30:50Z` |
| actor        | `AI:groom` |
| predecessor  | `idle` |
| theme (AI)   | *"Add NVIDIA Nemotron ASR to `services/transcription-service` without regressing the existing Whisper/OpenAI-compatible contract."* |

---

## Scope, stated plainly

`services/transcription-service` is **not** a generic ASR multiplexer today.
It is a single-backend FastAPI app that loads one `faster-whisper`
`WhisperModel` at startup and then serves every request through that instance.

The current compatibility contract is stronger than the README alone suggests:

1. The API is presented as **OpenAI Whisper compatible** at
   `/v1/audio/transcriptions`.
2. The request form field `model` is **required**, but today it is only checked
   for presence; it does not select a backend.
3. The Vexa bot client hard-codes `model=whisper-1` in
   `services/vexa-bot/core/src/services/transcription-client.ts`, so existing
   live and deferred transcription callers assume the current Whisper-shaped
   contract and will keep sending that value unless explicitly changed.

The user request is to add
`nvidia/nemotron-3.5-asr-streaming-0.6b` **additionally**, not as a Whisper
replacement. That means the release must preserve the current Whisper path and
introduce an explicit way to choose Nemotron.

The code and model research show this is not a one-line model swap:

- Local service shape:
  - `services/transcription-service/main.py` imports `WhisperModel` directly and
    constructs a single global model instance on startup from `MODEL_SIZE`,
    `DEVICE`, and `COMPUTE_TYPE`.
  - Request-time decoding assumes Whisper/faster-whisper semantics:
    `word_timestamps`, `vad_parameters`, `task`, `initial_prompt`,
    hallucination heuristics, and the current `segments` schema.
- NVIDIA Nemotron model shape:
  - The official model card says the model is used through **NeMo**, not
    faster-whisper, via `nemo.collections.asr`.
  - Inference is designed around **cache-aware streaming** and requires a
    language selector `target_lang=<locale>|auto`, plus chunk/context settings
    such as `att_context_size`.
  - The model card describes Linux-only integration and lists the runtime as
    **NeMo 26.06**.

So the actual problem to scope is:

> turn the service from a single Whisper engine into a small backend-selection
> layer, while preserving the existing OpenAI-compatible request/response shape
> for current callers.

---

## Signal sources scanned

| source | notes |
|--------|-------|
| `services/transcription-service/main.py` | Single global `WhisperModel`; `model` field required but not used for backend selection. |
| `services/transcription-service/README.md` | Public contract is OpenAI Whisper-compatible `/v1/audio/transcriptions`; examples use `model=whisper-1`. |
| `services/transcription-service/docs/models.md` | Whisper-only model guidance today; no backend abstraction. |
| `services/transcription-service/requirements.txt` | Whisper runtime only (`faster-whisper`); no NeMo stack present. |
| `services/transcription-service/Dockerfile` | CUDA-oriented container, but built around current faster-whisper dependencies. |
| `services/transcription-service/tests/test_config.py` | Unit tests cover config helpers and tier logic only; no backend-selection coverage exists. |
| `services/vexa-bot/core/src/services/transcription-client.ts` | Hard-codes multipart field `model=whisper-1`; requests word timestamps; this is the highest-risk compatibility edge. |
| Hugging Face model card: `nvidia/nemotron-3.5-asr-streaming-0.6b` | Official interface uses NeMo, `target_lang`, cache-aware streaming config, mono WAV input, punctuation/capitalization output, and optional `auto` language detection. |

---

## Packs — candidates for this cycle

### Pack A — Selectable Nemotron backend in `transcription-service` (**recommended: YES, P0**)

- **source**: user request on 2026-06-07.
- **symptom**: the service can only run one ASR backend today. Adding Nemotron
  by replacing `WhisperModel` would break existing callers; doing nothing keeps
  Nemotron unavailable.
- **severity**: **P0**. This is the release's core feature.
- **scope shape (groom view; plan finalizes)**:
  - Introduce a backend-selection layer in `services/transcription-service`
    instead of a single global Whisper object.
  - Keep **Whisper** as an explicit supported backend.
  - Add **Nemotron** as a second backend using NVIDIA NeMo, not
    faster-whisper.
  - Define how callers choose the backend without breaking the current API:
    recommended shape is **service config default + optional request-time
    override**, while keeping current `model=whisper-1` requests valid.
  - Preserve the current response envelope (`text`, `language`,
    `language_probability`, `duration`, `segments`) for both backends, even if
    Nemotron requires adaptation internally.
  - Decide whether Nemotron supports the full existing request surface on day 1
    or only a compatible subset; if subset, reject unsupported combinations
    explicitly rather than silently ignoring them.
- **repo facts driving scope**:
  - `main.py` uses faster-whisper-specific transcription args and response
    fields.
  - The bot client hard-codes `model=whisper-1`, so backward compatibility must
    be real, not aspirational.
  - Nemotron’s official path is NeMo with `target_lang` and cache-aware
    streaming config; it is not a drop-in `WhisperModel` replacement.
- **estimated scope**: **2-4 develop days** depending on whether Nemotron is
  exposed as offline file transcription only in v1, or whether the release also
  adapts the service’s real-time segmentation/timestamp expectations fully.
- **repro confidence**: HIGH that the problem exists; MEDIUM on final effort
  because Nemotron output normalization and timestamp parity need real code
  validation.
- **owner feature(s)**: `transcription-service` + `realtime-transcription`.

### Pack B — Whisper-compat preservation and caller contract locks (**recommended: YES, P0**)

- **source**: same user request, plus local caller inspection.
- **symptom**: even a correct Nemotron integration can regress the installed
  base if `model=whisper-1` stops working, if word timestamps disappear, or if
  the request schema changes under the bot.
- **severity**: **P0**. This is the "preserve Whisper" half of the request.
- **scope shape**:
  - Add explicit compatibility checks proving existing Whisper callers still
    work unchanged.
  - Lock the `model=whisper-1` path as valid and mapped to Whisper.
  - Decide whether Nemotron gets a new request model name, a new backend field,
    or both; the important point is that the old request shape must continue to
    route to Whisper by default.
  - Verify the current bot assumptions:
    - `model=whisper-1`
    - `response_format=verbose_json`
    - `timestamp_granularities=word`
  - If Nemotron cannot supply equivalent word-level timestamps, scope whether
    Nemotron is allowed only for clients that do not require them, or whether
    the service must synthesize/normalize them before claiming parity.
- **estimated scope**: **0.5-1.5 develop days** on top of Pack A.
- **repro confidence**: HIGH.
- **owner feature(s)**: `transcription-service` + bot/transcription client
  contract.

### Pack C — Runtime + image changes for NeMo/Nemotron (**recommended: YES, P1**)

- **source**: official model card + current container inspection.
- **symptom**: the current image only installs the faster-whisper stack. There
  is no NeMo runtime, and Nemotron’s documented inference path is NeMo-based.
- **severity**: **P1**, but unavoidable if Pack A is approved.
- **scope shape**:
  - Add the NeMo/Nemotron runtime dependencies to the service image in a way
    that does not break the current Whisper image.
  - Decide whether both backends live in one image or whether Nemotron gets a
    separate compose worker/image variant. Groom recommendation: prefer one
    service API surface, but let plan decide whether the runtime should be
    unified or split if dependency conflicts appear.
  - Update docs/config for backend-specific env vars such as Nemotron model
    identity, target language default, and any streaming/chunk config the
    service exposes.
- **estimated scope**: **0.5-1.5 develop days** depending on dependency
  conflicts and image size.
- **repro confidence**: HIGH that runtime work is required; LOW-MEDIUM on exact
  package friction until implementation.
- **owner feature(s)**: `transcription-service` deployment/runtime.

### Pack D — DoD and test expansion for dual-backend transcription (**recommended: YES, P1**)

- **source**: current tests and README DoD gaps.
- **symptom**: the service has no dual-backend checks today; most tests are
  helper/config oriented, and the README DoD still describes a single-model
  service.
- **severity**: **P1**. Without this, the release can claim Nemotron support
  without regression protection.
- **scope shape**:
  - Add tests proving:
    - Whisper remains functional on the unchanged request path.
    - Nemotron can be selected and returns valid transcript JSON.
    - invalid backend/model selection fails clearly.
    - backend-specific unsupported options fail explicitly if not implemented.
  - Update service docs and feature DoDs so the gate distinguishes "Whisper
    works" from "Nemotron selectable and works."
- **estimated scope**: **0.5-1 develop day**.
- **repro confidence**: HIGH.
- **owner feature(s)**: `transcription-service` + release gate.

### Pack E — Streaming-native Nemotron semantics for bot realtime path (**recommended: DEFER unless Pack A proves parity is cheap**)

- **source**: Nemotron model card architecture notes.
- **symptom**: Nemotron’s strongest value is cache-aware streaming with explicit
  chunk/context control, but the current service is built around file upload
  requests that are then segmented/transcribed with Whisper semantics.
- **why DEFER**:
  - The user asked to add Nemotron **additionally** and preserve Whisper, not
    to redesign the entire realtime audio pipeline in the same cycle.
  - A first release can validly expose Nemotron behind the current HTTP
    contract if transcript quality and response normalization are acceptable.
  - Reworking the bot/service boundary to exploit cache-aware streaming is a
    larger architectural follow-on once the additive support exists.
- **route**: follow-on cycle after Pack A determines whether current upload-based
  invocation is sufficient.

---

## Suggested cycle shape — human picks

### Shape 1 — Additive dual-backend delivery (**my recommendation**)

- Pack A — selectable Nemotron backend
- Pack B — Whisper-compat preservation and caller locks
- Pack C — runtime/image changes
- Pack D — tests + DoD coverage
- DEFER Pack E — streaming-native architectural redesign

Why this shape:

- matches the user request exactly: **add Nemotron, preserve Whisper, choose
  what model to use**
- is grounded in the current code: the service needs backend selection, not
  just a new model name
- avoids coupling the feature request to a larger rewrite of the realtime audio
  protocol in the same cycle

### Shape 2 — Research-only spike (**fallback if the team wants uncertainty burned down first**)

- Keep this cycle limited to Pack A/B/C research deliverables:
  implementation note, dependency trial, and API-contract decision.
- Do **not** promise shipping Nemotron in develop until NeMo dependency fit and
  timestamp parity are proven.

Not recommended unless confidence needs to be raised before implementation.

---

## Recommendation

Approve **Shape 1**.

The repo facts are clear enough to move into `plan` with a concrete issue pack:

- today’s service is single-backend Whisper
- caller compatibility depends on keeping `model=whisper-1` valid
- Nemotron requires a different runtime and likely a normalization layer
- the user asked for additive support, not a replacement or a realtime
  architecture rewrite
