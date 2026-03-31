# Current — Findings

## Bot defaults verified

| Default | Google Meet | Teams | Evidence |
|---------|-----------|-------|----------|
| Silent mic (tts_sink muted) | ✅ | ✅ | pactl get-sink-mute tts_sink = yes |
| No camera | ✅ | ✅ | Camera turned off in join flow |
| No video block | ✅ (active) | ✅ (skipped — breaks audio) | Video block on GMeet, skipped on Teams |
| TTS /speak works | ✅ | ✅ | "Oh my god, one two three" transcribed |
| Bot stays alive | ✅ 15+ min | ✅ 11+ min | Alone-timeout fixed |

## Transcription confidence

| Platform | Score | Evidence | Blocker |
|----------|-------|----------|---------|
| Google Meet | 92 | 9/10 utterances, speaker 100% | TTS pronunciation of technical terms |
| Teams | 87 | 5/5 captured, avg 87% accuracy | Start clipping (2-3 words), cross-utterance bleed |

## Teams 5-utterance validation (2026-03-17)

| # | Sent | Transcribed | Accuracy |
|---|------|-------------|----------|
| 1 | "Hello this is a test of Teams transcription..." | "...a test of Teams transcription. The deployment is scheduled for Friday." | 85% |
| 2 | "The quarterly report shows a fifteen percent increase..." | "quarterly report shows a 15% increase in revenue compared to last year." | 95% |
| 3 | "We need to finalize the design documents before the end of the sprint on Wednesday." | "We need to finalize the design documents before the end of the sprint." | 90% |
| 4 | "The new machine learning model achieved ninety seven percent accuracy..." | "Wednesday. Gene learning model achieved 97% accuracy on the test data set." | 70% |
| 5 | "Please schedule a follow up meeting with the infrastructure team..." | "Schedule a follow-up meeting with the infrastructure team for next Monday afternoon." | 95% |

## Teams 5-utterance retest after unmute delay 500ms/300ms (2026-03-17 19:28)

Bots: 8975 (Speaker), 8976 (Listener). Meeting 9320087910670.

| # | Sent | Transcribed (merged segments) | Accuracy |
|---|------|-------------------------------|----------|
| 1 | "Hello everyone welcome to the weekly infrastructure review meeting." | "Hello everyone, welcome to the Glee Infrastructure Review Meeting." | 85% — "weekly" hallucinated as "Glee" |
| 2 | "The quarterly report shows fifteen percent revenue growth year over year." | "The quarterly report shows 15% revenue growth year over year" | 95% — minor truncation |
| 3 | "We need to finalize the database migration plan before Friday." | "we need to finalize the database migration plan before Friday." | 100% |
| 4 | "The new monitoring system detected three critical alerts last night." | "The new monitoring system detected three critical alerts last night." | 100% |
| 5 | "Please schedule a follow up meeting for next Monday at two PM." | "Please schedule a follow-up meeting for next Monday at 2 p.m." | 100% |

**Average accuracy: 96%** (up from 87%)

### What improved
- **Zero start clipping** — 500ms pre-unmute delay fixed it completely. All 5 utterances begin cleanly.
- **No cross-utterance bleed** — 300ms post-mute delay + 12s gap eliminated the "Wednesday" leaking problem.
- **3/5 perfect matches** (up from 0/5)

### Remaining issues
1. **ASR hallucination** — "weekly" -> "Glee" in utterance 1. Not a TTS/unmute issue; this is Whisper ASR error.
2. **Segment splitting** — utterances 2+3 merged into contiguous segments (no silence gap detected). Utterance 5 split into two segments. Content is preserved but segment boundaries don't align with utterance boundaries.

### Verdict
**PASS** — 96% accuracy exceeds 90% target. Unmute delay 500ms/300ms is the correct fix. Start clipping is eliminated.
