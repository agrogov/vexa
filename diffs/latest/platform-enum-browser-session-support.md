# fix: add browser_session to Platform enum — fixes 422 on stop/delete/transcripts

## Commit title
`fix: add browser_session to Platform enum to fix 422 on meeting stop/delete/transcripts`

## Description
`browser_session` was a valid platform value stored in the database but was missing from
the `Platform` enum in `shared_models/schemas.py`. As a result, any API call that routes
through an endpoint typed `{platform}: Platform` would fail with HTTP 422 Unprocessable
Entity when the meeting had `platform="browser_session"`.

Affected endpoints (all returning 422 before this fix):
- `DELETE /bots/browser_session/{native_id}` (stop bot)
- `DELETE /meetings/browser_session/{native_id}` (delete meeting)
- `GET /transcripts/browser_session/{native_id}` (fetch transcripts)
- `GET /bots/browser_session/{native_id}/chat` (fetch chat messages)

### Changes

**`libs/shared-models/shared_models/schemas.py`**
- Added `BROWSER_SESSION = "browser_session"` to the `Platform` enum
- Added `Platform.BROWSER_SESSION: "browser_session"` mapping to the `bot_name` property

**`services/dashboard/src/types/vexa.ts`**
- Added `"browser_session"` to the `Platform` union type so TypeScript no longer
  rejects the value when it appears in meeting data from the API

### Why this is the right fix
All backend route handlers validate the `{platform}` path parameter against the `Platform`
enum before any handler logic runs. Adding `browser_session` to the enum means existing
stop, delete, and transcript endpoints work for browser session meetings without any
additional routing or handler changes. The `construct_meeting_url` method already has an
`else: return None` fallback so browser_session URL construction degrades gracefully.
