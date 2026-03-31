# /create-meeting — Create a real Google Meet for testing

Creates a new Google Meet meeting using an authenticated browser session, returns the meeting URL.

## Prerequisites
- Browser containers running: `docker compose -f /home/dima/dev/playwright-vnc-poc/docker-compose.yml up -d`
- CDP available at `localhost:9222` (browser-1)
- Google account signed in on browser-1. If not, VNC into `http://localhost:6080/vnc.html` and sign in manually.

## How it works

`meet.new` creates an instant meeting. Google auto-joins if the account is signed in — no "Join now" click needed.

```javascript
const { chromium } = require('playwright');
const browser = await chromium.connectOverCDP('http://localhost:9222');
const context = browser.contexts()[0];
const page = context.pages()[0] || await context.newPage();

await page.goto('https://meet.new', { waitUntil: 'networkidle', timeout: 30000 });

// If redirected to accounts.google.com → sign-in needed
// Otherwise: auto-creates and auto-joins the meeting
const meetingUrl = page.url(); // https://meet.google.com/xxx-yyyy-zzz

// Dismiss "Got it" dialog if shown
const gotIt = page.locator('button:has-text("Got it")');
if (await gotIt.isVisible({ timeout: 2000 }).catch(() => false)) await gotIt.click();

// Disconnect CDP without closing browser — meeting stays alive
await browser.close();
```

## Output
Log: `MEETING CREATED: https://meet.google.com/xxx-yyyy-zzz`

The bot joins with:
```bash
curl -s -X POST http://localhost:8056/bots \
  -H "X-API-Key: <token>" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"xxx-yyyy-zzz"}'
```

## Learned (2026-03-17)

- `meet.new` auto-joins if signed in — no need to click "Join now"
- "Microphone not found" warning is expected in VNC container (no audio hardware)
- Bot gets auto-admitted to non-locked meetings (no host admission needed)
- Browser-1 (port 6080/9222) has the Google account session
- Meeting stays alive as long as someone is in it — the host in the VNC browser

## Cleanup
Leave the meeting from the VNC browser or let it timeout.
