# Transcription Collector Test Findings
Date: 2026-03-16 22:08:56
Mode: compose-full

## Summary
- PASS: 8
- FAIL: 1
- DEGRADED: 0
- UNTESTED: 1
- SURPRISING: 0

## Results
| Status | Test | Detail |
|--------|------|--------|
| PASS | Health (GET /health) | 200 |
| FAIL | Health | HTTP 200 |
| PASS | Meetings auth required | HTTP 403 |
| PASS | Redis stream exists | len=15071 |
| PASS | Consumer group | collector_group present |
| PASS | Postgres transcriptions | rows=417563 |
| PASS | Postgres meetings | rows=8539 |
| PASS | Docker logs | 1 error lines |
| PASS | Container stability | 0 restarts |
| UNTESTED | Transcript fetch | No google_meet meetings in DB |

## Riskiest thing
Silent transcript failures — 22% of completed meetings deliver nothing. No alerting.

## What was untested
- E2E segment flow (needs bot publishing to Redis)
- Webhook delivery
- Filtering logic
- Delete/anonymize endpoint

---

# Run 2
Date: 2026-03-16 19:31 UTC
Mode: compose-full (collector on port 8123)

## Summary
- PASS: 8
- FAIL: 0
- DEGRADED: 2
- UNTESTED: 3
- SURPRISING: 2

## Results
| Status | Test | Detail |
|--------|------|--------|
| PASS | Health (GET /health) | 200, redis=healthy, database=healthy |
| PASS | Meetings auth (GET /meetings) | 403 "Missing API token" — correct |
| PASS | Transcripts auth (GET /transcripts/...) | 403 "Missing API token" — correct |
| PASS | DELETE auth (DELETE /meetings/...) | 403 "Missing API token" — correct |
| PASS | PATCH auth (PATCH /meetings/...) | 403 "Missing API token" — correct |
| PASS | Redis transcription_segments stream | len=15073, collector_group present, last-delivered matches latest entry |
| PASS | Redis speaker_events_relative stream | len=19698, 1 consumer group present |
| PASS | Container stability | 0 restarts, up 34 min, 1 error log line (stale msg check, benign) |
| DEGRADED | Consumer group lag | 744 messages lag. 1 pending message stuck for 36 days (ID 1770555700442-0 from Feb 8). Consumer has read 14329 of 15073 entries. |
| DEGRADED | Silent transcript failures | 41% of completed meetings in last 30 days have zero transcriptions (473/1144). All-time: 44% (3207/7292). README documents 22% — understated by 2x. |
| UNTESTED | E2E segment flow | No active meetings producing segments during test window. Background processor reports "No active meetings found in Redis Set" every 10s. |
| UNTESTED | Webhook delivery | No webhook targets configured/visible. Cannot test without active meeting. |
| UNTESTED | Filtering logic | No segments flowing to exercise filters. Would need bot publishing real transcript data. |

## Riskiest thing
**Silent transcript failures at 41% (not 22%)** — nearly half of completed meetings in the last 30 days have zero transcriptions persisted. The collector has no detection or alerting for this. Segments never arrive from the bot — the collector cannot persist what it never receives. But the collector also does not raise an alarm when a meeting completes with zero segments, making the failure invisible.

## Degraded
1. **Stuck pending message** — Message ID 1770555700442-0 has been pending for 36 days (3.1 billion ms idle time). It was the first entry ever in the stream (a session_start from Feb 8). The consumer claimed it but never ACKed. This is not causing data loss (it's a session_start, not a transcript segment) but indicates the consumer's stale message claim logic isn't reclaiming it.
2. **Consumer lag of 744** — The consumer has read 14329 of 15073 entries. Since last-delivered-id matches the latest stream entry, this lag represents entries that were in the stream before the consumer group was created or the consumer started. Not a live issue but means ~5% of historical stream entries were never processed.

## Surprising
1. **README says `speaker_events` stream but code uses `speaker_events_relative`** — config.py sets `REDIS_SPEAKER_EVENTS_STREAM_NAME = "speaker_events_relative"`. The README lists `speaker_events` as a dependency. A separate `speaker_events` stream exists with only 25 entries and no consumer groups — it appears to be test data or a different producer path.
2. **All 5 REST endpoints require auth** — The README documents the endpoints but doesn't mention that every one (except /health) requires an API token. This makes black-box testing of the API impossible without credentials.

## What was untested
- **E2E segment flow**: No bot actively publishing segments. Cannot verify dedup, filtering, or Postgres persistence of new data.
- **Webhook delivery**: No webhook configuration visible. README doesn't document webhook setup.
- **Filtering logic**: Requires live segment flow to exercise.
- **DELETE/anonymize behavior**: Auth-gated, cannot test without valid token.
- **PATCH meeting metadata**: Auth-gated.

## README corrections needed
1. Silent failure rate: 22% -> 41% (as of March 2026, 30-day window)
2. Stream name: `speaker_events` -> `speaker_events_relative` in the dependency table
3. Endpoints table should note auth requirement
