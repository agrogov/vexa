# WebSocket Streaming Test Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| WS connection established | 90 | Connected to ws://localhost:8056/ws with X-API-Key header, got bidirectional comms. Also works via ?api_key= query param. | 2026-03-17 11:55 | Test with real production client |
| Auth rejection | 90 | No-key connection gets `{"type":"error","error":"missing_api_key"}` then close code 4401 | 2026-03-17 11:55 | Test with invalid/expired key |
| Ping/pong | 90 | Sent `{"action":"ping"}`, received `{"type":"pong"}` | 2026-03-17 11:55 | -- |
| Subscribe to meeting | 90 | Sent subscribe for google_meet/kyr-hxog-eah, got `{"type":"subscribed","meetings":[...]}`. TC authorize-subscribe called successfully. | 2026-03-17 11:55 | -- |
| Live segments received | 85 | Published test segment to Redis channel `tc:meeting:8812:mutable`, received it on WS with correct text/speaker_name/timestamp. Redis PUBLISH returned 1 subscriber. | 2026-03-17 11:55 | Verify with real speech producing segments from transcription-collector (no active speech during test) |
| Segment format correct | 85 | Received: `{"type":"segment","meeting_id":8812,"text":"Hello from WebSocket test","speaker_name":"TestSpeaker","timestamp":"..."}` -- has text, speaker_name, timestamp | 2026-03-17 11:55 | Verify real TC-produced segment format matches |
| Unsubscribe | 90 | Sent unsubscribe for google_meet/kyr-hxog-eah, got `{"type":"unsubscribed","meetings":[...]}` | 2026-03-17 11:55 | -- |
| Multi-client fanout | 80 | Two simultaneous WS connections both connected and subscribed to same meeting successfully | 2026-03-17 11:55 | Verify both clients receive the same segment from a single Redis publish |
| Error handling | 90 | Invalid subscribe payload returns `invalid_subscribe_payload`, unknown action returns `unknown_action`, invalid JSON returns `invalid_json` | 2026-03-17 11:55 | -- |
| Query param auth | 90 | Connected via `ws://localhost:8056/ws?api_key=...`, ping/pong works | 2026-03-17 11:55 | -- |

## Gate verdict: PASS

All checks >= 80. Lowest score: 80 (multi-client fanout -- verified connect+subscribe, not same-segment delivery to both).

## Key findings

1. **Full pipeline works**: Redis PUBLISH on `tc:meeting:{id}:mutable` -> api-gateway WS -> client. Verified end-to-end with synthetic segment.
2. **No real segments observed**: Bot for meeting 8812 was active but no speech was occurring during test window (15s listen). This is expected -- the pipeline only delivers when transcription-collector publishes.
3. **Auth works both ways**: X-API-Key header and `?api_key=` query param both authenticate successfully.
4. **Subscribe calls TC authorize-subscribe**: api-gateway delegates authorization to transcription-collector at `/ws/authorize-subscribe`, which resolves user_id and meeting_id.
5. **Three Redis channels per subscription**: `tc:meeting:{id}:mutable` (segments), `bm:meeting:{id}:status` (meeting status), `va:meeting:{id}:chat` (chat messages).

## Untested

- Real transcription-collector segment delivery (requires active speech in meeting)
- Multi-client same-segment delivery (both clients subscribed, but no segment was published to verify both receive it)
- Invalid/expired API key rejection (only tested missing key)
- Connection behavior under load
- Reconnection handling
