# Chat Test Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Send message via API | 0 | Not tested | — | POST /bots/{id}/chat, verify 200 response |
| Message appears in meeting | 0 | Not tested | — | Check meeting chat DOM for injected message |
| Read messages from participants | 0 | Not tested | — | GET /bots/{id}/chat returns messages from others |
| Bidirectional flow | 0 | Not tested | — | Send + receive in same session, verify both directions |
| Message relay via Redis | 0 | Not tested | — | Check Redis for chat message events |
