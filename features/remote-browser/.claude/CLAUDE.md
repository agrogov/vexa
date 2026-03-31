# Remote Browser Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope

You deliver a **remotely-accessible browser session** with persistent state via MinIO. The browser runs inside a vexa-bot container in `browser_session` mode. Human controls via VNC, agent controls via CDP/Playwright. The entire Chromium userdata directory syncs to/from MinIO.

## Gate

The gate is the URL. One `POST /bots { mode: "browser_session" }` call returns a URL. Everything works through it:

| Check | How to verify |
|-------|---------------|
| Browser accessible | Open URL in tab → see live Chromium via noVNC |
| Human can interact | Click, type, navigate in the noVNC view |
| Agent can control | `chromium.connectOverCDP(url + '/cdp')` → Playwright API works |
| Storage persists | Save → stop → restart → all accounts + files still there |
| Files persist | Create file in `/tmp/userdata/` → save → restart → file still there |
| Authenticated bot | `POST /bots { platform: "google_meet", authenticated: true }` → bot joins as authenticated user |

PASS = all checks verified. FAIL = any one missing.

## Key constraints

- **Persistent context**: Always `chromium.launchPersistentContext('/tmp/userdata', ...)` — never `launch()` or `--incognito`
- **No `--enable-automation`**: Strip via `ignoreDefaultArgs`
- **MinIO sync**: `aws s3 sync` before launch (download) and on save/exit (upload)
- **SingletonLock cleanup**: Always `rm -f SingletonLock SingletonCookie SingletonSocket` before Chromium start
- **URL is auth**: `/b/{token}` routes need no API key — the token IS the auth

## Infrastructure

- **vexa-bot** container in `browser_session` mode
- **MinIO** at `s3://vexa/users/{user_id}/browser-userdata/`
- **Ports**: noVNC :6080, CDP :9222 (proxied through api-gateway)
- **PoC reference**: `/home/dima/dev/playwright-vnc-poc/`

## Confidence ladder

| Level | Gate |
|-------|------|
| 0 | Not started |
| 30 | Container builds with VNC packages |
| 50 | Browser starts in session mode, VNC accessible via URL |
| 60 | CDP connection works via gateway proxy |
| 70 | User authenticates via VNC, Save syncs to MinIO |
| 80 | Restart browser session → all state restored from MinIO |
| 90 | Meeting bot with authenticated=true joins as authenticated user |
| 95 | Agent controls browser via CDP, creates files, files persist |
| 99 | Full round-trip: auth → save → authenticated meeting bot → transcription works |

## Critical findings
Save to `tests/findings.md`.
