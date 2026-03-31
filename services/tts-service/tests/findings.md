# TTS Service — Meeting Conversation Test Findings
Date: 2026-03-17 18:55:00
Mode: compose-full (live Google Meet meeting raf-yeou-nib)

## Summary
- PASS: 7
- FAIL: 0
- DEGRADED: 3
- UNTESTED: 0
- SURPRISING: 2

## Test Setup
- Meeting: Google Meet raf-yeou-nib (host: Dima)
- Alice Johnson (8904): speaker + listener (degraded audio capture, used for TTS)
- Bob Listener (8905): listener, 3 audio streams, per-speaker transcription
- Carol Williams (8906): listener, 3 audio streams, per-speaker transcription
- 10 scripted utterances sent via /speak endpoint with 10s spacing
- Voices: en_US-amy-medium (Alice), en_US-ryan-medium (Bob), en_GB-alba-medium (Carol)

## Bob's Transcription (primary validator)

Bob hears Alice (speaker-1) and Carol (speaker-2) but not himself.

| # | Who Spoke | Script | Bob Confirmed | Verdict |
|---|-----------|--------|---------------|---------|
| 1 | Alice | "Good morning everyone. Let's begin our weekly product review meeting." | "Good morning, everyone. Let's begin our weekly product review meeting." | PASS |
| 2 | Bob | (self — not captured) | — | EXPECTED |
| 3 | Carol | "Before we start, I want to flag a critical bug in the payment module." | "Before we start, I want to flag a critical bug in the payment module." | PASS |
| 4 | Alice | "That sounds urgent Carol. Can you give us the details?" | "That sounds urgent, Carol. Can you give us the details?" | PASS |
| 5 | Bob | (self — not captured) | — | EXPECTED |
| 6 | Carol | "The bug causes duplicate charges when users click submit twice quickly." | "The bug causes duplicate charges when users click Submit twice quickly." | PASS |
| 7 | Alice | "How many customers have been affected so far?" | "How many customers have been affected so far?" | PASS |
| 8 | Bob | (self — not captured) | — | EXPECTED |
| 9 | Carol | "Engineering has a hotfix ready. We need approval to deploy today." | "Engineering has a hot fix ready. We need approval to deploy today." | PASS (minor: "hotfix" → "hot fix") |
| 10 | Alice | "Approved. Let's deploy the fix immediately and monitor the results." | "Approved. Let's deploy the fix immediately and monitor the results." | PASS |

**Bob score: 7/7 hearable utterances transcribed correctly (1 minor "hotfix"→"hot fix")**

## Carol's Transcription (cross-validation)

Carol hears Alice (speaker-1) and Bob (speaker-2) but not herself.

| # | Who Spoke | Script | Carol Confirmed | Verdict |
|---|-----------|--------|-----------------|---------|
| 1 | Alice | "Good morning everyone..." | Merged with #4 into one segment: "review meeting that sounds urgent Carol can you give us" | DEGRADED (segment merge) |
| 2 | Bob | "Thanks Alice. I have the Q4 metrics ready to share with the team." | "Thanks to the core metrics ready to share with the team." | DEGRADED (mishearing: "Alice. I have the Q4" → "to the core") |
| 4 | Alice | "That sounds urgent Carol..." | Merged with #1 | DEGRADED |
| 5 | Bob | "While Carol explains, I'll pull up the relevant dashboard." | "While Carol explains, I'll pull up the relevant dashboard." | PASS |
| 7 | Alice | "How many customers..." | "The details, how many customers have been affected so far." (cross-segment bleed) | PASS (content present) |
| 8 | Bob | "I checked the logs this morning. We have forty seven cases since Tuesday." | "I checked the logs this morning. We have 47 cases since Tuesday." | PASS ("forty seven" → "47" — correct numeral conversion) |
| 10 | Alice | "Approved. Let's deploy the fix immediately and monitor the results." | Split into 2 segments but content correct | PASS |

**Carol score: 4/7 clean, 3/7 degraded (segment merging and one mishearing)**

## Speaker Identity

| Bot | Mapping | Notes |
|-----|---------|-------|
| Bob | speaker-1 = (unmapped), speaker-2 = Carol Williams | Alice's name never resolved on Bob's side |
| Carol | speaker-1 = Alice Johnson, speaker-2 = Bob Listener | Both names mapped correctly |

## Surprising Findings
1. **Bob never mapped Alice's speaker name** — speaker-1 stayed empty string throughout. Carol mapped Alice correctly. Root cause: participant count change triggered mapping invalidation, and remapping only resolved Carol.
2. **Carol had segment merging** — Alice's utterances #1 and #4 merged into one segment, losing boundaries. Bob did not have this problem. Possible cause: Carol's transcription timing was slightly off or voice similarity caused merge.

## Riskiest Thing
Speaker identity mapping is inconsistent across bots — Bob failed to map Alice while Carol succeeded. This means the same meeting viewed by different users could show different speaker attributions.

## What Was Not Tested
- Multi-language voices (all utterances were English)
- Long utterances (>30 seconds)
- Overlapping speech from multiple TTS bots simultaneously
- Voice agent response (AI reply to speech) — only one-way TTS tested
