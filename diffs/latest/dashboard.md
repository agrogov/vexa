# dashboard changes

## Sub-path deployment (NEXT_PUBLIC_BASE_PATH=/vexa)
- Added `withBasePath()` wrapper to all `fetch()` / API calls that were missing it: `admin-api.ts` (6 calls), `webhook-store.ts` (3 calls), `profile/page.tsx` (2 calls), and various other pages/hooks/stores
- Removed `withBasePath()` from Next.js `<Image src>` props — Next.js `<Image>` auto-prepends `basePath` from `next.config.ts`, so applying `withBasePath()` on top double-prefixed paths to `/vexa/vexa/...` causing `received null` errors. Native `<img>` tags keep `withBasePath()` as the browser has no knowledge of `basePath`
- Renamed `NEXT_PUBLIC_DECISION_LISTENER_URL` → `DECISION_LISTENER_URL` in dashboard deployment (was a public build-time var, now server-side only)

## admin/bots/page.tsx
- Filter out running bots with missing `platform` or `native_meeting_id` before rendering (prevents crash on incomplete bot records)
- `handleStopBot`: added null guard on `platform` / `nativeId` parameters
- `stopping` status badge color changed from slate to orange for better visibility

## Various pages — base-path and minor fixes
- `login/page.tsx`, `meetings/page.tsx`, `meetings/[id]/page.tsx`, `mcp/page.tsx`, `profile/page.tsx`, `settings/page.tsx`, `tracker/page.tsx`, `browser/page.tsx`: base-path fixes and minor UI/routing corrections
- `auth/verify/page.tsx`, `auth/zoom/callback/page.tsx`: base-path fixes
- `components/`: `admin-guard`, `ai-chat-panel`, `decisions-panel`, `sidebar`, `mcp-config-button`, `notification-banner`, `logo` — base-path and minor fixes
- `hooks/`: `use-live-transcripts`, `use-runtime-config`, `use-vexa-websocket` — base-path fixes
- `stores/`: `admin-auth-store`, `auth-store`, `webhook-store` — base-path fixes
- `lib/`: `admin-api`, `api`, `zoom-oauth-client` — base-path fixes
