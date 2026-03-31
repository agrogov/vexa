# WebSocket Streaming

## Why

Clients need live transcripts as they happen, not after the meeting ends. WebSocket streaming pushes transcript segments to connected clients in real time.

## What

This feature provides a WebSocket endpoint that clients connect to for receiving live transcript segments during an active meeting.

### Documentation
- [WebSocket API](../../docs/websocket.mdx)

### Components

- **transcription-collector**: publishes new transcript segments to Redis pubsub
- **Redis**: pubsub channel carries segment events
- **api-gateway**: maintains WS connections, subscribes to Redis pubsub, fans out segments to clients

### Data flow

```
transcription-collector → Redis pubsub → api-gateway WS → client
```

### Key behaviors

- Client connects to `ws://host/ws` with authentication
- Client subscribes to a specific meeting by ID
- Segments are pushed as they're produced (low latency)
- Each segment includes text, speaker name, timestamp
- Multiple clients can subscribe to the same meeting
- Disconnected clients can reconnect and catch up via REST API

## How

This is a cross-service feature. Testing requires the full compose stack with an active meeting producing transcripts.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Connect to WS: `wscat -c ws://localhost:8056/ws -H "X-API-Key: <token>"`
3. Subscribe to a meeting
4. Start a bot in that meeting
5. Verify transcript segments arrive via WS

### Known limitations

- No message backlog — missed messages during disconnect are not replayed via WS
- No heartbeat/ping-pong implementation documented
- Scaling: Redis pubsub is single-node, no clustering support
