# Remote Browser — Findings

## Scaffold — 2026-03-18

Feature scaffolded from playwright-vnc-poc. No tests run yet.

### Known from PoC
- Chromium persistent context + VNC + CDP: **working** (tested in playwright-vnc-poc)
- Google/Teams auth via VNC: **working**
- Cookie persistence via Docker volumes: **working**
- CDP connect from outside container: **working** (socat proxy required)
- SingletonLock must be cleaned on restart or Chromium won't start
