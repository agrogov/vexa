# Chat

## Why

Bots need to interact with meeting participants via chat — reading messages and sending responses. This enables AI-powered chat interactions during live meetings.

## What

This feature enables the bot to observe meeting chat messages and inject messages into the meeting chat via API.

### Documentation
- [Interactive Bots](../../docs/interactive-bots.mdx)
- [Interactive Bots API](../../docs/api/interactive-bots.mdx)

### Components

- **vexa-bot**: observes the meeting chat DOM for new messages, injects messages into the DOM
- **bot-manager**: relays chat commands between API and bot
- **api-gateway**: exposes chat endpoints (POST to send, GET to read)

### Data flow

```
Sending:  client → api-gateway → bot-manager → vexa-bot → meeting chat DOM
Reading:  meeting chat DOM → vexa-bot → Redis → api-gateway → client
```

### Key behaviors

- POST /bots/{id}/chat sends a message into the meeting chat
- GET /bots/{id}/chat returns messages observed from other participants
- Bot observes the DOM for new chat messages in real-time
- Messages are relayed via bot-manager and Redis
- Chat works across supported meeting platforms

## How

This is a cross-service feature. Testing requires the full compose stack with a mock meeting.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Start a bot in a mock meeting
3. Send a message: `POST /bots/{id}/chat` with `{"message": "Hello"}`
4. Verify the message appears in the meeting chat
5. Have another participant send a chat message
6. Read messages: `GET /bots/{id}/chat` — verify the participant's message appears

### Known limitations

- Chat observation depends on platform-specific DOM structure
- No message history persistence beyond the meeting session
- Rate limiting on chat injection not documented
