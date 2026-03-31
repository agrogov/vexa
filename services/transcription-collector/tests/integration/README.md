# Integration Tests — transcription-collector

## What this tests
- Redis stream consumption: reads transcription_segments, processes, acknowledges
- Postgres persistence: segments written correctly with speaker attribution
- Meeting lifecycle: segments grouped by meeting, finalized on meeting end
- Webhook delivery: fires webhooks on transcript ready with correct payload
- Backpressure: handles Redis stream backlog without data loss
- Consumer group recovery: resumes after restart without reprocessing

## Dependencies
- transcription-collector running
- Redis running (with transcription_segments stream)
- Postgres running (with vexa schema)

## How to invoke
Start a testing agent in this directory. It reads this README and the parent service README to understand what to verify.
