# Fix decision-listener: compatibility with gpt-5-mini (o-series) model

## PR Title

Fix decision-listener OpenAI API compatibility with gpt-5-mini

## PR Description

The `gpt-5-mini` model deployed via Azure OpenAI is an o-series reasoning model that:
1. Rejects the deprecated `max_tokens` parameter — requires `max_completion_tokens`
2. Does not support custom `temperature` values — only default (1) is allowed

All LLM calls in the decision-listener service fail with these errors, making the service non-functional.

### Changes

- Replace `max_tokens` with `max_completion_tokens` in all `chat.completions.create()` calls
- Remove `temperature` parameter from all calls (let the model use its default)

| File | Function | Changes |
|------|----------|---------|
| `llm.py` | `analyze_window` | remove `temperature=0.1`, `max_tokens` → `max_completion_tokens=256` |
| `llm.py` | `is_duplicate_llm` | remove `temperature=0`, `max_tokens` → `max_completion_tokens=5` |
| `narrative.py` | `generate_summary` | remove `temperature=0.2`, `max_tokens` → `max_completion_tokens=256` |
| `narrative.py` | `generate_narrative` | remove `temperature=0.3`, `max_tokens` → `max_completion_tokens=4096` |
| `enrichment.py` | `_web_search` | remove `temperature=0.2`, `max_tokens` → `max_completion_tokens=512` |
| `enrichment.py` | `_enrich_entity` | remove `temperature=0.1`, `max_tokens` → `max_completion_tokens=512` |

### Files

| File | Change |
|------|--------|
| `services/decision-listener/llm.py` | -2 temperature, 2 max_tokens fixes |
| `services/decision-listener/narrative.py` | -2 temperature, 2 max_tokens fixes |
| `services/decision-listener/enrichment.py` | -2 temperature, 2 max_tokens fixes |