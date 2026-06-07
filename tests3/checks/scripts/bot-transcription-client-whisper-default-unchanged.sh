#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
CLIENT="$ROOT/services/vexa-bot/core/src/services/transcription-client.ts"

grep -q 'name="model"' "$CLIENT"
grep -q 'whisper-1' "$CLIENT"

echo "model_field_default=whisper-1"
