# Real Google Meet DOM vs Mock Page — Comparison

Captured: 2026-03-17 from live meeting at meet.google.com/cxi-ebnp-ixk
Single participant (self): Dmitriy Grankin

## 1. Participant Tile Structure

### Real Meet
```html
<div jsname="E2KThb" tabindex="-1" class="oZRSLe"
     jscontroller="K3Z5Df"
     data-participant-id="spaces/1WRTcuGyP40B/devices/97"
     data-requested-participant-id="spaces/1WRTcuGyP40B/devices/97"
     data-tile-media-id="spaces/1WRTcuGyP40B/devices/97"
     jsaction="...">
  <div class="FKJK2b ZrmAYe" style="--tile-primary-dark: ...">
    <div class="CNjCjf iPFm3e">
      <div class="koV58 Zi94Db" jscontroller="dTVdqe" data-resolution-cap="0" data-layout="roi-crop">
        <div class="knW4sf OvyUed">
          <div class="T4q2od iPFm3e">
            <img class="m0DVAf" src="..." crossorigin="use-credentials">
            <div class="D3ywUe"></div>
            <div class="qRU4mf uSECwd JTEhGf iPFm3e">
              <div class="sCE0Tb"></div>
              <div class="DYfzY cYKTje gjg47c" jsname="QgSmzd"></div>  <!-- SPEAKING INDICATOR -->
              <div class="qg7mD r6DyN xm86Be JBY0Kc eXUaib KXY1yb">
                <img class="SOQwsf" src="...">  <!-- Avatar -->
              </div>
            </div>
          </div>
        </div>
        <div class="LBDzPb">...</div>  <!-- Name overlay area -->
      </div>
    </div>
  </div>
</div>
```

### Mock Page
```html
<div class="participant" data-participant-id="1">
  <div class="participant-name">Alice Johnson</div>
  <audio id="audio-alice" src="alice.wav"></audio>
</div>
```

### DISCREPANCIES:
- **Tag/class mismatch**: Real uses `class="oZRSLe"` on the `data-participant-id` div. Mock uses `class="participant"`.
- **Participant ID format**: Real uses `spaces/1WRTcuGyP40B/devices/97`. Mock uses simple integers `"1"`, `"2"`, `"3"`.
- **Additional attributes**: Real has `data-requested-participant-id`, `data-tile-media-id`, `jscontroller`, `jsname`, `jsaction`. Mock has none of these.
- **Nesting depth**: Real has ~6 levels of nesting. Mock has flat structure.
- **Speaking indicator div**: Real has a `<div class="DYfzY cYKTje gjg47c">` inside the tile. Mock has nothing.

## 2. Media Elements (Audio)

### Real Meet
- 3 `<audio>` elements, all with:
  - **No `id`** (empty string)
  - **No `src`** (empty string)
  - **`srcObject` = true** (MediaStream with WebRTC audio tracks)
  - **`paused` = true** (Google Meet keeps them paused; audio plays via WebRTC)
  - **`autoplay` = false**
  - Each has exactly 1 audio track with unique UUID-based `id`

### Mock Page
- 3 `<audio>` elements with:
  - **Has `id`** (`audio-alice`, `audio-bob`, `audio-carol`)
  - **Has `src`** (file paths: `alice.wav`, `bob.wav`, `carol.wav`)
  - **`srcObject` = null** (uses file source, not MediaStream)
  - **`paused` varies** (depends on autoplay)

### DISCREPANCIES:
- **Audio elements are NOT inside participant tiles in real Meet**. They appear to be standalone in the DOM, separate from the `[data-participant-id]` containers. The mock nests them inside `.participant` divs.
- **Real Meet uses `srcObject` (MediaStream) not `src` (file URL)**. The mock uses file sources. This matters for `captureStream()` behavior.
- **Real Meet audio elements have no `id`**. The mock relies on IDs for identification.

## 3. Toolbar Buttons (aria-labels)

### Real Meet toolbar aria-labels (in order):
1. "Backgrounds and effects"
2. "Can't remove your tile in this layout"
3. "More options for Dmitriy Grankin"
4. "This call is open to anyone"
5. "Audio settings"
6. **"Turn off microphone"** (mic control)
7. "Video settings"
8. **"Camera problem. Show more info"** (camera control)
9. **"Share screen"**
10. "Send a reaction"
11. **"Turn on captions"**
12. **"Raise hand (Ctrl + alt + h)"**
13. "More options"
14. **"Leave call"** (critical for bot)
15. **"Meeting details"**
16. **"Chat with everyone"**
17. **"Meeting tools"**
18. **"Host controls"**
19. "Your call is ending soon"
20. "Close"
21. "Copy link"

### Mock Page
- No toolbar at all.

### DISCREPANCY:
- Mock has zero toolbar buttons. The bot uses these for admission detection (`Leave call`, `Turn off microphone`, `Chat`, etc.) and leaving meetings.

## 4. Speaking Class Names

### Real Meet (present in live DOM):
- `gjg47c`: **2 instances found** (this is the SILENCE class, confirmed)
- `Oaajhc`: 0 (speaking class — not present because nobody was speaking at capture time)
- `HX2H7`: 0
- `wEsLMd`: 0
- `OgVli`: 0

### Bot selectors.ts configuration:
- Speaking classes: `Oaajhc`, `HX2H7`, `wEsLMd`, `OgVli`
- Silence classes: `gjg47c`

### Key finding:
- The speaking indicator div is `<div class="DYfzY cYKTje gjg47c">` — class `gjg47c` is indeed the silence state.
- When speaking, this div likely switches to include `Oaajhc` (or similar) instead of `gjg47c`.
- The mock page has NO speaking indicator elements at all.

## 5. Name Element Structure

### Real Meet
```html
<span class="notranslate">Dmitriy Grankin</span>
```
- Tag: `SPAN`
- Class: `notranslate` (with no other classes on the primary name span)
- Parent class: empty (varies)
- Additional name-like spans exist with classes `notranslate cR8Azd bkl1qf` and `notranslate zYrqtc thO1y` but these are empty text (likely for other participants or UI elements).
- Many `<i class="... notranslate ...">` elements exist for icon fonts (material icons), NOT participant names.

### Mock Page
```html
<div class="participant-name">Alice Johnson</div>
```
- Tag: `DIV` (not SPAN)
- Class: `participant-name` (not `notranslate`)
- No nesting relationship to data-participant-id tile

### DISCREPANCIES:
- Bot uses `span.notranslate` as PRIMARY name selector (line 322 in recording.ts). Mock uses `div.participant-name`. This won't match.
- Bot also falls back to `.participant-name` selector (googleNameSelectors line 209), so the mock's class WILL match as a fallback. However, the primary selector misses.

## 6. role="toolbar" Structure

### Real Meet
- **Zero `[role="toolbar"]` elements found!** (toolbars array is empty)
- The bot checks for `[role="toolbar"]` as an admission indicator. In this capture, it was not present, yet the meeting was clearly active.
- Buttons exist but are NOT wrapped in a `role="toolbar"` container.

### DISCREPANCY:
- The bot's admission detection relies partly on `[role="toolbar"]` which may not always be present. This is a potential false-negative for admission detection.

## 7. Missing Attributes in Real DOM

### Not found in real Meet:
- `data-meeting-id` — 0 elements
- `data-call-id` — 0 elements
- `data-self-name` — 0 elements
- `[data-audio-level]` — not checked but likely absent

### Present in real Meet but not in mock:
- `data-requested-participant-id`
- `data-tile-media-id`
- `jsname`, `jscontroller`, `jsmodel`, `jsaction` (Google Closure attributes)
- CSS custom properties on tiles (`--tile-primary-dark`, etc.)

## Summary of Critical Discrepancies for Mock Page

| Feature | Real Meet | Mock Page | Impact |
|---------|-----------|-----------|--------|
| Participant container class | `oZRSLe` | `participant` | Bot finds via `[data-participant-id]` — works in both |
| Participant ID format | `spaces/.../devices/97` | `"1"` | OK for testing, but format differs |
| Audio inside participant tile | NO (separate) | YES (nested) | Mock's `el.closest('.participant')` works but is unrealistic |
| Audio source | `srcObject` (MediaStream) | `src` (file URL) | Different capture behavior |
| Name element | `span.notranslate` | `div.participant-name` | Primary selector misses; fallback works |
| Speaking indicator div | `<div class="DYfzY cYKTje gjg47c">` | None | No speaking detection possible in mock |
| Toolbar buttons | 20+ buttons with aria-labels | None | Admission detection won't work in mock |
| Nesting depth | ~6 levels | 1 level | DOM traversal differs |
