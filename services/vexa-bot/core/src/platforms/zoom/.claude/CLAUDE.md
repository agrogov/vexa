# Zoom Platform Agent

## Scope
Zoom SDK integration via shared meetingFlow pattern. Strategies: join, admission, prepare, recording, removal, leave.

## What you know
- index.ts: delegates to runMeetingFlow() with Zoom-specific PlatformStrategies.
- strategies/: join.ts, admission.ts, prepare.ts, recording.ts, removal.ts, leave.ts — each a standalone strategy.
- native/zoom_meeting_sdk/: proprietary SDK binaries (not in repo, must be provided).
- sdk-manager.ts: manages SDK lifecycle, OBF token auth (limited).
- Self-hosted only — not available on hosted service. Requires own Zoom Marketplace app.
- Web app mode (Playwright-based) in development — working code in strategies/src/, not released.

## Critical questions
- Are SDK binaries present in native/zoom_meeting_sdk/?
- Does the SDK initialize without errors? (sdk-manager.ts)
- Do all 6 strategies (join/admission/prepare/recording/removal/leave) execute without throwing?
- Web app mode: what's the completion state of strategies/src/?

## After every run
Update SDK binary status and strategy execution results.

## Diagnostic protocol
1. **Read last findings** (`tests/findings.md`) — what failed before? Start there.
2. **Fail fast** — test the riskiest thing first. If a dependency is down, everything above it fails. Check dependencies before dependents.
3. **Isolate** — when something fails, drill into WHY. Is it the service? The dependency? The network? The config? Don't report "Zoom bot failed" — report "Zoom bot failed because SDK binary missing in native/zoom_meeting_sdk/."
4. **Parallelize** — run independent checks concurrently. Don't wait for SDK init before checking strategy file presence.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

Dependencies to check first: SDK binaries present (native/zoom_meeting_sdk/), then SDK initialization (sdk-manager.ts), then OBF token auth. If SDK init fails, check binary presence and platform compatibility before looking at strategy code.

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
