# vexa-bot changes

## Dockerfile — Infobip corporate network support
- Stage 1 (`native-builder`): switched base image from public `node:20-bullseye` to `docker.ib-ci.com/node:20-bullseye`; added Infobip Root CA cert + `NODE_EXTRA_CA_CERTS` so node-gyp can pull packages through SSL inspection proxy
- Stages 2 & 3 (ts-builder / runtime): added Infobip Root CA cert injection to fix `npm install` failures behind corporate SSL inspection
- Added `mkdir -p /app/vexa-bot/build` before native addon build so the subsequent `COPY --from=native-builder` doesn't fail when Zoom SDK is absent (no build/ dir created)

## msteams/join.ts — Teams light experience join fix
- `waitForTeamsPreJoinReadiness`: added DOM presence check (`getElementById`, `querySelector[data-tid]`, `querySelector[aria-label]`) as fallback to `isVisible()` — the light-meetings experience renders the button in the DOM before Playwright considers it visible
- Step 6 join click: replaced Playwright `isVisible()` + `.click()` with JS `page.evaluate` click as primary path (bypasses Playwright visibility checks entirely); Playwright `force: true` click as fallback
- Added button dump debug logging in the catch block: dumps all visible buttons with tag/text/aria-label/data-tid/id to help diagnose future selector mismatches

## msteams/selectors.ts — expanded join button selectors
- Added `data-tid` based selectors (`prejoin-join-button`, `*join-button*`, `*join_button*`) first — most reliable across both full and light experience
- Added `aria-label` variants (`Join now`, `Join meeting`, wildcards)
- Kept text-based selectors as last resort
- Removed ambiguous bare `button:has-text("Join")` (too broad)

## msteams/leave.ts — Teams light experience leave fix
- Rewrote leave sequence: JS click first (bypasses overlay/z-index blocking Playwright's native click in light experience), Playwright `force: true` as fallback, `performLeaveAction` as last resort

## msteams/recording.ts — Teams speaker grace window + silence threshold
- Added `SPEAKER_GRACE_MS` grace window (read from `botConfigData.teamsSpeakingKeepaliveMs`, default 8000ms): routes audio to the last known speaker for up to N ms after their `SPEAKER_END` event, fixing 30-60s transcription gaps caused by Teams DOM speaker state flapping between every word
- Lowered silence threshold: `maxVal <= 0.005` → `maxVal <= 0.001` to capture quieter speech frames

## core/src/utils/browser.ts — unblock paused audio elements
- Added `play()` call on paused media elements that have a valid MediaStream with audio tracks; Teams light experience can leave elements paused after admission, silently blocking audio capture
