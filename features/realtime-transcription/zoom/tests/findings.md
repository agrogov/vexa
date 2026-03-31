# Zoom Realtime Transcription (Browser-Based) Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach next level |
|-------|-------|----------|-------------|---------------------|
| Browser navigates to Zoom web client | 0 | Not implemented | -- | Implement Playwright navigation to zoom.us/wc/join/{id} |
| Bot joins meeting via browser | 0 | Not implemented | -- | Handle name input, join button, waiting room in web client |
| Media element discovery | 0 | Not implemented | -- | Analyze Zoom web client DOM for audio/video elements per participant |
| Speaker identity locks | 0 | Not implemented | -- | Find Zoom speaking indicator selectors, implement voting |
| Audio reaches TX service | 0 | Not implemented | -- | ScriptProcessor capture -> TranscriptionClient -> HTTP 200 |
| Transcription content | 0 | Not implemented | -- | Non-empty text from Zoom meeting audio |
| WS delivery | 0 | Not implemented | -- | Live segments via WebSocket |
| REST /transcripts | 0 | Not implemented | -- | GET /transcripts returns segments with speaker names |
| GC prevention | 0 | Not implemented | -- | window.__vexaAudioStreams pattern (same as Meet/Teams) |
| Mock meeting works | 0 | Not implemented | -- | Create Zoom mock HTML, test with 3 speakers |

**Overall: 0/100** -- scaffold only, nothing implemented.

## Confidence Ladder

| Level | Gate |
|-------|------|
| 0 | Not implemented |
| 30 | Browser navigates to Zoom web client |
| 50 | Bot joins meeting, finds audio elements |
| 70 | Transcription works on mock |
| 80 | Transcription works on real meeting |
| 90 | Multiple meeting URLs |
| 95 | Browser-based replaces SDK approach |

## Open research

- Zoom web client DOM structure unknown -- needs live inspection at zoom.us/wc/join/{id}
- Unknown whether Zoom web client provides per-participant audio elements or mixed audio
- Unknown Zoom speaking indicator class names / selectors
- Unknown CAPTCHA or anti-bot measures on web client join
- Unknown waiting room behavior in web client vs SDK
