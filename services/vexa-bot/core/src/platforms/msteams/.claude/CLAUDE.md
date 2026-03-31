# Microsoft Teams Platform Agent

## Scope
Teams bot integration. Playwright-based join, media warm-up, mixed audio routing, DOM-based speaker detection.

## What you know
- join.ts: warmUpTeamsMediaDevices() before join, waitForTeamsPreJoinReadiness(), then name input → join.
- Single mixed RTCPeerConnection — speaker identity via DOM active speaker detection + voting/locking.
- selectors.ts: continue button, join button, camera/video options, name input, audio radio buttons, speaker enable/disable.
- teams.live.com links verified working. Enterprise links untested — auth policies may block unauthenticated guest.
- 0% failure rate in current production, but open issues #171, #189, #190, #191.
- Media warm-up: getUserMedia({audio:true, video:true}) then stop tracks — primes browser permissions.

## Critical questions
- Does teams.live.com join still work end-to-end?
- Does speaker detection resolve names with 3+ participants? (mixed audio makes this harder)
- What happens with enterprise meeting links? (org policy blocks)
- Are selectors still valid against current Teams web UI?

## After every run
Update findings. Track selector drift and enterprise link behavior.

## Diagnostic protocol
1. **Read last findings** (`tests/findings.md`) — what failed before? Start there.
2. **Fail fast** — test the riskiest thing first. If a dependency is down, everything above it fails. Check dependencies before dependents.
3. **Isolate** — when something fails, drill into WHY. Is it the service? The dependency? The network? The config? Don't report "Teams join failed" — report "Teams join failed because media warm-up threw because getUserMedia denied by browser permissions."
4. **Parallelize** — run independent checks concurrently. Don't wait for join flow before checking selector validity.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

Dependencies to check first: DOM selectors (Teams UI changes), then media warm-up (getUserMedia permissions), then RTCPeerConnection. If join works but no audio, check media warm-up and mixed audio routing before blaming speaker detection.

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
