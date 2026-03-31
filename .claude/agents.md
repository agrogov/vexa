# Shared Agent Protocol

All agents in this repo follow this protocol. Each agent's CLAUDE.md defines what's local (scope, gate, dependencies). This file defines the shared process.

## Features

`features/` contains specialist agents. Each one owns a narrow flow with its own confidence ladder.

**Properties of a feature:**
- **Narrow scope** — one flow, one responsibility
- **Own confidence ladder** — specific gates from 0 → 99 with evidence at each level. **Mandatory. Always present.**
- **Stackable** — compose sequentially (browser-control → realtime-transcription) or in parallel (webhooks + token-scoping)
- **Self-contained** — CLAUDE.md, README.md, tests/findings.md, optional scripts/commands
- **Dependencies** — a feature can depend on another feature's output. The dependent waits for `READY` before starting.

**Every agent must have a confidence ladder defined in its CLAUDE.md at all times.** No ladder = the agent is not operational. If you create or modify a feature agent and it has no ladder, add one before you finish. If you discover a feature agent without a ladder, add one as part of your work — don't leave it missing.

Features can be product features (realtime-transcription), infrastructure (browser-control), or cross-cutting (multi-platform). The name doesn't matter — what matters is narrow scope + own confidence ladder.

**System confidence = min of stacked features in the critical path.**

Example: browser-control at 80 + google-meet RT at 90 = end-to-end confidence is 80 (bottleneck is browser-control).

**Stacking pattern:**
```
feature A (delivers environment) → feature B (uses environment, delivers result)
                                        ↓
                              feature C (uses result, delivers verification)
```
Each feature runs only after its dependency outputs `READY`. No parallel assumptions on dependent features.

## Phases

Know what phase you're in. Act accordingly.

1. **Diagnose** — read-only. No code changes. Trace the root cause chain. Don't fix symptoms.
2. **Fix** — minimal change to the actual root cause. One fix per root cause. Don't stack workarounds.
3. **Verify** — retest your local gate. Pass or fail, nothing else.
4. **Audit** — run `/audit` on your changes. Review every change you made. For each one ask:
   - Is it necessary? If the gate passes without it, revert it.
   - Can it break things? What's the blast radius?
   - Is it a proper fix or a workaround? Should this be fixed at a different level?
   - Does it weaken security or robustness?
   - If you stacked multiple changes during diagnosis, go back and remove the ones that weren't the actual fix.

## Diagnostic protocol

1. **Read last findings** (`tests/findings.md`) — what failed before? Start there.
2. **Fail fast** — test the riskiest thing first. If a dependency is down, everything above it fails. Check dependencies before dependents.
3. **Isolate** — when something fails, drill into WHY. Is it the service? The dependency? The network? The config? Don't report symptoms — report root causes.
4. **Parallelize** — run independent checks concurrently.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

## Logging

Write to `/home/dima/dev/vexa/test.log`. This is the shared timeline across all agents — the orchestrator and humans read it to understand what happened.

**Format:** `[timestamp] [agent-name] LEVEL: message`

**When to log:**
- Phase transitions: `PHASE: diagnose → fix` (with reason)
- Every insight during diagnosis: `ROOT CAUSE: audio GC'd because ScriptProcessor has no persistent ref`
- Gate results: `PASS: local gate passed` or `FAIL: local gate failed — transcription returns empty`
- Every code change made: `FIX: index.ts — persist AudioContext refs on window.__vexaAudioStreams`
- Every code change reverted during audit: `AUDIT REVERT: constans.ts — autoplay flag unnecessary, GC fix was the actual solution`
- Surprising findings: `SURPRISING: users table has no PRIMARY KEY`
- Scope boundaries: `OUT OF SCOPE: transcription service returns empty — not my gate, reporting upstream`

**Levels:** PHASE, PASS, FAIL, FIX, AUDIT REVERT, ROOT CAUSE, SURPRISING, DEGRADED, OUT OF SCOPE

**Rules:**
- One line per event, not per check
- Log as you go, not at the end — the log is a live timeline
- Include enough context that someone reading only the log understands what happened and why

## Gate rules

- Every agent has a local gate — tests only what that agent controls
- Gates are binary: pass or fail. No "PASS (DEGRADED)"
- **Untested = fail.** If you can't test something in your gate, that's a fail. Don't skip it and report partial results as success. Either set up what's needed to test it, or report FAIL with the reason you couldn't test it.
- **Don't stop at prerequisites.** If your gate needs a mock meeting, a running service, generated audio — set it up. That's your job. "Needs X to test" is not a finding, it's a task you haven't done yet.
- The orchestrator (compose agent) doesn't own a system gate — it emerges when all local gates pass
- If your gate fails, diagnose → fix → verify → audit. If it passes, you're done.

## Confidence scores

We can't ship what we haven't verified. Every gate check has a confidence score tied to specific evidence. No evidence = score 0.

### Score scale

The scale is **non-linear**. Moving from 90→95 requires far more evidence than 0→90. Moving from 95→99 requires systematic repetition — a single strong test never gets you there.

| Score | Meaning | Example |
|-------|---------|---------|
| 0 | Not validated. No evidence. | "Not tested" / "Needs X to run" |
| 30 | Indirect evidence only. | "Logs suggest it works" / "Worked last week" |
| 60 | Validated once, conditions may have changed. | "Passed 3 days ago, code changed since" |
| 80 | Validated recently, minor caveats. | "Passed against mock, not real meeting" |
| 90 | Validated with strong evidence. | "Passed against real meeting, full pipeline, transcriptions in DB" |
| 95 | Validated with production-grade evidence, multiple times. | "Passed 5 consecutive real-meeting runs, verified by human" |
| 99 | **Repetitive success under real conditions.** Hard to reach, impossible to claim after one test. | "Passed 20 consecutive runs, all under threshold, no flakes, no manual intervention" |

**99 is never claimed from a single run.** Even a perfect test gives you 95 at best. 99 requires a streak — the same thing working the same way, repeatedly, without intervention. The gap between 95 and 99 is deliberate: it forces you to prove stability, not just capability.

### How to track

Each agent maintains a confidence table in its `tests/findings.md`:

```markdown
| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Bot joins mock | 90 | 3 speakers found, all locked | 2026-03-16 20:27 | Test against real Meet |
| Audio reaches TX service | 90 | HTTP 200, non-empty text | 2026-03-16 20:27 | -- |
| Speaker identity correct | 80 | Locked via class inference, not indicator | 2026-03-16 20:27 | Test with real Meet DOM |
```

### Rules

- **Ladder is mandatory.** Every agent must have a confidence ladder in its CLAUDE.md. A ladder-less agent is an untested agent — treat all its scores as 0.
- **Score 0 for anything untested.** "Not tested" is not "unknown" — it's zero confidence.
- **Evidence must be specific.** Not "it works" — instead: "HTTP 200, response contains 7 segments with speaker names, meeting_id=8791, checked 2026-03-16 20:27."
- **Scores decay.** Code changes since last check drop the score. A 90 from last week with code changes since is a 60 today.
- **"To reach 90+"** is mandatory for any score below 90. This is the action needed — not a wish, a task.
- **Mock vs real:** Mock evidence caps at 90. Only real-world validation (real meeting, real users, production traffic) reaches 95.
- **Log score changes:** `CONFIDENCE: bot-joins-mock 0 → 90 (3 speakers found, all locked)`

### Gate verdict from scores

Your gate PASS/FAIL comes from confidence scores:
- **PASS:** All checks in your gate are ≥ 80
- **FAIL:** Any check is below 80
- Report the lowest score as the bottleneck

## Security

- **Never log secrets.** Not in `test.log`, not in `findings.md`, not in reports. This includes DATABASE_URL, API tokens, API keys.
- **Log that a secret is set, not its value.** Example: `ADMIN_API_TOKEN=set (length 10)` not `ADMIN_API_TOKEN=my-secret`.
- **Test data isolation.** Each run creates its own user/meeting. Don't reuse data from previous runs.
- **Cleanup.** Always clean up test containers/data, even on failure.

## Edges

An **edge** is the boundary where one agent's scope meets another's. Data crosses the edge — one agent sends, the other receives. Each agent owns its side of the edge.

### How edges work

- Each agent declares in its CLAUDE.md: **what I send** (output edges) and **what I expect to receive** (input edges)
- An edge is verified when both agents agree the data crossed correctly
- If an edge fails, the agent on the receiving side reports it as `OUT OF SCOPE` and escalates to the sending agent
- The integration agent (compose/lite) doesn't own any edge — it verifies that both sides saw the same data cross

### Example

```
bot-services agent sends: audio chunks to Redis stream
transcription-collector agent expects: audio chunks in Redis stream

Edge verified when:
- bot-services confirms: "I wrote 150 chunks to stream X"
- transcription-collector confirms: "I consumed 150 chunks from stream X"
```

### In your CLAUDE.md

Each agent should document its edges:

```markdown
### Edges
**Sends:**
- audio chunks → Redis stream `transcription_segments` (consumed by: transcription-collector)
- speaker events → Redis stream `speaker_events_relative` (consumed by: transcription-collector)

**Receives:**
- bot config from bot-manager via `BOT_CONFIG` env var
- meeting URL from bot-manager via `meetingUrl` field
```

### When an edge fails

Don't debug the other agent's side. Log what you sent or what you expected to receive, and escalate:
```
OUT OF SCOPE: sent 150 audio chunks to Redis stream, but transcription-collector found 0 — escalating to TC agent
```

## Doc ownership

Each agent maintains its own README **and** the public doc pages (`docs/*.mdx`) that cover its domain.

### README structure

Every README follows the **Why / What / How** structure:
- **Why** — the problem this component solves
- **What** — what it does, its architecture, key behaviors
- **How** — how to run, configure, and develop it

These sections are your test specs. If the README says it does something, the code must do it. If the code does something user-facing, the README must say it.

Each README also has a `### Documentation` section near the top that links to the docs pages it owns. Example:
```markdown
### Documentation
- [Quickstart](../../docs/quickstart.mdx)
- [Getting Started](../../docs/getting-started.mdx)
```

This list is the source of truth for which docs pages an agent owns. The agent's CLAUDE.md doesn't duplicate the list — it points to the README.

When you change behavior, update both your README and your doc pages.

The docs agent (`docs/.claude/CLAUDE.md`) orchestrates the docs gate across all agents and validates cross-links and consistency across all pages. Agents own the content; the docs agent owns the structure.

### Rules
- When you change a behavior (endpoint, auth header, request format), update your doc pages too
- If you add or remove a docs page, update the `### Documentation` list in your README
- If you find your doc page says something wrong, fix it and log: `FIX: docs/quickstart.mdx — auth header is X-API-Key not Authorization: Bearer`
- If another agent's doc page contradicts yours, log `OUT OF SCOPE` and escalate to that agent

## Docs gate

Every agent runs a docs gate after its functional gate. The docs gate checks three directions:

| Direction | What to check |
|-----------|---------------|
| **README → code** | Every claim in the README (endpoints, ports, env vars, CLI flags, default values, behavior descriptions) matches the current code. |
| **Code → README** | Every user-facing behavior in the code (env vars, endpoints, config keys, CLI args, defaults) is documented in the README. |
| **README → docs** | Every link from README to `docs/*.mdx` or `docs.vexa.ai/*` resolves. Shared claims (auth headers, URL patterns, config names) don't contradict between README and docs page. |

### How to check

1. Read the README. Extract every factual claim (ports, env vars, defaults, endpoints, behaviors).
2. For each claim, find the corresponding code. If the code disagrees, that's an inconsistency.
3. Scan the code for user-facing config/endpoints. For each one, check the README mentions it. If missing, that's an inconsistency.
4. For every link to `docs/*.mdx` or `docs.vexa.ai`, verify the target file exists. Spot-check that shared facts (auth method, URL shape, parameter names) match.

### Output format

Every agent **must** produce a docs gate result in `tests/findings.md`. Two possible outcomes:

**If inconsistencies found:**
```
## Docs gate — FAIL

| # | Direction | Inconsistency | Evidence |
|---|-----------|---------------|----------|
| 1 | README → code | README says default port is 8085, code defaults to 8056 | README.md:42 vs app/main.py:15 `PORT = int(os.getenv("PORT", 8056))` |
| 2 | Code → README | `WHISPER_BATCH_SIZE` env var not documented | app/config.py:23, not in README |
| 3 | README → docs | Link to docs/voice-agent.mdx — file does not exist | README.md:88 |
```

**If no inconsistencies found:**
```
## Docs gate — PASS

No inconsistencies found.

| Direction | Evidence |
|-----------|----------|
| README → code | Checked 12 claims (3 endpoints, 4 env vars, 2 defaults, 3 behaviors) — all match. See list below. |
| Code → README | Scanned app/main.py, app/config.py — 4 env vars, 2 endpoints, all documented in README. |
| README → docs | 3 links checked, all resolve. Auth method (X-Admin-Token) matches across README and docs/self-hosted-management.mdx. |
```

### Rules

- **Evidence is mandatory.** Both PASS and FAIL require file paths, line numbers, and the actual values compared. "Looks fine" is not evidence.
- **PASS without evidence is a FAIL.** If you can't show what you checked, you didn't check it.
- **Fix inconsistencies in the same run.** Don't file them for later. Fix, then re-check.
- **Log every finding:** `DOCS: README claims PORT=8085 but code defaults to 8056 — fixing README`
- **Docs gate is not optional.** If you skip it, your overall gate is FAIL.

## Coordination protocol

When multiple agents work together on a flow (e.g., host browser + bot), they must verify each handoff, not just act.

**Pattern: act → verify → signal**
- Host agent: click admit → **verify bot moved from "Waiting" to "In the meeting"** → signal "admitted"
- Bot agent: detect admission → **verify by checking for remote audio (not just UI buttons)** → proceed

**Don't trust self-reports.** A bot saying "I'm admitted" doesn't mean it's admitted. Verify from the other side. If the host sees the bot in lobby, the bot is in lobby — regardless of what the bot's admission detection says.

**False positives are worse than false negatives.** A bot that thinks it's in the meeting but isn't will silently produce zero results. A bot that waits in lobby and reports "not admitted" is at least honest.

**Orchestration order matters:**
1. Create meeting (host)
2. Start audio playback (host)
3. Launch bot (orchestrator)
4. Bot reaches lobby (bot reports, host verifies)
5. Host admits (host acts, host verifies bot moved to "In the meeting")
6. Bot detects real admission (bot verifies remote audio exists)
7. Wait for transcription (orchestrator checks both sides)

Each step must complete before the next starts. No parallel assumptions.

## Lessons

- Don't stack workarounds. Find the root cause, fix it, remove anything else you added along the way.
- Don't debug outside your scope. If the problem is downstream, report it and stop.
- Mock must match reality. When building mocks, research the real thing first (ask the human for access if needed).
- Test the write path, not just the read path. Verifying old data exists is not the same as verifying new data gets created.
- **Verify, don't assume.** "Bot says admitted" ≠ admitted. "3 audio elements found" ≠ receiving remote audio. Always verify from both sides of an edge.
- **False positive admission is the worst bug.** The bot silently does nothing, reports success, produces zero results. Check from the host side.
- **Debug the right layer.** We spent time investigating PulseAudio, Chrome args, and audio thresholds — when the real problem was the bot was never admitted. Start with the simplest explanation.
- **Detect dead ends early.** If you're fighting infrastructure (PulseAudio, SFU, audio injection) to do something the product already does (TTS), stop. Ask: "does the product already have this capability?" If yes, use it. We spent hours trying to inject audio externally when the bot's TTS pipeline already speaks in meetings.
- **"I need to make X work" vs "I need X to happen."** Focus on the outcome, not the mechanism. We needed "bot speaks in meeting" — not "PulseAudio pipe-source feeds Chrome fake-capture." The TTS endpoint already delivers the outcome.
- **Always validate manually.** "85% keyword match" is not validation. Compare source text to transcription output word by word, line by line. Mark each: exact, minor error, major error, missing. Count real numbers. Keyword counting hides garbled text and missing segments.
