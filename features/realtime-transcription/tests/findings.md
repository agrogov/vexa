# Realtime Transcription Test Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Bot joins 3-speaker mock (Google Meet) | 90 | 3 speakers found, all locked permanently at 100% | 2026-03-16 | Retest with fresh stack |
| Per-speaker audio captured | 90 | 3 ScriptProcessors active, audio reaching handlePerSpeakerAudioData | 2026-03-16 | -- |
| Speaker identity locks correctly | 90 | Alice/Bob/Carol all locked (3/3 votes, 100% ratio) | 2026-03-16 | -- |
| Transcription returns text | 90 | HTTP 200 with non-empty text from transcription-service | 2026-03-16 | -- |
| Segments in Redis Hash | 90 | 7 segments in meeting 8791 Redis Hash | 2026-03-16 | -- |
| Segments persist to Postgres | 90 | 7 segments returned via GET /transcripts | 2026-03-16 | -- |
| Live segments via WebSocket | 0 | Not tested | -- | Connect wscat during active meeting, verify segments arrive |
| WS and REST consistency | 0 | Not tested | -- | Compare WS segments to GET /transcripts -- same text, same speakers |
| VAD filters silence | 80 | No empty-text segments in output (indirect) | 2026-03-16 | Feed silent audio, verify zero segments |
| End-to-end latency | 0 | Not tested | -- | Measure speech-to-WS-arrival, expect <5s |
| MS Teams pipeline | 0 | Teams mock does not exist | -- | Build Teams mock, test full pipeline |

## Platform Status

| Platform | Gate Status | Bottleneck |
|----------|-----------|------------|
| Google Meet | PASS (degraded: WS untested) | WebSocket live delivery at score 0 |
| MS Teams | FAIL | No mock meeting -- all checks at 0 |

## Aggregate: Lowest score = 0 (WS delivery + Teams)

Gate verdict: **FAIL** -- WebSocket live delivery untested, Teams pipeline entirely untested.

## Action Items

1. Connect wscat during active Google Meet mock and verify segments arrive in real-time
2. Compare WS output to REST /transcripts output for consistency
3. Build Teams mock meeting with `voice-level-stream-outline` + `vdi-frame-occlusion` DOM signals
4. Test Teams pipeline end-to-end once mock exists
