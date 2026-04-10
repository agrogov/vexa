#!/usr/bin/env bash
set -euo pipefail

# Builds and pushes Vexa images to the Infobip registry.
#
# Usage:
#   ./build-images.sh [gpu|cpu] [VERSION]
#
# Examples:
#   ./build-images.sh           # gpu, default version
#   ./build-images.sh cpu       # cpu transcription-service variant
#   ./build-images.sh gpu v0.9.1

PROFILE="${1:-gpu}"
VERSION="${2:-v0.9.0}"
BASE_REPO="docker.ib-ci.com"

echo "Building Vexa images (PROFILE=${PROFILE}, VERSION=${VERSION})"
echo ""

build() {
  local name="$1"
  local tag="${BASE_REPO}/vexa/${name}:${VERSION}"
  shift
  echo "→ ${tag}"
  docker build -t "${tag}" "$@"
}

# ── Bot (spawned dynamically by runtime-api / meeting-api) ──────────────────
build vexa-bot \
  -f services/vexa-bot/Dockerfile \
  services/vexa-bot

# ── Core services (root build context) ──────────────────────────────────────
build api-gateway \
  -f services/api-gateway/Dockerfile \
  .

build admin-api \
  -f services/admin-api/Dockerfile \
  .

# Replaces bot-manager: bot orchestration + transcription aggregation
build meeting-api \
  -f services/meeting-api/Dockerfile \
  .

# Replaces bot-manager kubernetes orchestrator: pod lifecycle via K8s API
build runtime-api \
  -f services/runtime-api/Dockerfile \
  services/runtime-api

build mcp \
  -f services/mcp/Dockerfile \
  .

build tts-service \
  -f services/tts-service/Dockerfile \
  .

build vexa-dashboard \
  --build-arg NEXT_PUBLIC_BASE_PATH=/vexa \
  -f services/dashboard/Dockerfile \
  .

# ── New upstream services ────────────────────────────────────────────────────
build agent-api \
  -f services/agent-api/Dockerfile \
  .

build calendar-service \
  -f services/calendar-service/Dockerfile \
  .

build telegram-bot \
  -f services/telegram-bot/Dockerfile \
  .

build vexa-agent \
  -f services/vexa-agent/Dockerfile \
  .

# ── GPU/CPU transcription service ────────────────────────────────────────────
if [ "${PROFILE}" == "gpu" ]; then
  echo "→ ${BASE_REPO}/vexa/transcription-service:${VERSION} (GPU)"
  docker build \
    -t "${BASE_REPO}/vexa/transcription-service:${VERSION}" \
    -f services/transcription-service/Dockerfile \
    services/transcription-service
else
  echo "→ ${BASE_REPO}/vexa/transcription-service:${VERSION} (CPU)"
  docker build \
    -t "${BASE_REPO}/vexa/transcription-service:${VERSION}" \
    -f services/transcription-service/Dockerfile.cpu \
    services/transcription-service
fi

# ── Push ─────────────────────────────────────────────────────────────────────
echo ""
echo "Pushing to ${BASE_REPO}/vexa/ ..."
echo ""

for name in \
  vexa-bot \
  api-gateway \
  admin-api \
  meeting-api \
  runtime-api \
  mcp \
  tts-service \
  vexa-dashboard \
  agent-api \
  calendar-service \
  telegram-bot \
  vexa-agent \
  transcription-service
do
  docker push "${BASE_REPO}/vexa/${name}:${VERSION}"
done

echo ""
echo "All done. Images tagged ${VERSION}."
