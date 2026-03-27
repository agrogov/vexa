# Fix: decision-listener max_completion_tokens 256 → 512

## PR Title
`fix(decision-listener): raise max_completion_tokens from 256 to 512`

## PR Description

### Problem

`analyze_window` in `decision-listener/llm.py` capped `max_completion_tokens` at 256. The
`capture_meeting_item` tool schema can produce responses (summary + action items + decisions)
that exceed 256 tokens for even moderately long meeting windows, causing the model to truncate
mid-output and return malformed or incomplete tool-call payloads.

### Fix

Raised `max_completion_tokens` from `256` to `512` in the `openai.chat.completions.create` call
inside `analyze_window`. 512 tokens gives enough headroom for full structured output while staying
well within cost/latency targets for the decision-listener workload.

## Files Changed

| File | Change |
|------|--------|
| `services/decision-listener/llm.py` | `max_completion_tokens`: 256 → 512 |
