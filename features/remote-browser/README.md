# Remote Browser

## Why

Vexa bots are unauthenticated guests. They launch fresh `--incognito` Chromium, join as strangers, land in lobbies, get rejected from org-restricted meetings. There's no way to give a bot a persistent browser identity.

The fix: a **human-agent collaborative browser** with profile persistence. Human authenticates via VNC, agent automates via CDP/Playwright — both control the same browser simultaneously. Browser state and user workspace persist across sessions.

Human handles what requires judgment (OAuth, CAPTCHAs, MFA). Agent handles what's automatable (navigation, validation, meeting scripts).

---

## What

One API call → one URL → a live Chromium browser you can see, control, and script.

- **VNC** — open the URL in a browser tab, see and interact with Chromium live
- **CDP/Playwright** — `connectOverCDP(url + '/cdp')` for full programmatic control
- **Persistent workspace** — scripts, files, data survive container restarts (git or MinIO)
- **Persistent browser state** — cookies, localStorage, IndexedDB survive restarts (MinIO)
- **Auto-admit script** — runs inside the container, admits anyone who joins the lobby

## How it works

Two persistent layers, separated:

```
/workspace/              ← user files (scripts, data) — synced via git or MinIO
/tmp/browser-data/       ← Chromium profile (cookies, localStorage) — synced via MinIO
```

On start: download both. On save: upload both. On next start: everything is there.

### Storage options for workspace

**Option A: MinIO (default)** — workspace syncs to `s3://vexa-recordings/users/{id}/browser-userdata/workspace/`. Git is initialized locally for version history. No external setup needed.

**Option B: GitHub (recommended for teams)** — workspace clones from a private GitHub repo. On save: commit + push. Full git history, PRs, collaboration. Configured via API.

Browser data always uses MinIO (Chromium profile is binary, not git-friendly).

---

## Quick start

### 1. Create a browser session

```bash
curl -X POST http://localhost:8056/bots \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}'
```

Response:
```json
{
  "id": 9107,
  "status": "active",
  "data": {
    "mode": "browser_session",
    "session_token": "HxpBmQsJOsHtG8myegDHuS-wMhBJaPDv"
  }
}
```

### 2. Open the browser

Dashboard (noVNC + toolbar):
```
http://localhost:8056/b/HxpBmQsJOsHtG8myegDHuS-wMhBJaPDv
```

### 3. Control via Playwright

```js
const { chromium } = require('playwright');
const browser = await chromium.connectOverCDP(
  'http://localhost:8056/b/HxpBmQsJOsHtG8myegDHuS-wMhBJaPDv/cdp'
);
const context = browser.contexts()[0];
const page = context.pages()[0];

await page.goto('https://accounts.google.com');
// ... authenticate, navigate, script
await page.screenshot({ path: 'screenshot.png' });

await browser.close(); // disconnects only — browser stays alive
```

### 4. Save storage

Click **[Save]** in the dashboard toolbar, or:
```bash
curl -X POST http://localhost:8056/b/HxpBmQsJOsHtG8myegDHuS-wMhBJaPDv/save
```

### 5. Stop and restart

```bash
# Stop
curl -X DELETE http://localhost:8056/bots/google_meet/9107 \
  -H "X-API-Key: YOUR_API_KEY"

# Start again — everything restored
curl -X POST http://localhost:8056/bots \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}'
```

Open the new URL → all accounts logged in, all workspace files there.

---

## GitHub workspace setup

Use a private GitHub repo to persist your workspace files (scripts, configs, data). Full git history, collaboration, PRs.

### 1. Create a private repo

Create a new private repo on GitHub (e.g., `my-bot-workspace`). Can be empty.

### 2. Create a fine-grained personal access token

Go to: https://github.com/settings/personal-access-tokens/new

Settings:
- **Token name**: `vexa-bot-workspace` (or whatever)
- **Expiration**: 90 days (or custom)
- **Repository access**: "Only select repositories" → select your workspace repo
- **Permissions**:
  - **Contents**: Read and write
  - **Metadata**: Read-only (auto-selected)
- Everything else: No access

Click "Generate token", copy the token (starts with `github_pat_...`).

### 3. Configure via API

```bash
curl -X PUT http://localhost:8056/auth/workspace-git \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/YOUR_USER/my-bot-workspace.git",
    "token": "github_pat_...",
    "branch": "main"
  }'
```

### 4. Use it

Next browser session will clone the repo into `/workspace/`. On save: commit + push. On next start: pull latest.

```
/workspace/                    ← cloned from your GitHub repo
├── scripts/
│   └── auto-admit.js          ← your scripts
├── configs/
│   └── settings.json          ← your configs
└── data/                      ← any data files
```

### 5. Remove git config (revert to MinIO)

```bash
curl -X DELETE http://localhost:8056/auth/workspace-git \
  -H "X-API-Key: YOUR_API_KEY"
```

---

## Auto-admit script

Runs inside the container. Polls for lobby guests, clicks Admit.

### Run manually

```bash
# Copy to workspace (persists across sessions)
docker cp auto-admit.js CONTAINER:/workspace/scripts/auto-admit.js

# Run inside the container
docker exec -d -e NODE_PATH=/app/vexa-bot/core/node_modules CONTAINER \
  sh -c 'node /workspace/scripts/auto-admit.js > /workspace/auto-admit.log 2>&1'
```

### Run via CDP from outside

```js
const { chromium } = require('playwright');
const browser = await chromium.connectOverCDP('http://localhost:8056/b/TOKEN/cdp');
const page = browser.contexts()[0].pages()[0]; // Google Meet page

// Admit all waiting guests
await page.evaluate(() => {
  // Click individual Admit button
  const buttons = document.querySelectorAll('button');
  for (const btn of buttons) {
    if (btn.textContent.trim() === 'Admit' && btn.offsetParent) {
      btn.click();
      return;
    }
  }
  // Or click green pill to open People panel
  const pills = document.querySelectorAll('div[role="button"]');
  for (const el of pills) {
    if (/Admit \d+ guest/.test(el.textContent) && el.offsetParent) {
      el.click();
    }
  }
});

// If confirmation dialog appears
await page.evaluate(() => {
  const ok = document.querySelector('button[data-mdc-dialog-action="ok"]');
  if (ok) ok.click();
});
```

### Google Meet admit flow (selectors reference)

| Element | Selector | Notes |
|---------|----------|-------|
| Green pill "Admit N guest(s)" | `div[role="button"]` matching `/Admit \d+ guest/` | Opens People panel |
| Individual "Admit" button | `button` with exact text "Admit" | Next to person's name, no dialog |
| "Admit all" link in panel | `div.qJDiDf` with text "Admit all" | Opens confirmation dialog |
| Dialog confirm button | `button[data-mdc-dialog-action="ok"]` | Confirms "Admit all?" dialog |
| Dialog cancel button | `button[data-mdc-dialog-action="cancel"]` | |

---

## Architecture

```
POST /bots { mode: "browser_session" }
      │
      ▼
bot-manager
│  generates session token
│  reads user.data.workspace_git (if configured)
│  starts vexa-bot with mode=browser_session
│  returns { url: "/b/{token}" }
│
      ▼
vexa-bot (browser session mode)
│  downloads browser data from MinIO
│  clones/pulls workspace from GitHub (or MinIO)
│  launchPersistentContext('/tmp/browser-data')
│  VNC (:6080) + CDP (:9223 via socat) exposed
│
│  Human: opens /b/{token} → noVNC in browser tab
│  Agent: connectOverCDP('/b/{token}/cdp') → Playwright
│
│  [Save] → git commit + push workspace (or S3 sync)
│         → S3 sync browser data (excludes cache)
│  container stays alive until stopped
```

### Container layout

```
/workspace/              ← user files, git-tracked (GitHub or MinIO)
├── scripts/
│   └── auto-admit.js
├── .git/                ← full git history
└── ...

/tmp/browser-data/       ← Chromium profile (MinIO, excludes cache)
├── Default/
│   ├── Cookies
│   ├── Local Storage/
│   ├── IndexedDB/
│   └── ...
└── Local State
```

### MinIO layout

```
s3://vexa-recordings/users/{id}/browser-userdata/
├── workspace/           ← user files (if not using GitHub)
│   ├── .git/
│   ├── scripts/
│   └── ...
└── browser-data/        ← Chromium profile (sans cache/journals)
    ├── Default/
    │   ├── Cookies
    │   ├── Local Storage/
    │   └── ...
    └── Local State
```

---

## API reference

### Browser session lifecycle

```
POST   /bots { mode: "browser_session" }
  → creates browser session, returns { id, data.session_token }

DELETE /bots/{platform}/{id}
  → stops browser session (existing endpoint)
```

### Browser access (token-authenticated, no API key needed)

```
GET  /b/{token}              → dashboard page (noVNC + toolbar)
WS   /b/{token}/vnc/websockify  → VNC WebSocket proxy
GET  /b/{token}/vnc/{path}   → noVNC static files proxy
WS   /b/{token}/cdp          → CDP WebSocket proxy
GET  /b/{token}/cdp/{path}   → CDP HTTP proxy (e.g. /json/version)
POST /b/{token}/save         → trigger storage save
```

### Workspace git configuration

```
PUT    /auth/workspace-git { repo, token, branch }
  → configure GitHub repo for workspace sync

DELETE /auth/workspace-git
  → remove git config, revert to MinIO
```

### Storage save (internal)

```
POST /bots/{id}/storage/save
  → trigger save (authenticated, for direct API use)

POST /internal/browser-sessions/{token}/save
  → trigger save (internal, used by gateway proxy)
```

---

## System requirements

| Resource | Per session |
|----------|------------|
| RAM | ~1-1.5 GB (Chromium + Xvfb + VNC) |
| CPU | 0.5 core idle, 1 core active |
| SHM | 2 GB |
| Disk | ~50 MB workspace + ~20 MB browser data (excludes cache) |
| Image size | +50 MB over base vexa-bot (VNC + awscli + git + socat) |
| MinIO | ~20-50 MB per user |

---

## Gate

One API call → one URL → everything works:

1. **Browser** — open URL → live Chromium via noVNC
2. **Agent** — `connectOverCDP(url + '/cdp')` → full Playwright API
3. **Storage** — Save → browser data + workspace persisted
4. **Persistence** — stop, restart → everything restored (accounts, files, git history)
5. **Scripts** — `/workspace/scripts/` runs inside container, persists across sessions

### Verified

- [x] Create session via API → get URL
- [x] Open URL → see live browser
- [x] Playwright CDP via gateway → navigate, type, screenshot
- [x] Authenticate Google account → profile persists across restarts
- [x] Workspace files persist across restarts
- [x] Git history preserved
- [x] Auto-admit script runs inside container
- [x] Individual Admit button click (no dialog needed)
