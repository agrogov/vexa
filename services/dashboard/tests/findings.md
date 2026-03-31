# Dashboard Test Findings
Date: 2026-03-16 22:11:03
Mode: compose-full

## Summary
- PASS: 6
- FAIL: 1
- DEGRADED: 2
- UNTESTED: 0
- SURPRISING: 0

## Results
| Status | Test | Detail |
|--------|------|--------|
| PASS | Main page (GET /) | 200 |
| FAIL | Main page | HTTP 200 |
| PASS | HTML content valid | Contains Next.js markers |
| PASS | Static assets | 200 for /_next/static/chunks/de2480e4bd286b27.js |
| DEGRADED | API proxy | HTTP 404 |
| PASS | Login page | HTTP 200 |
| PASS | Docker logs | 0 error lines |
| PASS | Container stability | 0 restarts |
| DEGRADED | Dashboard route | HTTP 404 |

## Riskiest thing
API URL misconfiguration — dashboard loads but shows empty data if VEXA_API_URL is wrong.

## What was untested
- Full auth flow (needs browser/Playwright)
- WebSocket live transcript
- Recording playback
- Actual user interactions
