#!/bin/bash
# Validate the Lite Dockerfile exists and has expected structure.
# Optionally builds the image if Docker is available.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
DOCKERFILE="$ROOT/deploy/lite/Dockerfile.lite"

echo "=== Lite Dockerfile validation ==="

# Check Dockerfile exists
if [ ! -f "$DOCKERFILE" ]; then
  echo "FAIL: Dockerfile.lite not found at $DOCKERFILE"
  exit 1
fi
echo "  OK: Dockerfile.lite exists"

# Check it has a FROM instruction
if ! grep -q "^FROM" "$DOCKERFILE"; then
  echo "FAIL: Dockerfile.lite has no FROM instruction"
  exit 1
fi
echo "  OK: has FROM instruction"

# Check supervisord config exists (lite uses supervisord)
SUPERVISORD="$ROOT/deploy/lite/supervisord.conf"
if [ ! -f "$SUPERVISORD" ]; then
  echo "FAIL: supervisord.conf not found"
  exit 1
fi
echo "  OK: supervisord.conf exists"

# Check entrypoint exists
ENTRYPOINT="$ROOT/deploy/lite/entrypoint.sh"
if [ ! -f "$ENTRYPOINT" ]; then
  echo "FAIL: entrypoint.sh not found"
  exit 1
fi
echo "  OK: entrypoint.sh exists"

# Optional: build test (skipped in CI unless LITE_BUILD_TEST=true)
if [ "${LITE_BUILD_TEST:-}" = "true" ] && command -v docker &>/dev/null; then
  echo "  Building vexa-lite:test..."
  docker build -f "$DOCKERFILE" -t vexa-lite:test "$ROOT" 2>&1 | tail -5
  echo "  OK: build succeeded"
fi

echo ""
echo "Lite Dockerfile validation: PASS"
