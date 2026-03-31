# /create-meeting — Create a real MS Teams meeting for testing

Creates an MS Teams meeting using an authenticated browser session, returns the meeting URL.

## Prerequisites
- Browser containers running: `docker compose -f /home/dima/dev/playwright-vnc-poc/docker-compose.yml up -d`
- Microsoft/Teams account signed in on **browser-1** (port 6080/9222). Not browser-2.
- If not signed in, VNC into `http://localhost:6080/vnc.html` and sign in to teams.microsoft.com manually.

## How it works

Teams has NO `teams.new` shortcut. You must navigate to the Meet section and create a link.

### Step 1: Create meeting link (browser-1, organizer)

```javascript
const { chromium } = require('playwright');
// NOTE: Playwright connectOverCDP may timeout on heavy browser sessions.
// If it does, fall back to raw CDP: http://localhost:9222/json
const browser = await chromium.connectOverCDP('http://localhost:9222');
const context = browser.contexts()[0];
const page = context.pages()[0] || await context.newPage();

// Navigate to Teams
await page.goto('https://teams.microsoft.com', { waitUntil: 'load', timeout: 30000 });

// Click Meet in sidebar
await page.locator('[data-tid="app-bar-Meet"], button:has-text("Meet")').click();

// Click "Create a meeting link"
await page.locator('button:has-text("Create a meeting link")').click();

// Name the meeting
await page.locator('input[placeholder*="meeting"]').fill('Test Meeting');
await page.locator('button:has-text("Create and copy link")').click();

// Get the link from clipboard or page
// Link format: https://teams.live.com/meet/<ID>?p=<PASSWORD>

// Join as organizer
await page.locator('button:has-text("Start meeting")').click();
```

### Step 2: Join as guest (browser-2, for testing bot)

This is optional — the bot joins directly via API. But if you need a second participant:

```javascript
const browser2 = await chromium.connectOverCDP('http://localhost:9224');
const context2 = browser2.contexts()[0];
const page2 = context2.pages()[0] || await context2.newPage();

// Guest join — no auth needed
await page2.goto('https://teams.live.com/meet/<ID>?p=<PASSWORD>');
await page2.locator('input[placeholder*="name"]').fill('Guest');
await page2.locator('button:has-text("Join now")').click();
// Guest lands in lobby — organizer must admit from browser-1
```

### Step 3: Admit guest (browser-1)

The organizer must click the admit button when a guest is in the lobby.

## Output
Log: `MEETING CREATED: https://teams.live.com/meet/<ID>?p=<PASSWORD>`

The bot joins with:
```bash
curl -s -X POST http://localhost:8056/bots \
  -H "X-API-Key: <token>" \
  -H "Content-Type: application/json" \
  -d '{"platform":"teams","native_meeting_id":"<ID>","meeting_url":"https://teams.live.com/meet/<ID>?p=<PASSWORD>"}'
```

## Learned (2026-03-17)

- Teams has NO `teams.new` — must use Meet sidebar → "Create a meeting link"
- Guest join works without authentication via the meeting link
- Guests go through lobby — organizer must admit them
- Browser-1 (port 6080/9222) has the Teams session (Dmitry Grankin account), NOT browser-2
- Browser-2 (port 6081/9224) had no Teams session — used it for guest join
- Playwright `connectOverCDP` may timeout on browser-1 due to heavy Google/Stripe iframe targets — fall back to raw CDP if needed
- Meeting link format: `https://teams.live.com/meet/<NUMERIC_ID>?p=<PASSWORD_STRING>`
- Both organizer and guest appear in meeting: "In this meeting (2)"

## Cleanup
Leave the meeting from both browsers when testing is done.
