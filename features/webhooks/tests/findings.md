# Webhooks Test Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Webhook URL configurable | 90 | PUT /user/webhook stores webhook_url and webhook_secret in user.data JSONB. Verified: user_id=3 data=`{"webhook_url":"https://httpbin.org/post","webhook_secret":"test-secret-123"}`. Response returns UserResponse with updated data. | 2026-03-17 11:56 | Test with real external endpoint, not httpbin |
| Bot status webhook fires (completion) | 90 | Meeting 8814 stopped -> bot-manager fired both exit webhook (send_webhook) and status webhook (send_status_webhook) for `meeting.completed` event. Logs: `Webhook delivered to https://httpbin.org/post: 200`, `Webhook delivery status written for meeting 8814: delivered (200)`. | 2026-03-17 11:58 | Test with real meeting, verify payload content |
| Bot status webhook fires (intermediate) | 60 | Webhook task ran for `joining` status but was skipped: `Webhook event 'meeting.status_change' not enabled for user`. Only `meeting.completed` is in default_enabled. Code review confirms intermediate statuses map to `meeting.status_change` which is OFF by default. User must set `webhook_events` in data to enable. | 2026-03-17 11:56 | Configure webhook_events and verify intermediate status webhooks fire |
| Transcript ready webhook fires | 0 | NOT IMPLEMENTED. No code fires `transcript.ready` events. send_status_webhook.py comment says it's default-ON but the code contradicts: `default_enabled = {"meeting.completed"}`. transcription-collector has zero webhook code. | 2026-03-17 11:57 | Implement transcript.ready webhook in transcription-collector or bot-manager |
| Payload schema correct | 80 | Code review of send_status_webhook.py: payload includes event_type, meeting object (id, user_id, platform, native_meeting_id, status, timestamps, data), and status_change object (from, to, reason, timestamp, transition_source). Exit webhook (send_webhook.py) sends flat meeting payload without event_type wrapper. No shared Pydantic schema for webhook payloads exists in shared-models. | 2026-03-17 11:57 | Capture actual httpbin response to verify payload matches code |
| End-to-end delivery | 90 | Full cycle verified: PUT /user/webhook (set URL) -> POST /bots (create bot, status=requested) -> bot transitions to joining -> DELETE /bots/platform/id (stop bot) -> status=completed -> webhook POSTed to httpbin.org -> HTTP 200. Delivery status written to meeting.data["webhook_delivery"]. | 2026-03-17 11:58 | Test with real meeting that runs through full lifecycle |
| HMAC signing | 80 | Code review: webhook_delivery.py build_headers() adds Authorization: Bearer, X-Webhook-Signature (sha256 HMAC of timestamp+payload), X-Webhook-Timestamp when webhook_secret is set. User_id=3 has webhook_secret stored. Both webhooks delivered with 200 status. | 2026-03-17 11:58 | Capture httpbin response to verify signature headers are present |
| SSRF protection | 80 | Code review: webhook_url.py blocks private IPs (10.x, 172.16.x, 192.168.x, 127.x, link-local), blocked hostnames (localhost, Docker service names, cloud metadata), validates scheme (http/https only), resolves DNS and checks all IPs. Applied both at URL set time (admin-api) and at delivery time (bot-manager). | 2026-03-17 11:57 | Test with blocked URLs to verify rejection |
| Retry/durability | 80 | Code review: webhook_delivery.py uses with_retry for exponential backoff (max 3 retries). Failed deliveries enqueued to Redis `webhook:retry_queue` when Redis client is set. webhook_retry_worker.py provides background retry. Bot-manager startup calls set_redis_client(). | 2026-03-17 11:57 | Test with unreachable URL and verify retry queue |
| GET webhook config | 0 | NOT IMPLEMENTED. No GET /user/webhook endpoint exists in admin-api or api-gateway. Users cannot read back their webhook config. Only PUT exists. | 2026-03-17 11:54 | Implement GET /user/webhook |

## Gate verdict: FAIL

Lowest score: 0 (transcript.ready webhook, GET webhook config).

Bottleneck: `transcript.ready` webhook is documented/referenced in comments but not implemented anywhere. GET endpoint for reading webhook config does not exist.

## Blocker: Provided API token unusable for webhook operations

The provided test token `vxa_user_mZbCdN...` resolves to user_id=2, which has DUPLICATE rows in the users table (emails: `angelkurten@gmail.com` and `108511@example.com`). SQLAlchemy UPDATE fails with `StaleDataError: UPDATE statement on table 'users' expected to update 1 row(s); 2 were matched.` This blocks all write operations on user_id=2, including setting webhook URL. Tests used user_id=3 (token `QSBB2hoKkzzyFH2iNl7N4...`) which has a unique row.

Root cause: users table has duplicate column names (id x2, email x2, created_at x2) suggesting a merged view/table from Supabase auth.users + app users. IDs 1 and 2 have 2 rows each.

## Code inconsistencies found

1. **Comment vs code mismatch** in `send_status_webhook.py:28-31`: Comment says "meeting.completed and transcript.ready are ON by default" but code has `default_enabled = {"meeting.completed"}` only.
2. **Two separate webhook paths**: Exit webhook (`bot_exit_tasks/send_webhook.py`) fires a flat meeting payload. Status webhook (`send_status_webhook.py`) fires an event_type-wrapped payload with status_change info. Both fire on completion, meaning the external endpoint receives TWO webhook POSTs for a single completion event.
3. **No webhook payload schema in shared-models**: Despite shared-models having webhook_url.py and webhook_delivery.py, there is no Pydantic model defining the webhook payload structure. Each sender constructs its own dict.
4. **No event filtering on exit webhook**: The exit webhook (`send_webhook.py`) always fires on meeting completion regardless of user's `webhook_events` config. Only status webhook respects event filtering.

## Docs gate -- FAIL

No README or docs pages found for the webhooks feature at `/home/dima/dev/vexa/features/webhooks/README.md`. Cannot check README-to-code or code-to-README consistency.
