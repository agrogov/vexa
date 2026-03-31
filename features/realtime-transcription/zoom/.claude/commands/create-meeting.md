# /create-meeting -- Create a Zoom meeting for testing

Creates a new Zoom meeting using an authenticated browser session or Zoom API, returns the meeting URL.

## Prerequisites
- Browser containers running: `docker compose -f /home/dima/dev/playwright-vnc-poc/docker-compose.yml up -d`
- Browser-3 allocated for Zoom: CDP at `localhost:9226`, VNC at port `6082`
- Zoom account signed in on browser-3. If not, VNC into `http://localhost:6082/vnc.html` and sign in at zoom.us manually.

## Option A: Browser-based (CDP)

Sign in to zoom.us on browser-3, then create a meeting via CDP.

```javascript
const { chromium } = require('playwright');
const browser = await chromium.connectOverCDP('http://localhost:9226');
const context = browser.contexts()[0];
const page = context.pages()[0] || await context.newPage();

// Navigate to Zoom and host a meeting
await page.goto('https://zoom.us/meeting#/upcoming', { waitUntil: 'networkidle', timeout: 30000 });

// If redirected to sign-in -> authentication needed via VNC
// Otherwise: click "Host a Meeting" -> "With Video Off" (or "With Video On")
// Alternative: use the personal meeting room link from profile

// Get the meeting ID from the created meeting
const meetingUrl = page.url(); // https://zoom.us/j/1234567890

// Disconnect CDP without closing browser -- meeting stays alive
await browser.close();
```

## Option B: Zoom API (OAuth)

If Zoom API credentials are available (OAuth app on Zoom Marketplace):

```bash
# Create meeting via Zoom REST API
curl -X POST "https://api.zoom.us/v2/users/me/meetings" \
  -H "Authorization: Bearer ${ZOOM_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Vexa Test Meeting",
    "type": 1,
    "settings": {
      "join_before_host": true,
      "waiting_room": false
    }
  }'
# Returns: { "join_url": "https://zoom.us/j/1234567890?pwd=..." }
```

## Bot joins via web client

The bot does NOT use the SDK. It joins via the Zoom web client:

```
https://zoom.us/wc/join/{meeting_id}
```

This URL opens the Zoom web client in the browser -- no download needed, no SDK. The bot enters the meeting as a browser participant, same as Google Meet and Teams.

```bash
curl -s -X POST http://localhost:8056/bots \
  -H "X-API-Key: <token>" \
  -H "Content-Type: application/json" \
  -d '{"platform":"zoom","native_meeting_id":"1234567890"}'
```

## Key notes

- Zoom web client at `zoom.us/wc/join/{id}` allows browser-based join without SDK
- Zoom requires an account to CREATE meetings (unlike Google Meet's `meet.new` which auto-creates)
- Some meetings may have "waiting room" enabled -- host must admit from VNC browser
- Passcode-protected meetings: append `?pwd=...` to the web client URL
- Browser-3 (CDP localhost:9226, VNC port 6082) is designated for Zoom to avoid session conflicts with Meet (browser-1) and Teams (browser-2)

## Not yet implemented

This is a scaffold. The actual CDP automation for Zoom meeting creation and the browser-based bot join flow have not been built yet. The code snippets above are the target design.

## Cleanup

End the meeting from the VNC browser or let it timeout when all participants leave.
