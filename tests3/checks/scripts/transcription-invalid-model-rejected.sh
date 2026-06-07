#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
MAIN="$ROOT/services/transcription-service/main.py"

grep -q 'def _validate_requested_model' "$MAIN"
grep -q 'status_code=400' "$MAIN"
grep -q "Unsupported model" "$MAIN"

echo "ok: unsupported model values are rejected with HTTP 400"
