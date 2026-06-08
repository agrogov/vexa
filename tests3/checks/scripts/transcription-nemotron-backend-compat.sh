#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
MAIN="$ROOT/services/transcription-service/main.py"
REQS="$ROOT/services/transcription-service/requirements.txt"

grep -q 'class NemotronBackend' "$MAIN"
grep -q 'nvidia/nemotron-3.5-asr-streaming-0.6b' "$MAIN"
grep -q 'return {NEMOTRON_PUBLIC_MODEL, NEMOTRON_MODEL_NAME}' "$MAIN"
grep -q 'EncDecRNNTBPEModelWithPrompt' "$MAIN"
grep -q 'set_inference_prompt(target_lang)' "$MAIN"
grep -q 'git+https://github.com/NVIDIA/NeMo.git@main' "$REQS"

echo "ok: nemotron backend + nemo runtime wiring present"
