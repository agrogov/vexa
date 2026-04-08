# fix(dashboard): wrap all static icon paths with withBasePath, harden admin session with HMAC, drive Tracker nav from config

## Commit title
`fix(dashboard): fix icon paths for sub-path deployments, sign admin session cookie with HMAC, config-driven Tracker nav`

## Description

### `withBasePath()` for all static icon `<Image>` sources
When the dashboard is deployed under a sub-path (e.g. `/vexa`), Next.js `<Image>` tags with bare `/icons/...` paths produce 404s because the base path is not prepended. All affected files now wrap icon `src` values with `withBasePath()`:

- `login/page.tsx` — platform icon in the URL input field and the Google Meet / Teams chips.
- `mcp/page.tsx` — Cursor and VS Code icons in the MCP connection cards.
- `meetings/[id]/page.tsx` — ChatGPT / Perplexity dropdown icons (two locations) and the per-meeting platform icon in the header.
- `meetings/page.tsx` — `PlatformIcon` component (Google Meet, Teams, Zoom).
- `components/meetings/meeting-card.tsx` — `GoogleMeetIcon`, `TeamsIcon`, `ZoomIcon` helper components condensed and wrapped.

### HMAC-signed admin session cookie (`api/admin/[...path]/route.ts`)
The admin session cookie was a plain base64-encoded JSON blob — anyone who could read the cookie could forge a valid session by crafting their own payload. The cookie is now signed with an HMAC-SHA256 signature using `JWT_SECRET` / `NEXTAUTH_SECRET`:

- Cookie format: `<base64-payload>.<hex-signature>`
- `extractPayload()` verifies the signature with `crypto.timingSafeEqual` before deserialising.
- Unsigned or tampered cookies are rejected.

### Config-driven Tracker nav item (`components/layout/sidebar.tsx`)
The Tracker nav entry was conditionally rendered via a build-time `NEXT_PUBLIC_TRACKER_ENABLED` env var, which required a rebuild to toggle. It is now driven at runtime by `config.decisionListenerUrl`: the item appears when the runtime config includes a decision-listener URL, and is hidden otherwise. The static `navigation` array is replaced with a computed one inside the component.
