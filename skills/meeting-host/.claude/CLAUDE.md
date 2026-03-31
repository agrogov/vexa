# meeting_host skill

## Confidence ladder

| Score | Gate | What it proves |
|-------|------|----------------|
| 30 | `url_obtained` | Meeting URL captured from API |
| 50 | `organizer_in` | Organizer is in meeting (hangup button visible) |
| 70 | `one_admitted` | 1 bot admitted via auto-admit |
| 80 | `two_admitted` | 2 bots admitted within 40s |
| 90 | `5x_clean` | 5 consecutive runs, no manual intervention |
| 95 | `10x_clean` | 10 consecutive runs, no flakes |
| 99 | `20x_clean` | 20 consecutive runs, no flakes, no intervention |

**Current: 90** — gates `url_obtained` through `5x_clean` passed. Evidence: meetings 9383926870133, 9351292554180, 9349463533815, 9311134017647, 5+ consecutive runs with MutationObserver admit in ~20s (2026-03-18). Next: 10 consecutive logged runs for 95.

## Why

Testing bots requires a human to host the meeting and admit them from the lobby. This skill replaces the human host — it creates the meeting, prints the join URL, and admits anyone who arrives.

## What

1. Creates a Teams meeting via CDP (Meet sidebar → Create a meeting link → join as organizer)
2. Prints the join URL
3. Runs an admit loop forever — anyone who arrives in the lobby gets admitted instantly

That's it.

## How

```bash
# Create new meeting
node run.js

# Reuse existing meeting (organizer must already be in)
node run.js --meeting-url <URL>
```

Output:
```
============================================================
MEETING URL: https://teams.live.com/meet/9383926870133?p=xxx
============================================================
```

Press Ctrl+C to stop.

## What we learned

- Meeting URL captured from `schedulingService/create` API response (Service Workers bypass `page.route` — must use `page.on('response', ...)`)
- Organizer browser at `localhost:9222`, connected via `chromium.connectOverCDP`
- Teams consumer keeps organizer at `/v2/` while call runs — organizer must be ACTIVELY IN the meeting (hangup button visible) for lobby notifications to appear
- Teams admit flow: "View Lobby" button appears first → click it → "Admit" / "Admit all" appear
- MutationObserver catches the button the instant it appears in DOM
- Backup poll every 2s as safety net
- Teams lobby bypass is impossible for anonymous/unauthenticated users — auto-admit is the only solution
- Playwright module: `/home/dima/dev/playwright-vnc-poc/node_modules/playwright`
