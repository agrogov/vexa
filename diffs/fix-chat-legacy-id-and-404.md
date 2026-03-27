# Fix: Chat API legacy combined-ID routes and soft 404 on chat read

## PR Title
`fix(api-gateway,bot-manager): add legacy combined-ID chat routes and return empty list on chat-read 404`

## PR Description

### Problem

Two separate issues in the chat endpoints:

1. **Legacy combined-ID requests fail with 404** — some callers (dashboard, older SDK versions)
   send chat requests to `/bots/{platform}_{native_meeting_id}/chat` (compound ID in a single
   path segment) instead of the canonical `/bots/{platform}/{native_meeting_id}/chat`. The API
   gateway had no route for this shape, so requests 404'd immediately.

2. **Chat read after meeting end returns 404** — `bot_chat_read` in `bot-manager` called
   `_find_active_meeting`, which only matches meetings in an active state. Once a meeting ends
   the endpoint returned 404, causing noisy errors in the dashboard even though reading chat
   history is a valid post-meeting operation.

### Fix

**`services/api-gateway/main.py`**
- Added `_split_compound_platform_meeting_id(compound_id)` helper that parses legacy IDs like
  `teams_123456789` or `google_meet_abc-defg-hij` by matching against `Platform` enum values
  (longest prefix first to handle multi-word platforms like `google_meet`).
- Added `POST /bots/{platform_and_native_meeting_id}/chat` and
  `GET /bots/{platform_and_native_meeting_id}/chat` legacy compatibility routes (hidden from
  schema with `include_in_schema=False`).
- `chat_read_proxy` and `chat_read_legacy_proxy` now return `{"messages": [], "meeting_id": null}`
  on a 404 from bot-manager instead of propagating the error.

**`services/bot-manager/app/main.py`**
- Added `_find_latest_meeting()` helper that queries for any meeting matching
  `(user_id, platform, native_meeting_id)` ordered by `created_at DESC`, regardless of status.
- `bot_chat_read` now calls `_find_latest_meeting` instead of `_find_active_meeting` and returns
  `{"messages": [], "meeting_id": None}` when no record is found at all, eliminating 404 noise.

## Files Changed

| File | Change |
|------|--------|
| `services/api-gateway/main.py` | `_split_compound_platform_meeting_id` helper; legacy POST/GET `/bots/{compound}/chat` routes; soft-404 on chat read |
| `services/bot-manager/app/main.py` | `_find_latest_meeting` helper; `bot_chat_read` uses it instead of `_find_active_meeting` |
