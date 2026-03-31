# Post-Meeting Transcription Test Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Deferred transcription triggers | 0 | Not tested | — | End meeting, verify TC starts deferred processing |
| Full recording re-transcribed | 0 | Not tested | — | Check transcription-service receives full recording |
| SPLM runs on output | 0 | Not tested | — | Verify speaker-language mapping executes |
| Speaker mapping >=70% | 0 | Not tested | — | Compare speaker names to known source, measure accuracy |
| Postgres updated | 0 | Not tested | — | Query DB before/after, confirm transcript replaced |
| API serves improved version | 0 | Not tested | — | GET /transcripts returns post-meeting version, not real-time |
