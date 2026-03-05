#!/usr/bin/env bash
set -euo pipefail

# Builds Vexa images LOCALLY from the Vexa repo source tree.
# Usage:
#   ./scripts/build-images.sh cpu
#   ./scripts/build-images.sh gpu
#
# Notes:
# - For kind/minikube you may need to load images into the cluster after building.

PROFILE="${1:-cpu}"
VERSION="v0.6.0"
BASE_REPO="docker.ib-ci.com"

echo "Building Vexa images (PROFILE=$PROFILE, VERSION=$VERSION)"

# Bot image (spawned dynamically by bot-manager)
echo "Building ${BASE_REPO}/vexa/vexa-bot:${VERSION}"
docker build -t "${BASE_REPO}/vexa/vexa-bot:${VERSION}" -f services/vexa-bot/core/Dockerfile services/vexa-bot/core

# Core services
echo "Building ${BASE_REPO}/vexa/api-gateway:${VERSION}"
docker build -t "${BASE_REPO}/vexa/api-gateway:${VERSION}" -f services/api-gateway/Dockerfile .
echo "Building ${BASE_REPO}/vexa/admin-api:${VERSION}"
docker build -t "${BASE_REPO}/vexa/admin-api:${VERSION}" -f services/admin-api/Dockerfile .
echo "Building ${BASE_REPO}/vexa/bot-manager:${VERSION}"
docker build -t "${BASE_REPO}/vexa/bot-manager:${VERSION}" -f services/bot-manager/Dockerfile .
echo "Building ${BASE_REPO}/vexa/transcription-collector:${VERSION}"
docker build -t "${BASE_REPO}/vexa/transcription-collector:${VERSION}" -f services/transcription-collector/Dockerfile .
echo "Building ${BASE_REPO}/vexa/mcp:${VERSION}"
docker build -t "${BASE_REPO}/vexa/mcp:${VERSION}" -f services/mcp/Dockerfile .
echo "Building ${BASE_REPO}/vexa/transcription-service:${VERSION}"
docker build -t "${BASE_REPO}/vexa/transcription-service:${VERSION}" -f services/transcription-service/Dockerfile.cpu services/transcription-service

# WhisperLive
if [ "${PROFILE}" == "gpu" ]; then
  echo "Building ${BASE_REPO}/vexa/whisperlive (GPU version):${VERSION}"
  docker build -t "${BASE_REPO}/vexa/whisperlive:${VERSION}" -f services/WhisperLive/Dockerfile.project .
else
  echo "Building ${BASE_REPO}/vexa/whisperlive (CPU version):${VERSION}"
  docker build -t "${BASE_REPO}/vexa/whisperlive:${VERSION}" -f services/WhisperLive/Dockerfile.cpu .
fi

echo "Building ${BASE_REPO}/vexa/vexa-lite:${VERSION}"
docker build -t "${BASE_REPO}/vexa/vexa-lite:${VERSION}" -f docker/lite/Dockerfile.lite .

echo ""
echo "Done. Images built with ${VERSION} tag."
echo ""
echo "Pushing docker images to ${BASE_REPO}/vexa/"
echo ""

docker push "${BASE_REPO}/vexa/vexa-bot:${VERSION}"
docker push "${BASE_REPO}/vexa/api-gateway:${VERSION}"
docker push "${BASE_REPO}/vexa/admin-api:${VERSION}"
docker push "${BASE_REPO}/vexa/bot-manager:${VERSION}"
docker push "${BASE_REPO}/vexa/transcription-collector:${VERSION}"
docker push "${BASE_REPO}/vexa/mcp:${VERSION}"
docker push "${BASE_REPO}/vexa/transcription-service:${VERSION}"
docker push "${BASE_REPO}/vexa/whisperlive:${VERSION}"
docker push "${BASE_REPO}/vexa/vexa-lite:${VERSION}"

echo ""
echo "All done."
