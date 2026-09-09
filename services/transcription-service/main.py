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
import re
import tempfile
import threading
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
from huggingface_hub import hf_hub_download
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
NEMOTRON_ATT_CONTEXT_SIZE_RAW = os.getenv("NEMOTRON_ATT_CONTEXT_SIZE", "56,6").strip() or "56,6"
NEMOTRON_BOOSTING_PHRASES_FILE = os.getenv("NEMOTRON_BOOSTING_PHRASES_FILE", "").strip()
WHISPER_HOTWORDS_FILE = os.getenv("WHISPER_HOTWORDS_FILE", "").strip()

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

NEMOTRON_BOOSTING_ALPHA = _env_float("NEMOTRON_BOOSTING_ALPHA", 1.0)
NEMOTRON_BOOSTING_CONTEXT_SCORE = _env_float("NEMOTRON_BOOSTING_CONTEXT_SCORE", 1.0)
NEMOTRON_BOOSTING_DEPTH_SCALING = _env_float("NEMOTRON_BOOSTING_DEPTH_SCALING", 2.0)

# Transcription defaults (can be overridden via env)
BEAM_SIZE = _env_int("BEAM_SIZE", 5)
BEST_OF = _env_int("BEST_OF", 5)
COMPRESSION_RATIO_THRESHOLD = _env_float("COMPRESSION_RATIO_THRESHOLD", 1.8)
LOG_PROB_THRESHOLD = _env_float("LOG_PROB_THRESHOLD", -1.0)
NO_SPEECH_THRESHOLD = _env_float("NO_SPEECH_THRESHOLD", 0.6)
# Nemotron uses compression-ratio + phrase-repetition for quality (no logprob
# gate — RNN-T score scale is fundamentally different from Whisper CTC).
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
NEMOTRON_MODEL_FILENAME = "nemotron-3.5-asr-streaming-0.6b.nemo"
# Nemotron-3.5-asr supports 40 BCP-47 locales (19 transcription-ready +
# 13 broad-coverage + 8 adaptation-ready). Source: HuggingFace model card
# https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b
# Passing a 2-letter code that is NOT in this map means the model receives an
# unrecognized prompt and falls back to ambiguous decoding (root cause of the
# Croatian-as-Cyrillic garbage we saw in meeting 317).
NEMOTRON_LANGUAGE_MAP = {
    # Transcription-ready (default to most common region per 2-letter code)
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "it": "it-IT",
    "pt": "pt-PT",
    "nl": "nl-NL",
    "de": "de-DE",
    "tr": "tr-TR",
    "ru": "ru-RU",
    "ar": "ar-AR",
    "hi": "hi-IN",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "vi": "vi-VN",
    "uk": "uk-UA",
    # Broad-coverage
    "pl": "pl-PL",
    "sv": "sv-SE",
    "cs": "cs-CZ",
    "no": "nb-NO",  # Norwegian Bokmål as default for bare 'no'
    "nb": "nb-NO",
    "da": "da-DK",
    "bg": "bg-BG",
    "fi": "fi-FI",
    "hr": "hr-HR",
    "sk": "sk-SK",
    "zh": "zh-CN",
    "hu": "hu-HU",
    "ro": "ro-RO",
    "et": "et-EE",
    # Adaptation-ready — recognized by the tokenizer; quality may need
    # fine-tuning but the prompt still constrains decoding.
    "el": "el-GR",
    "lt": "lt-LT",
    "lv": "lv-LV",
    "mt": "mt-MT",
    "sl": "sl-SI",
    "he": "he-IL",
    "th": "th-TH",
    "nn": "nn-NO",
}

# Full BCP-47 codes the model accepts (used for passthrough validation when
# a client sends e.g. "en-GB" or "pt-BR" directly).
NEMOTRON_SUPPORTED_BCP47 = frozenset({
    # Transcription-ready (19)
    "en-US", "en-GB", "es-US", "es-ES", "fr-FR", "fr-CA", "it-IT",
    "pt-BR", "pt-PT", "nl-NL", "de-DE", "tr-TR", "ru-RU", "ar-AR",
    "hi-IN", "ja-JP", "ko-KR", "vi-VN", "uk-UA",
    # Broad-coverage (13)
    "pl-PL", "sv-SE", "cs-CZ", "nb-NO", "da-DK", "bg-BG", "fi-FI",
    "hr-HR", "sk-SK", "zh-CN", "hu-HU", "ro-RO", "et-EE",
    # Adaptation-ready (8)
    "el-GR", "lt-LT", "lv-LV", "mt-MT", "sl-SI", "he-IL", "th-TH", "nn-NO",
})


def _normalize_backend_name(raw: Optional[str]) -> str:
    backend = (raw or "whisper").strip().lower()
    if backend not in ("whisper", "nemotron"):
        logger.warning("Unknown TRANSCRIPTION_BACKEND=%r, defaulting to whisper", raw)
        return "whisper"
    return backend


def _normalize_nemotron_target_lang(raw: Optional[str]) -> str:
    """Map a client-supplied language code to a Nemotron-accepted BCP-47 code.

    Accepts: None/empty → default, "auto" → "auto", 2-letter ISO 639-1 via
    NEMOTRON_LANGUAGE_MAP (e.g. "hr" → "hr-HR"), or full BCP-47 codes from
    NEMOTRON_SUPPORTED_BCP47 (e.g. "en-GB", "pt-BR") as passthrough with
    canonical "ll-RR" casing.

    Unknown codes log a warning and fall back to NEMOTRON_TARGET_LANG_DEFAULT
    rather than passing garbage to the model.
    """
    if raw is None:
        return NEMOTRON_TARGET_LANG_DEFAULT
    value = raw.strip()
    if not value:
        return NEMOTRON_TARGET_LANG_DEFAULT
    if value.lower() == "auto":
        return "auto"
    # BCP-47 passthrough — canonicalise to ll-RR casing then verify.
    if "-" in value:
        parts = value.split("-", 1)
        canonical = f"{parts[0].lower()}-{parts[1].upper()}"
        if canonical in NEMOTRON_SUPPORTED_BCP47:
            return canonical
    # 2-letter (or 3-letter) ISO code lookup.
    mapped = NEMOTRON_LANGUAGE_MAP.get(value.lower())
    if mapped is not None:
        return mapped
    logger.warning(
        "Unsupported Nemotron language %r, falling back to %r",
        raw, NEMOTRON_TARGET_LANG_DEFAULT,
    )
    return NEMOTRON_TARGET_LANG_DEFAULT


def _parse_nemotron_att_context_size(raw: Optional[str]) -> List[int]:
    value = (raw or "56,6").strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    try:
        parts = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError:
        logger.warning("Invalid NEMOTRON_ATT_CONTEXT_SIZE=%r, using [56, 6]", raw)
        return [56, 6]
    if len(parts) != 2 or parts[0] != 56 or parts[1] not in {0, 1, 3, 6, 13}:
        logger.warning("Invalid NEMOTRON_ATT_CONTEXT_SIZE=%r, using [56, 6]", raw)
        return [56, 6]
    return parts


def _nemotron_chunk_size_ms(att_context_size: List[int]) -> int:
    return (att_context_size[1] + 1) * 80


def _build_nemotron_manifest_entry(audio_filepath: str, duration: float, target_lang: str) -> Dict[str, Any]:
    return {
        "audio_filepath": audio_filepath,
        "duration": duration,
        "text": "",
        "lang": target_lang,
        "language": target_lang,
        "target_lang": target_lang,
    }


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


def _clean_nemotron_text(text: str) -> str:
    cleaned = re.sub(r"<[A-Za-z]{2,3}(?:-[A-Za-z]{2,3})?>", " ", text)
    return " ".join(cleaned.split()).strip()


def _normalize_language_code(code: str) -> Optional[str]:
    """Normalize language code to bare ISO 639-1 (2-letter).

    Strips BCP 47 region subtags ('en-US' -> 'en', 'zh-CN' -> 'zh').
    Returns None for 'auto' (language was not resolved to a specific code).
    """
    if not code or code == "auto":
        return None
    return code.split('-')[0].split('_')[0].lower()


def _extract_nemotron_detected_language(text: str, target_lang: str) -> Optional[str]:
    if target_lang != "auto":
        return _normalize_language_code(target_lang)
    match = re.search(r"<([A-Za-z]{2,3}(?:-[A-Za-z]{2,3})?)>", text)
    if match:
        return _normalize_language_code(match.group(1))
    return None


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


def _text_compression_ratio(text: str) -> float:
    """Classic Whisper-style repetition heuristic: bytes / zlib(bytes)."""
    if not text:
        return 0.0
    import zlib
    raw = text.encode("utf-8")
    if not raw:
        return 0.0
    compressed = zlib.compress(raw)
    return len(raw) / max(len(compressed), 1)


def _nemotron_no_speech_prob(text: str, duration: float) -> float:
    """Cheap proxy: empty text on real audio = silence/no-speech."""
    if duration <= 0.0:
        return 0.0
    stripped = (text or "").strip()
    if not stripped:
        return 1.0
    if duration >= 2.0 and len(stripped) < 3:
        return 0.8
    return 0.0


def _has_phrase_repetition(text: str) -> bool:
    """Mirror of vexa-bot's hallucination-filter phrase-loop detector."""
    words = (text or "").split()
    if len(words) < 9:
        return False
    for n in range(3, 7):
        phrase = " ".join(words[:n]).lower()
        count = 0
        for i in range(0, len(words) - n + 1, n):
            if " ".join(words[i:i + n]).lower() == phrase:
                count += 1
        if count >= 3:
            return True
    return False


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

        self.hotwords_string: Optional[str] = None
        if WHISPER_HOTWORDS_FILE:
            if not os.path.isfile(WHISPER_HOTWORDS_FILE):
                raise RuntimeError(
                    f"WHISPER_HOTWORDS_FILE does not exist: {WHISPER_HOTWORDS_FILE}"
                )
            with open(WHISPER_HOTWORDS_FILE, "r", encoding="utf-8") as f:
                phrases = [ln.strip() for ln in f if ln.strip()]
            self.hotwords_string = " ".join(phrases) if phrases else None
            logger.info(
                "Whisper hotwords enabled - file=%s count=%d chars=%d",
                WHISPER_HOTWORDS_FILE,
                len(phrases),
                len(self.hotwords_string or ""),
            )

    def startup_details(self) -> Dict[str, Any]:
        return {
            "backend": self.backend_name,
            "backend_model": MODEL_SIZE,
            "device": DEVICE,
            "compute_type": COMPUTE_TYPE,
            "hotwords_file": WHISPER_HOTWORDS_FILE or None,
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
                    hotwords=self.hotwords_string,
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

            full_text = " ".join([s["text"].strip() for s in segments]).strip()

            if not _looks_like_hallucination(segments) and not _has_phrase_repetition(full_text):
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
            import torch
            from omegaconf import OmegaConf
            from nemo.collections.asr.models.rnnt_bpe_models_prompt import (
                EncDecRNNTBPEModelWithPrompt,
            )
            from nemo.collections.asr.parts.submodules.rnnt_decoding import RNNTDecodingConfig
            from nemo.collections.asr.parts.utils.rnnt_utils import Hypothesis
            from nemo.collections.asr.parts.utils.streaming_utils import CacheAwareStreamingAudioBuffer
        except ImportError as exc:
            raise RuntimeError(
                "Nemotron backend requires NeMo ASR runtime from NVIDIA/NeMo main. "
                "Install `nemo_toolkit[asr] @ git+https://github.com/NVIDIA/NeMo.git@main` "
                "to use TRANSCRIPTION_BACKEND=nemotron."
            ) from exc
        self.torch = torch
        self.hypothesis_cls = Hypothesis
        self.streaming_buffer_cls = CacheAwareStreamingAudioBuffer
        self.att_context_size = _parse_nemotron_att_context_size(NEMOTRON_ATT_CONTEXT_SIZE_RAW)
        self.device = torch.device("cuda" if DEVICE == "cuda" and torch.cuda.is_available() else "cpu")
        self.compute_dtype = torch.float32
        self.model_path = hf_hub_download(
            repo_id=NEMOTRON_MODEL_NAME,
            filename=NEMOTRON_MODEL_FILENAME,
            cache_dir="/app/models/hf",
        )
        self.model = EncDecRNNTBPEModelWithPrompt.restore_from(self.model_path)
        if not hasattr(self.model.encoder, "set_default_att_context_size"):
            raise RuntimeError("Nemotron model does not support configurable att_context_size")
        self.model.encoder.set_default_att_context_size(att_context_size=self.att_context_size)
        self._configure_decoding(RNNTDecodingConfig, OmegaConf)
        self.model = self.model.to(device=self.device, dtype=self.compute_dtype)
        self.model.eval()
        self._inference_lock = threading.Lock()

    def startup_details(self) -> Dict[str, Any]:
        return {
            "backend": self.backend_name,
            "backend_model": NEMOTRON_MODEL_NAME,
            "device": DEVICE,
            "checkpoint": self.model_path,
            "att_context_size": self.att_context_size,
            "chunk_size_ms": _nemotron_chunk_size_ms(self.att_context_size),
            "boosting_phrases_file": NEMOTRON_BOOSTING_PHRASES_FILE or None,
        }

    def accepted_models(self) -> Set[str]:
        return {WHISPER_COMPAT_MODEL, NEMOTRON_PUBLIC_MODEL, NEMOTRON_MODEL_NAME}

    def _configure_decoding(self, rnnt_decoding_config_cls, omega_conf) -> None:
        decoding_cfg = omega_conf.structured(rnnt_decoding_config_cls(fused_batch_size=-1))
        decoding_cfg.strategy = "greedy_batch"
        if NEMOTRON_BOOSTING_PHRASES_FILE:
            if not os.path.isfile(NEMOTRON_BOOSTING_PHRASES_FILE):
                raise RuntimeError(
                    f"NEMOTRON_BOOSTING_PHRASES_FILE does not exist: {NEMOTRON_BOOSTING_PHRASES_FILE}"
                )
            decoding_cfg.greedy.boosting_tree.key_phrases_file = NEMOTRON_BOOSTING_PHRASES_FILE
            decoding_cfg.greedy.boosting_tree.context_score = NEMOTRON_BOOSTING_CONTEXT_SCORE
            decoding_cfg.greedy.boosting_tree.depth_scaling = NEMOTRON_BOOSTING_DEPTH_SCALING
            decoding_cfg.greedy.boosting_tree_alpha = NEMOTRON_BOOSTING_ALPHA
            logger.info(
                "Nemotron GPU phrase boosting enabled - file=%s alpha=%s context_score=%s depth_scaling=%s",
                NEMOTRON_BOOSTING_PHRASES_FILE,
                NEMOTRON_BOOSTING_ALPHA,
                NEMOTRON_BOOSTING_CONTEXT_SCORE,
                NEMOTRON_BOOSTING_DEPTH_SCALING,
            )
        if hasattr(self.model, "cur_decoder"):
            self.model.change_decoding_strategy(decoding_cfg, decoder_type="rnnt")
        else:
            self.model.change_decoding_strategy(decoding_cfg)

    def _extract_streaming_texts(self, hypotheses: Any) -> List[str]:
        if not hypotheses:
            return []
        if isinstance(hypotheses[0], self.hypothesis_cls):
            return [str(hyp.text).strip() for hyp in hypotheses]
        return [str(hyp).strip() for hyp in hypotheses]

    def _drop_extra_pre_encoded(self, step_num: int) -> int:
        if step_num == 0:
            return 0
        return int(getattr(self.model.encoder.streaming_cfg, "drop_extra_pre_encoded", 0))

    def _stream_audio_file(self, wav_path: str, target_lang: str) -> List[str]:
        streaming_buffer = self.streaming_buffer_cls(
            model=self.model,
            online_normalization=False,
            pad_and_drop_preencoded=False,
        )
        streaming_buffer.append_audio_file(wav_path, stream_id=-1)
        batch_size = len(streaming_buffer.streams_length)
        cache_last_channel, cache_last_time, cache_last_channel_len = self.model.encoder.get_initial_cache_state(
            batch_size=batch_size
        )
        previous_hypotheses = None
        pred_out_stream = None
        transcribed_texts: List[str] = []
        for step_num, (chunk_audio, chunk_lengths) in enumerate(iter(streaming_buffer)):
            with self.torch.inference_mode():
                chunk_audio = chunk_audio.to(self.device, dtype=self.compute_dtype)
                chunk_lengths = chunk_lengths.to(self.device)
                (
                    pred_out_stream,
                    step_hypotheses,
                    cache_last_channel,
                    cache_last_time,
                    cache_last_channel_len,
                    previous_hypotheses,
                ) = self.model.conformer_stream_step(
                    processed_signal=chunk_audio,
                    processed_signal_length=chunk_lengths,
                    cache_last_channel=cache_last_channel,
                    cache_last_time=cache_last_time,
                    cache_last_channel_len=cache_last_channel_len,
                    keep_all_outputs=streaming_buffer.is_buffer_empty(),
                    previous_hypotheses=previous_hypotheses,
                    previous_pred_out=pred_out_stream,
                    drop_extra_pre_encoded=self._drop_extra_pre_encoded(step_num),
                    return_transcription=True,
                )
                transcribed_texts = self._extract_streaming_texts(step_hypotheses)
        streaming_buffer.reset_buffer()
        logger.info(
            "Nemotron cache-aware streaming completed - target_lang=%s att_context_size=%s chunk_ms=%s",
            target_lang,
            self.att_context_size,
            _nemotron_chunk_size_ms(self.att_context_size),
        )
        return transcribed_texts

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
                with self._inference_lock:
                    if hasattr(self.model, "set_inference_prompt"):
                        self.model.set_inference_prompt(target_lang)
                    if hasattr(self.model, "decoding") and hasattr(self.model.decoding, "set_strip_lang_tags"):
                        self.model.decoding.set_strip_lang_tags(False)
                    return self._stream_audio_file(wav_path, target_lang)

            stream_result = await asyncio.get_event_loop().run_in_executor(
                transcription_executor, _transcribe_sync
            )
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

        if not isinstance(stream_result, list) or not stream_result:
            raise RuntimeError("Nemotron backend returned no hypotheses")

        hypotheses = stream_result
        first = hypotheses[0]
        raw_text = _extract_response_text(first)
        full_text = _clean_nemotron_text(raw_text)
        words = _extract_word_timestamps(first) if want_word_timestamps else []
        if words:
            seg_start = words[0]["start"]
            seg_end = words[-1]["end"]
        else:
            seg_start = 0.0
            seg_end = duration

        no_speech_prob = _nemotron_no_speech_prob(full_text, duration)

        segment: Dict[str, Any] = {
            "id": 0,
            "seek": 0,
            "start": seg_start,
            "end": seg_end,
            "text": full_text,
            "tokens": [],
            "temperature": 0.0,
            "avg_logprob": 0.0,
            "compression_ratio": _text_compression_ratio(full_text),
            "no_speech_prob": no_speech_prob,
            "audio_start": seg_start,
            "audio_end": seg_end,
        }
        if words:
            segment["words"] = words

        detected_language = _extract_nemotron_detected_language(raw_text, target_lang)
        language_probability = 1.0 if target_lang != "auto" else 0.0

        segments_out = [segment] if (full_text or words) else []

        def _empty_response(reason: str) -> Dict[str, Any]:
            logger.info(
                "Worker %s Nemotron gate dropped (%s): "
                "compression=%.3f no_speech=%.3f text=%r",
                WORKER_ID, reason,
                segment.get("compression_ratio", 0.0), no_speech_prob, full_text[:80],
            )
            return {
                "text": "",
                "language": detected_language,
                "language_probability": language_probability,
                "duration": duration,
                "segments": [],
            }

        if _looks_like_silence(segments_out):
            return _empty_response("silence")
        # Hallucination gate: uses compression_ratio only (same heuristic for both
        # backends) via _looks_like_hallucination. Nemotron does not get a logprob
        # check — RNN-T score scale (~-3 to -5 per token, grows with length) is
        # fundamentally different from Whisper CTC avg_logprob (~[-1.5, 0]).
        # Catching Nemotron repetition/garbage relies on compression_ratio +
        # phrase_repetition below.
        if _looks_like_hallucination(segments_out):
            return _empty_response("hallucination")
        if _has_phrase_repetition(full_text):
            return _empty_response("phrase_repetition")

        return {
            "text": full_text,
            "language": detected_language,
            "language_probability": language_probability,
            "duration": duration,
            "segments": segments_out,
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
    """Heuristic: reject segments that look like hallucinations / low-confidence.

    Note: this checks avg_logprob against LOG_PROB_THRESHOLD which is tuned
    for Whisper CTC scale (~[-1.5, 0]). Nemotron does NOT use this for the
    logprob check (different RNN-T scale) — it relies on compression_ratio
    + phrase_repetition instead.
    """
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
    if "att_context_size" in backend_details:
        health_status["att_context_size"] = backend_details["att_context_size"]
    if "chunk_size_ms" in backend_details:
        health_status["chunk_size_ms"] = backend_details["chunk_size_ms"]
    if "boosting_phrases_file" in backend_details:
        health_status["boosting_phrases_file"] = backend_details["boosting_phrases_file"]
    if "hotwords_file" in backend_details:
        health_status["hotwords_file"] = backend_details["hotwords_file"]
    
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
