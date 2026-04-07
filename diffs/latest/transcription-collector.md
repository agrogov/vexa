# transcription-collector + libs changes

## transcription-collector/mapping/speaker_mapper.py — refactored speaker mapping
- Significant rewrite of speaker mapping logic for correctness and testability
- Added optional import guard for `redis` package so the module can be imported in unit test environments without Redis installed
- Removed hardcoded `PRE_SEGMENT_SPEAKER_EVENT_FETCH_MS = 0` / `POST_SEGMENT_SPEAKER_EVENT_FETCH_MS = 500` constants; buffer logic moved into mapping functions
- Refactored participant identifier resolution, event matching, and concurrent speaker detection

## transcription-collector/streaming/processors.py — minor fixes

## libs/shared-models/shared_models/webhook_url.py — SSRF allowlist
- Added `WEBHOOK_ALLOWED_CIDRS` env var support: comma-separated CIDR ranges that bypass the private-IP SSRF block (e.g. `10.116.0.0/16` for in-cluster webhook delivery)
- Without this, webhooks targeting internal K8s service IPs were blocked by the SSRF protection layer
