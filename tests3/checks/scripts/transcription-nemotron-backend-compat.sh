#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
MAIN="$ROOT/services/transcription-service/main.py"
REQS="$ROOT/services/transcription-service/requirements.txt"

grep -q 'class NemotronBackend' "$MAIN"
grep -q 'nvidia/nemotron-3.5-asr-streaming-0.6b' "$MAIN"
grep -q 'return {WHISPER_COMPAT_MODEL, NEMOTRON_PUBLIC_MODEL, NEMOTRON_MODEL_NAME}' "$MAIN"
grep -q 'import nemo.collections.asr as nemo_asr' "$MAIN"
grep -q 'nemo_toolkit\[asr\]' "$REQS"

echo "ok: nemotron backend + nemo runtime wiring present"
