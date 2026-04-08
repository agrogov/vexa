# fix(dashboard): prevent crash on meeting detail page for unknown platforms

## Commit title
`fix(dashboard): prevent crash on meeting detail page for unknown platforms`

## Description
`PLATFORM_CONFIG` only covers `google_meet`, `teams`, and `zoom`. Browser session
meetings (`platform="browser_session"`) caused a client-side crash because
`PLATFORM_CONFIG["browser_session"]` is `undefined`, and the page immediately
dereferenced `platformConfig.name` / `.color` etc. without a null check.

Added a `??` fallback with neutral gray styles and the raw platform string
as the display name, so unknown platforms render gracefully and the page
remains functional (delete, export, etc.).

### Change (`meetings/[id]/page.tsx`, line 803)

```ts
// Before — crashes on unknown platform:
const platformConfig = PLATFORM_CONFIG[currentMeeting.platform];

// After — falls back to generic config:
const platformConfig = PLATFORM_CONFIG[currentMeeting.platform as keyof typeof PLATFORM_CONFIG] ?? {
  name: currentMeeting.platform ?? "Unknown",
  color: "bg-gray-500",
  textColor: "text-gray-700",
  bgColor: "bg-gray-50",
  icon: "video",
};
```

### Affected meetings
Any meeting with `platform` not in `PLATFORM_CONFIG` — currently: `browser_session`.
These are created by the Dashboard Browser page and accumulate as stale active meetings
when the browser session is not properly closed.
