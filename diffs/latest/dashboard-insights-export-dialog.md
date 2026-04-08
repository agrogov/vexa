# feat(dashboard): export Decisions and Anthology via insights export dialog

## Commit title
`feat(dashboard): add insights export dialog for Decisions and Anthology (TXT, JSON, MD)`

## Description

Previously there was no way to export detected insights from a meeting — only the transcript could be exported. This change adds a single **"Export insights…"** entry to the existing Export dropdown that opens a modal dialog where the user selects what to export and in which format, then triggers a download.

### UI/UX

- The "Export insights…" dropdown item is **only rendered** when `config.decisionListenerUrl` is set in runtime config — deployments without the decision-listener configured see no change to the Export menu.
- Clicking the item opens a `Dialog` (Radix, `ui/dialog.tsx`) with:
  - **What** toggle: Decisions / Anthology
  - **Format** toggle: .txt / .json / .md
  - **Export** button with loading spinner — fetches on demand, downloads, closes dialog
- Empty-data guard: shows `toast.info` and keeps dialog open if no data is available yet.
- Service unreachable: caught, `toast.error`, dialog stays open for retry.

### `services/dashboard/src/lib/export.ts`

Six new pure export functions appended (no existing code touched):

| Function | Output |
|---|---|
| `exportDecisionsToTxt` | `=====` header, `[Type Label]` blocks, speaker/confidence when present |
| `exportDecisionsToJson` | `{ meeting, decisions: [{type, summary, speaker?, confidence?}], exported_at }` |
| `exportDecisionsToMd` | `# Live Decisions`, `## Items`, `### Type` per item |
| `exportAnthologyToTxt` | Same as decisions TXT + optional SUMMARY block + entity lines per item |
| `exportAnthologyToJson` | `{ meeting, summary: {lede, theme}\|null, items: [{...entities}], exported_at }` |
| `exportAnthologyToMd` | `# Anthology`, optional `## Summary`, `## Items` with entity backtick list |

Also added:
- `ExportDecisionItem`, `ExportAnthologyItem`, `ExportSummaryData` — exported types used by both export functions and page handlers.
- `generateDecisionsFilename` → `decisions-YYYY-MM-DD-{id}.{ext}`
- `generateAnthologyFilename` → `anthology-YYYY-MM-DD-{id}.{ext}`

All functions follow the existing `exportToTxt` header/footer style. `speaker`/`confidence` are omitted from JSON when undefined (no null keys).

### `services/dashboard/src/app/meetings/[id]/page.tsx`

- Added `useRuntimeConfig` hook and `Dialog`/`DialogContent`/`DialogHeader`/`DialogTitle`/`DialogFooter` imports.
- 4 new state vars: `insightsExportOpen`, `insightsExportType`, `insightsExportFormat`, `insightsExportLoading`.
- `handleExportInsights` callback: fetches `/decisions/{id}/all` (decisions) or both `/decisions/{id}/all` + `/summary/{id}` in parallel (anthology), formats, and triggers download.
- Both Export dropdowns (toolbar and mobile) get the same conditional item — wrapped in `{config?.decisionListenerUrl && ...}`.
- `Dialog` JSX placed once at the bottom of the component return.

### Data verified
Export of meeting 168 (56 items) confirmed: exported file count matches Redis (56) and Postgres (56).
