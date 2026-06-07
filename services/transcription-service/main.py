"""
Vexa-Compatible Transcription Service (PoC)
Implements OpenAI Whisper API format for seamless integration with Vexa
"""
import os
import io
import time
import logging
import asyncio
import json
import sys
import tempfile
import types
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Set
import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
import uvicorn
from faster_whisper import WhisperModel
# faster-whisper uses CTranslate2 internally (no PyTorch needed)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
WORKER_ID = os.getenv("WORKER_ID", "1")
MODEL_SIZE = os.getenv("MODEL_SIZE", "large-v3-turbo")
TRANSCRIPTION_BACKEND = os.getenv("TRANSCRIPTION_BACKEND", "whisper").strip().lower() or "whisper"
NEMOTRON_MODEL_NAME = os.getenv(
    "NEMOTRON_MODEL_NAME",
    "nvidia/nemotron-3.5-asr-streaming-0.6b",
).strip()
NEMOTRON_TARGET_LANG_DEFAULT = os.getenv("NEMOTRON_TARGET_LANG_DEFAULT", "auto").strip() or "auto"

# Device detection: Use environment variable or default to cuda for GPU containers
# CTranslate2 (used by faster-whisper) will automatically detect and use CUDA if available
DEVICE = os.getenv("DEVICE", "cuda")

# Compute type optimization: Use INT8 for optimal VRAM efficiency
# Research shows: large-v3-turbo + INT8 = ~2.1 GB VRAM (validated)
# Provides 50-60% VRAM reduction with minimal accuracy loss (~1-2% WER increase)
COMPUTE_TYPE_ENV = os.getenv("COMPUTE_TYPE", "").strip().lower()
if COMPUTE_TYPE_ENV:
    COMPUTE_TYPE = COMPUTE_TYPE_ENV
else:
    # Default to INT8 for both GPU and CPU (optimal balance of speed, memory, and accuracy)
    COMPUTE_TYPE = "int8"

# CPU threads configuration (for CPU mode optimization)
CPU_THREADS = int(os.getenv("CPU_THREADS", "0"))  # 0 = auto-detect

# Quality / decoding parameters (optional)
def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, None)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")

def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, None)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"Invalid int env {name}={raw!r}, using default {default}")
        return default

def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, None)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning(f"Invalid float env {name}={raw!r}, using default {default}")
        return default

# Transcription defaults (can be overridden via env)
BEAM_SIZE = _env_int("BEAM_SIZE", 5)
BEST_OF = _env_int("BEST_OF", 5)
COMPRESSION_RATIO_THRESHOLD = _env_float("COMPRESSION_RATIO_THRESHOLD", 1.8)
LOG_PROB_THRESHOLD = _env_float("LOG_PROB_THRESHOLD", -1.0)
NO_SPEECH_THRESHOLD = _env_float("NO_SPEECH_THRESHOLD", 0.6)
CONDITION_ON_PREVIOUS_TEXT = _env_bool("CONDITION_ON_PREVIOUS_TEXT", False)
PROMPT_RESET_ON_TEMPERATURE = _env_float("PROMPT_RESET_ON_TEMPERATURE", 0.3)
REPETITION_PENALTY = _env_float("REPETITION_PENALTY", 1.1)
NO_REPEAT_NGRAM_SIZE = _env_int("NO_REPEAT_NGRAM_SIZE", 3)

# VAD parameters
VAD_FILTER = _env_bool("VAD_FILTER", True)
VAD_FILTER_THRESHOLD = _env_float("VAD_FILTER_THRESHOLD", 0.5)
VAD_MIN_SILENCE_DURATION_MS = _env_int("VAD_MIN_SILENCE_DURATION_MS", 160)
VAD_MAX_SPEECH_DURATION_S = _env_float("VAD_MAX_SPEECH_DURATION_S", 15.0)  # max segment length before forced split

# Temperature fallback chain
USE_TEMPERATURE_FALLBACK = _env_bool("USE_TEMPERATURE_FALLBACK", False)
TEMPERATURE_FALLBACK_CHAIN = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

WHISPER_COMPAT_MODEL = "whisper-1"
NEMOTRON_PUBLIC_MODEL = "nemotron-3.5-asr-streaming-0.6b"
NEMOTRON_PROMPT_MODULE = "nemo.collections.asr.models.rnnt_bpe_models_prompt"
NEMOTRON_PROMPT_CLASS = "EncDecRNNTBPEModelWithPrompt"
NEMOTRON_ALLOWED_MISSING_PREFIXES = ("ctc_decoder.",)
NEMOTRON_PROMPT_FIELD = "lang"
NEMOTRON_LANGUAGE_MAP = {
    "de": "de-DE",
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "it": "it-IT",
    "nl": "nl-NL",
    "pl": "pl-PL",
    "pt": "pt-PT",
    "ru": "ru-RU",
    "uk": "uk-UA",
}


def _normalize_backend_name(raw: Optional[str]) -> str:
    backend = (raw or "whisper").strip().lower()
    if backend not in ("whisper", "nemotron"):
        logger.warning("Unknown TRANSCRIPTION_BACKEND=%r, defaulting to whisper", raw)
        return "whisper"
    return backend


def _normalize_nemotron_target_lang(raw: Optional[str]) -> str:
    if raw is None:
        return NEMOTRON_TARGET_LANG_DEFAULT
    value = raw.strip()
    if not value:
        return NEMOTRON_TARGET_LANG_DEFAULT
    lowered = value.lower()
    if lowered == "auto":
        return "auto"
    return NEMOTRON_LANGUAGE_MAP.get(lowered, value)


def _extract_response_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if hasattr(payload, "text"):
        return str(payload.text).strip()
    if isinstance(payload, dict):
        if "text" in payload:
            return str(payload["text"]).strip()
        if "pred_text" in payload:
            return str(payload["pred_text"]).strip()
    return str(payload).strip()


def _extract_word_timestamps(payload: Any) -> List[Dict[str, Any]]:
    timestamp_data = getattr(payload, "timestamp", None)
    if timestamp_data is None and isinstance(payload, dict):
        timestamp_data = payload.get("timestamp")
    if not isinstance(timestamp_data, dict):
        return []
    words = timestamp_data.get("word")
    if not isinstance(words, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in words:
        if not isinstance(item, dict):
            continue
        word = item.get("word")
        start = item.get("start")
        end = item.get("end")
        if word is None or start is None or end is None:
            continue
        out.append(
            {
                "word": str(word),
                "start": float(start),
                "end": float(end),
                "probability": float(item.get("probability", 1.0)),
            }
        )
    return out


def _build_nemotron_audio_entry(audio_path: str, duration: float, target_lang: str) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "audio_filepath": audio_path,
        "duration": duration if duration > 0 else 100000,
        "text": "",
        # NeMo's prompt dataset currently reads cut.supervisions[0].language directly.
        "lang": target_lang,
        "language": target_lang,
    }
    return entry


def _nemotron_restore_needs_prompt_compat(exc: Exception) -> bool:
    message = str(exc)
    return (
        NEMOTRON_PROMPT_MODULE in message
        or "Can't instantiate abstract class ASRModel" in message
    )


def _nemotron_compat_mismatches(result: Any) -> Tuple[List[str], List[str]]:
    missing_keys = list(getattr(result, "missing_keys", []) or [])
    unexpected_keys = list(getattr(result, "unexpected_keys", []) or [])
    bad_missing = [
        key for key in missing_keys
        if not key.startswith(NEMOTRON_ALLOWED_MISSING_PREFIXES)
    ]
    return bad_missing, unexpected_keys


def _install_nemotron_prompt_compat() -> type:
    module_name = NEMOTRON_PROMPT_MODULE
    existing = sys.modules.get(module_name)
    if existing is not None and hasattr(existing, NEMOTRON_PROMPT_CLASS):
        return getattr(existing, NEMOTRON_PROMPT_CLASS)

    from torch.nn.modules.module import _IncompatibleKeys
    from nemo.collections.asr.models.hybrid_rnnt_ctc_bpe_models_prompt import (
        EncDecHybridRNNTCTCBPEModelWithPrompt,
    )

    class EncDecRNNTBPEModelWithPrompt(EncDecHybridRNNTCTCBPEModelWithPrompt):
        def load_state_dict(self, state_dict, strict: bool = True, assign: bool = False):
            result = super().load_state_dict(state_dict, strict=False, assign=assign)
            bad_missing, bad_unexpected = _nemotron_compat_mismatches(result)
            if strict and (bad_missing or bad_unexpected):
                raise RuntimeError(
                    "Nemotron compatibility shim saw unexpected state_dict mismatch: "
                    f"missing={bad_missing} unexpected={bad_unexpected}"
                )
            return _IncompatibleKeys(bad_missing, bad_unexpected)

    EncDecRNNTBPEModelWithPrompt.__module__ = module_name
    module = types.ModuleType(module_name)
    module.EncDecRNNTBPEModelWithPrompt = EncDecRNNTBPEModelWithPrompt
    sys.modules[module_name] = module
    return EncDecRNNTBPEModelWithPrompt


def _load_nemotron_model(nemo_asr, model_name: str):
    try:
        return nemo_asr.models.ASRModel.from_pretrained(model_name=model_name)
    except Exception as exc:
        if not _nemotron_restore_needs_prompt_compat(exc):
            raise
        logger.info(
            "Applying Nemotron NeMo compatibility shim for %s after restore failure: %s",
            model_name,
            exc,
        )
        _install_nemotron_prompt_compat()
        return nemo_asr.models.ASRModel.from_pretrained(model_name=model_name)


class BaseTranscriptionBackend:
    backend_name: str

    def startup_details(self) -> Dict[str, Any]:
        raise NotImplementedError

    def accepted_models(self) -> Set[str]:
        raise NotImplementedError

    async def transcribe(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        requested_model: str,
        language: Optional[str],
        prompt: Optional[str],
        task: str,
        want_word_timestamps: bool,
        req_max_speech: float,
        req_min_silence: int,
        requested_temp: float,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class WhisperBackend(BaseTranscriptionBackend):
    backend_name = "whisper"

    def __init__(self) -> None:
        model_kwargs = {
            "model_size_or_path": MODEL_SIZE,
            "device": DEVICE,
            "compute_type": COMPUTE_TYPE,
            "download_root": "/app/models",
        }
        if DEVICE == "cpu" and CPU_THREADS > 0:
            model_kwargs["cpu_threads"] = CPU_THREADS
            logger.info("Worker %s using %s CPU threads", WORKER_ID, CPU_THREADS)
        self.model = WhisperModel(**model_kwargs)

    def startup_details(self) -> Dict[str, Any]:
        return {
            "backend": self.backend_name,
            "backend_model": MODEL_SIZE,
            "device": DEVICE,
            "compute_type": COMPUTE_TYPE,
        }

    def accepted_models(self) -> Set[str]:
        return {WHISPER_COMPAT_MODEL, MODEL_SIZE}

    async def transcribe(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        requested_model: str,
        language: Optional[str],
        prompt: Optional[str],
        task: str,
        want_word_timestamps: bool,
        req_max_speech: float,
        req_min_silence: int,
        requested_temp: float,
    ) -> Dict[str, Any]:
        temps = TEMPERATURE_FALLBACK_CHAIN if USE_TEMPERATURE_FALLBACK else [requested_temp]

        best: Optional[Tuple[str, str, float, float, List[Dict[str, Any]]]] = None
        last_info = None
        last_segments: List[Dict[str, Any]] = []

        for t in temps:
            def _transcribe_sync():
                return self.model.transcribe(
                    audio_array,
                    language=language,
                    task=task,
                    initial_prompt=prompt,
                    temperature=t,
                    beam_size=BEAM_SIZE,
                    best_of=BEST_OF,
                    compression_ratio_threshold=COMPRESSION_RATIO_THRESHOLD,
                    log_prob_threshold=LOG_PROB_THRESHOLD,
                    no_speech_threshold=NO_SPEECH_THRESHOLD,
                    condition_on_previous_text=CONDITION_ON_PREVIOUS_TEXT,
                    prompt_reset_on_temperature=PROMPT_RESET_ON_TEMPERATURE,
                    repetition_penalty=REPETITION_PENALTY,
                    no_repeat_ngram_size=NO_REPEAT_NGRAM_SIZE,
                    vad_filter=VAD_FILTER,
                    vad_parameters={
                        "threshold": VAD_FILTER_THRESHOLD,
                        "min_silence_duration_ms": req_min_silence,
                        "max_speech_duration_s": req_max_speech,
                    },
                    word_timestamps=want_word_timestamps,
                )

            segments_list, info = await asyncio.get_event_loop().run_in_executor(
                transcription_executor, _transcribe_sync
            )
            last_info = info

            segments: List[Dict[str, Any]] = []
            for idx, segment in enumerate(segments_list):
                seg_dict: Dict[str, Any] = {
                    "id": idx,
                    "seek": 0,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "tokens": [],
                    "temperature": t,
                    "avg_logprob": segment.avg_logprob,
                    "compression_ratio": segment.compression_ratio,
                    "no_speech_prob": segment.no_speech_prob,
                    "audio_start": segment.start,
                    "audio_end": segment.end,
                }
                if want_word_timestamps and hasattr(segment, "words") and segment.words:
                    seg_dict["words"] = [
                        {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                        for w in segment.words
                    ]
                segments.append(seg_dict)
            last_segments = segments

            if _looks_like_silence(segments):
                best = ("", info.language, getattr(info, "language_probability", 0.0), 0.0, [])
                logger.info("Worker %s detected silence (temp=%s)", WORKER_ID, t)
                break

            if not _looks_like_hallucination(segments):
                full_text = " ".join([s["text"].strip() for s in segments]).strip()
                duration = segments[-1]["end"] if segments else 0.0
                best = (full_text, info.language, getattr(info, "language_probability", 0.0), duration, segments)
                logger.info("Worker %s accepted whisper transcription (temp=%s)", WORKER_ID, t)
                break

            logger.info("Worker %s rejected whisper transcription as hallucination/low-confidence (temp=%s)", WORKER_ID, t)

        if best is None:
            info = last_info
            segments = last_segments
            full_text = " ".join([s["text"].strip() for s in segments]).strip()
            duration = segments[-1]["end"] if segments else 0.0
            lang_prob = getattr(info, "language_probability", 0.0) if info else 0.0
            best = (full_text, info.language if info else (language or "unknown"), lang_prob, duration, segments)

        full_text, detected_language, detected_language_probability, duration, segments = best
        return {
            "text": full_text,
            "language": detected_language,
            "language_probability": detected_language_probability,
            "duration": duration,
            "segments": segments,
        }

class NemotronBackend(BaseTranscriptionBackend):
    backend_name = "nemotron"

    def __init__(self) -> None:
        try:
            import nemo.collections.asr as nemo_asr
        except ImportError as exc:
            raise RuntimeError(
                "Nemotron backend requires NeMo ASR runtime. Install nemo_toolkit[asr] to use TRANSCRIPTION_BACKEND=nemotron."
            ) from exc
        self.nemo_asr = nemo_asr
        self.model = _load_nemotron_model(nemo_asr, NEMOTRON_MODEL_NAME)

    def startup_details(self) -> Dict[str, Any]:
        return {
            "backend": self.backend_name,
            "backend_model": NEMOTRON_MODEL_NAME,
            "device": DEVICE,
        }

    def accepted_models(self) -> Set[str]:
        return {WHISPER_COMPAT_MODEL, NEMOTRON_PUBLIC_MODEL, NEMOTRON_MODEL_NAME}

    async def transcribe(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        requested_model: str,
        language: Optional[str],
        prompt: Optional[str],
        task: str,
        want_word_timestamps: bool,
        req_max_speech: float,
        req_min_silence: int,
        requested_temp: float,
    ) -> Dict[str, Any]:
        target_lang = _normalize_nemotron_target_lang(language)
        duration = float(len(audio_array) / sample_rate) if sample_rate > 0 else 0.0

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            wav_path = tmp_wav.name
        try:
            sf.write(wav_path, audio_array, sample_rate)

            def _transcribe_sync():
                kwargs: Dict[str, Any] = {
                    "audio": [_build_nemotron_audio_entry(wav_path, duration, target_lang)],
                    "batch_size": 1,
                }
                if target_lang:
                    kwargs["target_lang"] = target_lang
                    kwargs["prompt_field"] = NEMOTRON_PROMPT_FIELD
                if want_word_timestamps:
                    kwargs["timestamps"] = True
                return self.model.transcribe(**kwargs)

            hypotheses = await asyncio.get_event_loop().run_in_executor(
                transcription_executor, _transcribe_sync
            )
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

        if not isinstance(hypotheses, list) or not hypotheses:
            raise RuntimeError("Nemotron backend returned no hypotheses")

        first = hypotheses[0]
        full_text = _extract_response_text(first)
        words = _extract_word_timestamps(first) if want_word_timestamps else []
        if words:
            seg_start = words[0]["start"]
            seg_end = words[-1]["end"]
        else:
            seg_start = 0.0
            seg_end = duration

        segment: Dict[str, Any] = {
            "id": 0,
            "seek": 0,
            "start": seg_start,
            "end": seg_end,
            "text": full_text,
            "tokens": [],
            "temperature": 0.0,
            "avg_logprob": 0.0,
            "compression_ratio": 0.0,
            "no_speech_prob": 0.0,
            "audio_start": seg_start,
            "audio_end": seg_end,
        }
        if words:
            segment["words"] = words

        detected_language = target_lang if target_lang != "auto" else "auto"
        return {
            "text": full_text,
            "language": detected_language,
            "language_probability": 1.0 if target_lang != "auto" else 0.0,
            "duration": duration,
            "segments": [segment] if full_text or words else [],
        }


def _build_backend() -> BaseTranscriptionBackend:
    backend = _normalize_backend_name(TRANSCRIPTION_BACKEND)
    if backend == "nemotron":
        return NemotronBackend()
    return WhisperBackend()


def _validate_requested_model(backend: BaseTranscriptionBackend, requested_model: str) -> None:
    accepted = backend.accepted_models()
    if requested_model not in accepted:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported model '{requested_model}' for backend '{backend.backend_name}'. "
                f"Accepted values: {sorted(accepted)}"
            ),
        )

def _looks_like_silence(segments: List[Dict[str, Any]]) -> bool:
    """Heuristic: treat as silence if all segments look like no-speech."""
    if not segments:
        return True
    for s in segments:
        if not (
            float(s.get("no_speech_prob", 0.0)) > NO_SPEECH_THRESHOLD
            and float(s.get("avg_logprob", 0.0)) < LOG_PROB_THRESHOLD
        ):
            return False
    return True

def _looks_like_hallucination(segments: List[Dict[str, Any]]) -> bool:
    """Heuristic: reject segments that look like hallucinations / low-confidence."""
    for s in segments:
        if float(s.get("compression_ratio", 0.0)) > COMPRESSION_RATIO_THRESHOLD:
            return True
        if float(s.get("avg_logprob", 0.0)) < LOG_PROB_THRESHOLD:
            return True
    return False

# API Token Authentication
API_TOKEN = os.getenv("API_TOKEN", "").strip()
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_token(
    request: Request,
    api_key: Optional[str] = Depends(API_KEY_HEADER)
) -> bool:
    """Verify API token - supports both X-API-Key and Authorization Bearer"""
    if not API_TOKEN:
        # If no token configured, allow all requests (backward compatibility)
        logger.warning("API_TOKEN not configured - allowing all requests")
        return True
    
    # Try X-API-Key header first
    if api_key and api_key == API_TOKEN:
        return True
    
    # Try Authorization Bearer header (for compatibility)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        if token == API_TOKEN:
            return True
    
    logger.warning(f"Invalid or missing API token - X-API-Key: {api_key is not None}, Authorization: {bool(auth_header)}")
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API token"
    )

_VEXA_ENV = os.getenv("VEXA_ENV", "development")
_PUBLIC_DOCS = _VEXA_ENV != "production"
app = FastAPI(
    title="Vexa Transcription Service",
    description="OpenAI Whisper API compatible transcription service",
    version="1.0.0",
    docs_url="/docs" if _PUBLIC_DOCS else None,
    redoc_url="/redoc" if _PUBLIC_DOCS else None,
    openapi_url="/openapi.json" if _PUBLIC_DOCS else None,
)

# Global backend instance
transcription_backend: Optional[BaseTranscriptionBackend] = None

# Load management: Global concurrency limit and bounded queue
# These settings control how many transcription requests can be processed concurrently.
# CTranslate2 serializes CUDA ops, so concurrent requests queue on the GPU.
# RTX 4090 benchmarks (2026-03-08): 20 concurrent handles fine, latency ~3s worst case.
# Set high enough to avoid artificial bottlenecks, low enough to bound queue latency.
# MAX_ACTIVE_REQUESTS is the preferred name; MAX_CONCURRENT_TRANSCRIPTIONS is kept for compatibility.
MAX_CONCURRENT_TRANSCRIPTIONS = _env_int("MAX_ACTIVE_REQUESTS", _env_int("MAX_CONCURRENT_TRANSCRIPTIONS", 20))
MAX_QUEUE_SIZE = _env_int("MAX_QUEUE_SIZE", 10)  # Max requests waiting in queue

# Backpressure strategy:
# - If FAIL_FAST_WHEN_BUSY=true, we do NOT wait in a queue; we immediately return 503 so callers
#   callers can keep buffering and submit a newer/larger window later.
FAIL_FAST_WHEN_BUSY = _env_bool("FAIL_FAST_WHEN_BUSY", True)
BUSY_RETRY_AFTER_S = _env_int("BUSY_RETRY_AFTER_S", 1)
REALTIME_RESERVED_SLOTS = _env_int("REALTIME_RESERVED_SLOTS", 1)

# Semaphore to limit concurrent transcriptions (protects GPU/CPU from overload)
transcription_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)

# Thread pool for running blocking transcription calls
transcription_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TRANSCRIPTIONS)

# Queue to track waiting requests (for 429/503 responses when full)
# We use a simple counter since FastAPI doesn't have a built-in queue
waiting_requests = 0
waiting_requests_lock = asyncio.Lock()

# Active in-flight counters per tier for admission decisions.
active_realtime_requests = 0
active_deferred_requests = 0
active_requests_lock = asyncio.Lock()


def _normalize_transcription_tier(raw: Optional[str]) -> str:
    tier = (raw or "realtime").strip().lower()
    return tier if tier in ("realtime", "deferred") else "realtime"


def _deferred_capacity_available(active_rt: int, active_df: int) -> bool:
    deferred_limit = max(0, MAX_CONCURRENT_TRANSCRIPTIONS - REALTIME_RESERVED_SLOTS)
    total_active = active_rt + active_df
    return deferred_limit > 0 and active_df < deferred_limit and total_active < MAX_CONCURRENT_TRANSCRIPTIONS


@app.on_event("startup")
async def startup_event():
    """Initialize the configured transcription backend on startup."""
    global transcription_backend
    logger.info(f"Worker {WORKER_ID} starting up...")
    logger.info(
        "Backend startup - backend=%s device=%s whisper_model=%s nemotron_model=%s compute=%s",
        _normalize_backend_name(TRANSCRIPTION_BACKEND),
        DEVICE,
        MODEL_SIZE,
        NEMOTRON_MODEL_NAME,
        COMPUTE_TYPE,
    )
    logger.info(
        "Quality params - "
        f"beam_size={BEAM_SIZE}, best_of={BEST_OF}, "
        f"cond_prev_text={CONDITION_ON_PREVIOUS_TEXT}, "
        f"compression_ratio_threshold={COMPRESSION_RATIO_THRESHOLD}, "
        f"log_prob_threshold={LOG_PROB_THRESHOLD}, "
        f"no_speech_threshold={NO_SPEECH_THRESHOLD}, "
        f"vad_filter={VAD_FILTER}, "
        f"repetition_penalty={REPETITION_PENALTY}, "
        f"no_repeat_ngram_size={NO_REPEAT_NGRAM_SIZE}"
    )
    
    try:
        transcription_backend = _build_backend()
        details = transcription_backend.startup_details()
        logger.info("Worker %s ready - backend loaded successfully: %s", WORKER_ID, json.dumps(details, sort_keys=True))
    except Exception as e:
        logger.error(f"Failed to load transcription backend: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer"""
    backend = transcription_backend
    backend_details = backend.startup_details() if backend is not None else {}
    health_status = {
        "status": "healthy" if backend is not None else "unhealthy",
        "worker_id": WORKER_ID,
        "timestamp": datetime.utcnow().isoformat(),
        "model": backend_details.get("backend_model", MODEL_SIZE),
        "backend": backend_details.get("backend", _normalize_backend_name(TRANSCRIPTION_BACKEND)),
        "device": DEVICE,
        "gpu_available": DEVICE == "cuda",
    }
    
    if DEVICE == "cuda":
        # CTranslate2 (via faster-whisper) handles GPU automatically
        health_status["compute_type"] = COMPUTE_TYPE
    
    if backend is None:
        return JSONResponse(content=health_status, status_code=503)
    
    return health_status


@app.post("/v1/audio/transcriptions")
async def transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
    requested_model: str = Form(..., alias="model"),
    temperature: str = Form("0"),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: str = Form("verbose_json"),
    timestamp_granularities: str = Form("segment"),
    max_speech_duration_s: Optional[str] = Form(None),
    min_silence_duration_ms: Optional[str] = Form(None),
    transcription_tier_form: Optional[str] = Form(None, alias="transcription_tier"),
    task: str = Form("transcribe"),
    _: bool = Depends(verify_api_token)
):
    """
    OpenAI Whisper API compatible transcription endpoint
    
    Required by Vexa's RemoteTranscriber:
    - Accepts multipart/form-data with audio file
    - Returns verbose_json format with segments
    - Includes timing, language, and segment details
    
    Load management:
    - Limits concurrent transcriptions to prevent GPU/CPU overload
    - Returns 429/503 when queue is full to signal backpressure
    """
    if not requested_model:
        raise HTTPException(status_code=400, detail="Model parameter is required")
    backend = transcription_backend
    if backend is None:
        raise HTTPException(status_code=503, detail="Transcription backend not initialized")
    _validate_requested_model(backend, requested_model)
    global waiting_requests, active_realtime_requests, active_deferred_requests

    tier_from_header = request.headers.get("X-Transcription-Tier")
    transcription_tier = _normalize_transcription_tier(transcription_tier_form or tier_from_header)

    semaphore_acquired = False
    waiting_counted = False
    active_counted = False
    
    # Load management: Check queue size before accepting request
    async with waiting_requests_lock:
        async with active_requests_lock:
            current_active_rt = active_realtime_requests
            current_active_df = active_deferred_requests

        if transcription_tier == "deferred":
            if not _deferred_capacity_available(current_active_rt, current_active_df):
                raise HTTPException(
                    status_code=503,
                    detail="Deferred tier is out of capacity. Please retry later.",
                    headers={"Retry-After": str(max(1, BUSY_RETRY_AFTER_S))},
                )
        # Fail-fast mode: don't accept work we can't start immediately.
        # This avoids "processing the first chunk" (small/old) and lets upstream buffer/coalesce.
        if FAIL_FAST_WHEN_BUSY and (transcription_semaphore.locked() or waiting_requests > 0):
            raise HTTPException(
                status_code=503,
                detail="Service busy. Please retry later.",
                headers={"Retry-After": str(max(1, BUSY_RETRY_AFTER_S))},
            )
        if waiting_requests >= MAX_QUEUE_SIZE:
            logger.warning(
                f"Worker {WORKER_ID} queue full ({waiting_requests}/{MAX_QUEUE_SIZE}). "
                f"Rejecting request with 503."
            )
            raise HTTPException(
                status_code=503,
                detail="Service temporarily overloaded. Please retry later.",
                headers={"Retry-After": str(max(1, BUSY_RETRY_AFTER_S))}
            )
        waiting_requests += 1
        waiting_counted = True
    
    try:
        # Acquire semaphore (blocks if MAX_CONCURRENT_TRANSCRIPTIONS is reached)
        await transcription_semaphore.acquire()
        semaphore_acquired = True
        
        async with waiting_requests_lock:
            if waiting_counted:
                waiting_requests -= 1
                waiting_counted = False

        async with active_requests_lock:
            if transcription_tier == "deferred":
                active_deferred_requests += 1
            else:
                active_realtime_requests += 1
            active_counted = True
        
        start_time = time.time()
        logger.info(
            f"Worker {WORKER_ID} received transcription request - "
            f"tier={transcription_tier}, filename: {file.filename}, content_type: {file.content_type}"
        )
        # Read audio file
        audio_bytes = await file.read()
        logger.info(f"Worker {WORKER_ID} read {len(audio_bytes)} bytes of audio data")
        
        # Convert to format suitable for faster-whisper
        # Use soundfile to properly decode audio formats (WAV, MP3, etc.)
        # Falls back to ffmpeg subprocess for formats soundfile can't handle (webm, opus, etc.)
        audio_io = io.BytesIO(audio_bytes)
        try:
            audio_array, sample_rate = sf.read(audio_io, dtype=np.float32)
            logger.info(f"Worker {WORKER_ID} decoded audio - shape: {audio_array.shape}, sample_rate: {sample_rate}")
        except Exception as e:
            logger.warning(f"Worker {WORKER_ID} soundfile failed ({e}), trying ffmpeg fallback")
            try:
                import subprocess, tempfile
                with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp_in:
                    tmp_in.write(audio_bytes)
                    tmp_in_path = tmp_in.name
                tmp_out_path = tmp_in_path.replace('.webm', '.wav')
                result = subprocess.run(
                    ['ffmpeg', '-y', '-i', tmp_in_path, '-ar', '16000', '-ac', '1', '-f', 'wav', tmp_out_path],
                    capture_output=True, timeout=120
                )
                if result.returncode != 0:
                    raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:500]}")
                audio_array, sample_rate = sf.read(tmp_out_path, dtype=np.float32)
                logger.info(f"Worker {WORKER_ID} decoded via ffmpeg - shape: {audio_array.shape}, sample_rate: {sample_rate}")
                import os
                os.unlink(tmp_in_path)
                os.unlink(tmp_out_path)
            except FileNotFoundError:
                logger.error(f"Worker {WORKER_ID} ffmpeg not installed - cannot decode non-WAV formats")
                raise HTTPException(status_code=400, detail=f"Failed to decode audio file: {e}. Install ffmpeg for webm/opus support.")
            except Exception as e2:
                logger.error(f"Worker {WORKER_ID} ffmpeg fallback also failed: {e2}")
                raise HTTPException(status_code=400, detail=f"Failed to decode audio file: {e2}")
        
        # Ensure mono audio (convert stereo to mono if needed)
        if len(audio_array.shape) > 1:
            audio_array = np.mean(audio_array, axis=1)
            logger.info(f"Worker {WORKER_ID} converted to mono - shape: {audio_array.shape}")
        
        # Ensure audio is contiguous array
        audio_array = np.ascontiguousarray(audio_array, dtype=np.float32)
        
        requested_temp = float(temperature) if temperature else 0.0
        want_word_timestamps = "word" in timestamp_granularities

        # Per-request VAD overrides (with defaults from env)
        req_max_speech = float(max_speech_duration_s) if max_speech_duration_s else VAD_MAX_SPEECH_DURATION_S
        req_min_silence = int(min_silence_duration_ms) if min_silence_duration_ms else VAD_MIN_SILENCE_DURATION_MS

        logger.info(
            f"Worker {WORKER_ID} starting transcription - backend={backend.backend_name}, requested_model={requested_model}, "
            f"requested_temp: {requested_temp}, language: {language}, task: {task}, vad_filter: {VAD_FILTER}, "
            f"max_speech={req_max_speech}s, min_silence={req_min_silence}ms"
        )
        response = await backend.transcribe(
            audio_array=audio_array,
            sample_rate=sample_rate,
            requested_model=requested_model,
            language=language,
            prompt=prompt,
            task=task,
            want_word_timestamps=want_word_timestamps,
            req_max_speech=req_max_speech,
            req_min_silence=req_min_silence,
            requested_temp=requested_temp,
        )
        logger.info(
            "Worker %s transcription completed - backend=%s language=%s language_probability=%s",
            WORKER_ID,
            backend.backend_name,
            response.get("language"),
            response.get("language_probability"),
        )
        
        processing_time = time.time() - start_time
        logger.info(
            f"Worker {WORKER_ID} completed in {processing_time:.2f}s - "
            f"Duration: {float(response.get('duration', 0.0)):.2f}s, "
            f"Segments: {len(response.get('segments', []))}, Language: {response.get('language')}"
        )
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions (429, 503, etc.)
        raise
    except Exception as e:
        logger.error(f"Worker {WORKER_ID} transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Keep counters and semaphore balanced even on early failures.
        if active_counted:
            async with active_requests_lock:
                if transcription_tier == "deferred":
                    active_deferred_requests = max(0, active_deferred_requests - 1)
                else:
                    active_realtime_requests = max(0, active_realtime_requests - 1)
            active_counted = False

        if waiting_counted:
            async with waiting_requests_lock:
                waiting_requests = max(0, waiting_requests - 1)
            waiting_counted = False

        if semaphore_acquired:
            transcription_semaphore.release()


@app.get("/")
async def root():
    """Root endpoint with service info"""
    backend = transcription_backend
    backend_name = backend.backend_name if backend is not None else _normalize_backend_name(TRANSCRIPTION_BACKEND)
    backend_model = MODEL_SIZE
    if backend is not None:
        backend_model = backend.startup_details().get("backend_model", MODEL_SIZE)
    return {
        "service": "Vexa Transcription Service",
        "worker_id": WORKER_ID,
        "model": backend_model,
        "backend": backend_name,
        "device": DEVICE,
        "status": "ready" if backend is not None else "initializing",
        "endpoints": {
            "transcribe": "/v1/audio/transcriptions",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
