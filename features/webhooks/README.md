# Webhooks

## Why

Clients need to know when things happen without polling. Webhooks push event notifications (bot status changes, transcript ready) to external endpoints in real time.

## What

This feature fires HTTP POST requests to user-configured URLs when bot status changes or transcripts become ready.

### Documentation
- [Webhooks](../../docs/webhooks.mdx)
- [Local Webhook Development](../../docs/local-webhook-development.mdx)

### Event types

- **Bot status change**: fired by bot-manager when a bot joins, leaves, errors, etc.
- **Transcript ready**: fired by transcription-collector when transcription completes

### Data flow

```
bot-manager → HTTP POST → external URL (bot status events)
transcription-collector → HTTP POST → external URL (transcript ready events)
```

### Key behaviors

- Webhook URL is configured per user via PUT /user/webhook
- Payload schema is defined in shared-models
- Webhooks are fire-and-forget (no retry on failure by default)
- Webhook payloads include event type, timestamp, and event-specific data

## How

This is a cross-service feature. Testing requires the full compose stack plus a webhook receiver.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Start a webhook receiver: `python -m http.server 9999` or use webhook.site
3. Configure webhook: `PUT /user/webhook` with the receiver URL
4. Trigger a bot status change (start/stop a bot)
5. Verify the receiver got the correct payload

### Known limitations

- No retry mechanism — failed deliveries are lost
- No webhook signature verification for authenticity
