#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
TEST_AUDIO="$ROOT/tests3/testdata/test-speech-en.wav"

python3 - "$ROOT" "$TEST_AUDIO" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
test_audio = Path(sys.argv[2])

if not test_audio.is_file():
    print(f"test audio missing: {test_audio}", file=sys.stderr)
    sys.exit(1)

env_file = root / ".env"
tx_url = ""
tx_token = ""
if env_file.is_file():
    for line in env_file.read_text().splitlines():
        if line.startswith("TRANSCRIPTION_SERVICE_URL="):
            tx_url = line.split("=", 1)[1].strip()
        elif line.startswith("TRANSCRIPTION_SERVICE_TOKEN="):
            tx_token = line.split("=", 1)[1].strip()

def docker_compose_env(var: str) -> str:
    try:
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "meeting-api", "printenv", var],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""

if not tx_url:
    tx_url = docker_compose_env("TRANSCRIPTION_SERVICE_URL")
if not tx_token:
    tx_token = docker_compose_env("TRANSCRIPTION_SERVICE_TOKEN")

if not tx_url:
    print("no transcription URL configured", file=sys.stderr)
    sys.exit(1)

cmd = [
    "curl", "-sS", "-w", "\n%{http_code}", "-X", "POST", tx_url,
    "-H", f"Authorization: Bearer {tx_token}",
    "-F", f"file=@{test_audio};type=audio/wav",
    "-F", "model=totally-unknown-model",
    "-F", "response_format=verbose_json",
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
stdout = result.stdout.strip()
if not stdout:
    print(result.stderr.strip() or "empty response", file=sys.stderr)
    sys.exit(1)
body, code = stdout.rsplit("\n", 1)
if code not in {"400", "422"}:
    print(f"expected 4xx, got HTTP {code}: {body[:400]}", file=sys.stderr)
    sys.exit(1)

try:
    payload = json.loads(body)
except json.JSONDecodeError as exc:
    print(f"invalid JSON: {exc}", file=sys.stderr)
    sys.exit(1)

detail = str(payload.get("detail", ""))
if "totally-unknown-model" not in detail:
    print(f"error detail does not name invalid model: {detail}", file=sys.stderr)
    sys.exit(1)

print(f"ok: invalid model rejected with HTTP {code}")
PY
