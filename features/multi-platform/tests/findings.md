# Multi-Platform Test Findings

## Confidence Ladders

### Google Meet

| Level | Gate | Score | Evidence | Last checked |
|-------|------|-------|----------|-------------|
| 60 | Mock passes (full-messy, 3 speakers) | 90 | 7 segments, all speakers, Russian included | 2026-03-16 |
| 70 | Mock passes (rapid-overlap) | 0 | Scenario created, not tested | — |
| 75 | Real meeting: standard URL (abc-defg-hij) | 95 | 3 real meetings tested (cxi-ebnp-ixk, hcx-qgnx-dre, kpw-ccvz-umz) | 2026-03-17 |
| 80 | Real meeting: waiting room + host admits via CDP | 0 | Auto-admitted on all tests (same-account). Need external bot join | — |
| 85 | Real meeting: 3+ participants with active mics | 0 | Host had no mic in all tests | — |
| 88 | Real meeting: custom Workspace nickname URL | 0 | Not tested | — |
| 90 | Real meeting: participant joins mid-meeting | 0 | Not tested | — |
| 92 | Real meeting: participant leaves mid-meeting | 0 | Not tested | — |
| 94 | Real meeting: screen sharing active | 0 | Not tested | — |
| 95 | 5 different meeting URLs, all pass | 60 | 3/5 URLs tested | 2026-03-17 |
| 97 | 10+ meetings, varying participant counts | 0 | Not tested | — |
| 99 | All above + rapid speech + multilingual + noise | 0 | Not tested | — |

**Current: 75 (real meeting with standard URL passes, but no admission/mic/dynamic tests)**

### MS Teams

| Level | Gate | Score | Evidence | Last checked |
|-------|------|-------|----------|-------------|
| 60 | Mock passes (full-messy, 3 speakers) | 85 | 8 segments, 3 speakers, English+Russian | 2026-03-17 |
| 70 | Mock passes (rapid-overlap) with ring buffer | 0 | Ring buffer being implemented | — |
| 75 | Real meeting: personal URL (teams.live.com) | 60 | Meeting created+joined, bot admitted from lobby. Audio tracks muted → fix applied but unverified | 2026-03-17 |
| 78 | Real meeting: bot admitted from lobby via CDP | 85 | CDP clicked admit, bot entered meeting | 2026-03-17 |
| 80 | Real meeting: audio captured (muted tracks accepted) | 0 | Muted track fix applied, not retested | — |
| 83 | Real meeting: enterprise URL (teams.microsoft.com) | 0 | Not tested | — |
| 85 | Real meeting: 3+ participants with mics | 0 | Not tested | — |
| 88 | Real meeting: legacy deep link URL | 0 | Not tested | — |
| 90 | Real meeting: ring buffer captures first-second speech | 0 | Ring buffer being implemented | — |
| 92 | Real meeting: participant joins/leaves | 0 | Not tested | — |
| 94 | Real meeting: screen share active | 0 | Not tested | — |
| 95 | 5 different meeting links, personal + enterprise | 0 | Only 1 link tested | — |
| 97 | Government URL (gov.teams.microsoft.us) | 0 | No access to gov tenant | — |
| 99 | All above + rapid speech + multilingual | 0 | Not tested | — |

**Current: 65 (mock pipeline works, real meeting partial — lobby admission works but audio blocked by muted tracks)**

### Zoom

| Level | Gate | Score | Evidence | Last checked |
|-------|------|-------|----------|-------------|
| 0 | Not tested (SDK-based, self-hosted only) | 0 | — | — |
| 30 | SDK initializes, bot attempts join | 0 | — | — |
| 60 | Bot joins real Zoom meeting, audio captured | 0 | — | — |
| 80 | Transcription works end-to-end | 0 | — | — |
| 90 | Multiple meetings, different IDs | 0 | — | — |
| 95 | Regional subdomain URLs | 0 | — | — |

**Current: 0 (Zoom untested, requires SDK + OAuth + Marketplace app)**

### Cross-Platform

| Level | Gate | Score | Evidence | Last checked |
|-------|------|-------|----------|-------------|
| 60 | Same POST /bots API works for Google Meet + Teams | 90 | Both platforms create bots via same endpoint | 2026-03-17 |
| 80 | Same transcript format from both platforms | 85 | Both return {speaker, text, start_time, end_time, language} | 2026-03-17 |
| 90 | Same WS delivery format from both platforms | 0 | WS verified for Google Meet only | — |
| 95 | Switching between platforms in same session | 0 | Not tested | — |

**Current: 60 (API shape matches, WS only verified for Google Meet)**

## Overall Multi-Platform Score

```
Google Meet:   75/100
MS Teams:      65/100
Zoom:           0/100
Cross-platform: 60/100
────────────────────
Weighted avg:  50/100  (Google 40%, Teams 40%, Zoom 10%, Cross 10%)
```

## Out of scope

- Domain-restricted Google Meet (org-only) — bot rejected as unauthenticated guest
- Org-only Teams — bot rejected as anonymous guest
- Authenticated Zoom — requires user account
- Zoom Events — unique per-registrant links, not joinable
- Teams Live Events / Webinars — different URL format, untested
