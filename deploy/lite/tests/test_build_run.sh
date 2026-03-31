#!/usr/bin/env bash
set -euo pipefail

# Lite single-container deployment test
# Usage: ./deploy/lite/tests/test_build_run.sh
# Requires: DATABASE_URL env var pointing to an accessible PostgreSQL

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

CONTAINER_NAME="vexa-lite-test"
IMAGE_NAME="vexa-lite:test"
PASS=0
FAIL=0
RESULTS=""

check() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    RESULTS+="PASS: $name\n"
    ((PASS++))
  else
    RESULTS+="FAIL: $name\n"
    ((FAIL++))
  fi
}

cleanup() {
  echo ">>> Cleaning up..."
  docker stop "$CONTAINER_NAME" 2>/dev/null || true
  docker rm "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Vexa Lite Build + Run Test ==="
echo "Started: $(date -Iseconds)"
echo ""

# Cleanup any previous test
cleanup

# Step 1: Build
echo ">>> Building Lite image..."
if docker build -f deploy/lite/Dockerfile.lite -t "$IMAGE_NAME" .; then
  RESULTS+="PASS: image build\n"
  ((PASS++))
else
  RESULTS+="FAIL: image build\n"
  ((FAIL++))
  echo -e "\n=== RESULTS ===\n$RESULTS"
  echo "PASS: $PASS  FAIL: $FAIL"
  exit 1
fi

# Image size
SIZE=$(docker images "$IMAGE_NAME" --format '{{.Size}}')
echo "Image size: $SIZE"
RESULTS+="INFO: image size = $SIZE\n"

# Step 2: Run
echo ">>> Starting container..."
DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@host.docker.internal:5432/vexa}"
docker run -d --name "$CONTAINER_NAME" \
  -p 18056:8056 \
  -e DATABASE_URL="$DATABASE_URL" \
  -e ADMIN_API_TOKEN="test-token-lite" \
  -e TRANSCRIBER_URL="https://placeholder/v1/audio/transcriptions" \
  -e TRANSCRIBER_API_KEY="test" \
  "$IMAGE_NAME"

echo ">>> Waiting 25s for supervisord startup..."
sleep 25

# Step 3: Check container running
check "container running" docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME"

# Step 4: Check supervisord
echo ">>> Checking supervisord programs..."
SUPERVISOR_OUTPUT=$(docker exec "$CONTAINER_NAME" supervisorctl status 2>/dev/null || true)
echo "$SUPERVISOR_OUTPUT"
RUNNING_COUNT=$(echo "$SUPERVISOR_OUTPUT" | grep -c "RUNNING" || true)
TOTAL_COUNT=$(echo "$SUPERVISOR_OUTPUT" | wc -l)
if [ "$RUNNING_COUNT" -gt 0 ]; then
  RESULTS+="PASS: supervisord ($RUNNING_COUNT/$TOTAL_COUNT RUNNING)\n"
  ((PASS++))
else
  RESULTS+="FAIL: supervisord (0 RUNNING)\n"
  ((FAIL++))
fi

# Step 5: Check API Gateway
echo ">>> Checking API Gateway..."
check "API Gateway :18056" curl -sf http://localhost:18056/

# Step 6: Check Redis internal
echo ">>> Checking internal Redis..."
check "Redis internal" docker exec "$CONTAINER_NAME" redis-cli ping

# Step 7: Check for crashes in logs
echo ">>> Checking logs..."
CRASH_COUNT=$(docker logs "$CONTAINER_NAME" 2>&1 | grep -ic "fatal\|panic\|segfault" || true)
if [ "$CRASH_COUNT" -eq 0 ]; then
  RESULTS+="PASS: no crashes in logs\n"
  ((PASS++))
else
  RESULTS+="FAIL: $CRASH_COUNT crash indicators in logs\n"
  ((FAIL++))
fi

# Report
echo ""
echo "=== RESULTS ==="
echo -e "$RESULTS"
echo "PASS: $PASS  FAIL: $FAIL"
echo "Finished: $(date -Iseconds)"

# Save results
mkdir -p deploy/lite/tests/results
echo -e "$(date -Iseconds)\n\n$RESULTS\nPASS: $PASS  FAIL: $FAIL" > deploy/lite/tests/results/last_run.txt

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
