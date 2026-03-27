# Fix: MS Teams bot join/leave reliability for "light meetings" experience

## PR Title
`fix(vexa-bot): improve MS Teams join/leave reliability in light-meetings experience`

## PR Description

### Problem

Microsoft Teams has two rendering modes: the full SPA experience and a lighter "light-meetings"
experience served to certain clients/tenants. In the light experience:

- The pre-join "Join now" button is present in the DOM but Playwright's `isVisible()` returns
  `false`, so the bot never clicked the button and timed out at the pre-join screen.
- The leave (`#hangup-button`) is overlaid by a `ui-dialog__overlay` element, causing Playwright's
  native `.click()` to intercept-fail even though the button is technically in the DOM.
- Audio tracks on remote participants' `<video>` elements may be `enabled=false` or `muted=true`
  while Teams initialises the stream. The previous code rejected those elements, so no audio was
  captured until tracks became enabled — or at all, if Teams never toggled the flag.
- The `teamsJoinButtonSelectors` list only contained text-based selectors which don't match in the
  light experience.

### Fix

**`services/vexa-bot/core/src/platforms/msteams/join.ts`**
- `waitForTeamsPreJoinReadiness`: added a DOM-presence check via `page.evaluate` that looks for
  `#prejoin-join-button`, `[data-tid="prejoin-join-button"]`, and `[aria-label="Join now"]`.
  Readiness is declared if any of these are in the DOM, even if not visible.
- Step 6 join click: primary path is now a JS `btn.click()` via `page.evaluate` (bypasses
  Playwright visibility gates). Fallback uses `{ force: true }` on the locator.
- On join failure: dumps all visible buttons (tag, text, aria-label, data-tid, id) to the log to
  aid selector debugging without requiring SSH/container access.

**`services/vexa-bot/core/src/platforms/msteams/leave.ts`**
- Primary leave path is now a JS `btn.click()` via `page.evaluate`, iterating over
  `#hangup-button`, `[data-tid="hangup-main-btn"]`, `[aria-label="Leave"]`, and the full
  `teamsLeaveSelectors` list. Returns on first successful click.
- First fallback: Playwright `hangupButton.click({ force: true })` — bypasses overlay interception.
- Second fallback: existing `performLeaveAction` window function (unchanged behaviour).

**`services/vexa-bot/core/src/platforms/msteams/selectors.ts`**
- `teamsJoinButtonSelectors`: prepended `data-tid` selectors (`[data-tid="prejoin-join-button"]`,
  `[data-tid*="join-button"]`, `[data-tid*="join_button"]`) and `aria-label` selectors before the
  text-based ones. Text-based selectors retained as last resort.

**`services/vexa-bot/core/src/utils/browser.ts`**
- Before filtering media elements, iterates all `<audio>`/`<video>` elements and calls `play()`
  on any that are `paused` and have a `MediaStream` with audio tracks. This unblocks audio capture
  in the light-meetings experience where elements are left paused after bot admission.
- Removed the `enabled && !muted` track filter that was rejecting valid stream elements. Track
  `muted` is a read-only browser property that is `true` when no audio is flowing (transient);
  `enabled=false` can occur transiently during Teams stream initialisation. Both states resolve
  once audio starts flowing. The AudioContext captures correctly regardless.
- Added diagnostic log line showing `enabled`/`muted` counts per element instead of rejecting.

## Files Changed

| File | Change |
|------|--------|
| `services/vexa-bot/core/src/platforms/msteams/join.ts` | DOM-presence readiness check; JS-click primary join path; failure button dump |
| `services/vexa-bot/core/src/platforms/msteams/leave.ts` | JS-click primary leave path; force-click fallback |
| `services/vexa-bot/core/src/platforms/msteams/selectors.ts` | Prepend data-tid and aria-label selectors to join selector list |
| `services/vexa-bot/core/src/utils/browser.ts` | play() paused elements on start; remove muted/enabled track filter; add diagnostic log |
