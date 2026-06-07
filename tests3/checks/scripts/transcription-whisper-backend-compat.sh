#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
MAIN="$ROOT/services/transcription-service/main.py"

grep -q 'TRANSCRIPTION_BACKEND' "$MAIN"
grep -q 'class WhisperBackend' "$MAIN"
grep -q 'WHISPER_COMPAT_MODEL = "whisper-1"' "$MAIN"
grep -q 'return {WHISPER_COMPAT_MODEL, MODEL_SIZE}' "$MAIN"

echo "ok: whisper backend selector + whisper-1 compatibility path present"
