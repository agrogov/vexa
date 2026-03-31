# /learn — Save what you just learned to the right place

When you discover something important during work — a bug pattern, a coordination failure, a false assumption, a reliability issue — save it immediately to the correct file. Don't wait until the end.

## Where to save what

| What you learned | Where to save it |
|-----------------|-----------------|
| Shared process lesson (applies to all agents) | `.claude/agents.md` → Lessons section |
| Coordination failure between agents | `.claude/agents.md` → Coordination protocol section |
| Feature-specific finding (state detection, pipeline issue) | `features/{feature}/README.md` → Known Limitations or relevant section |
| Platform-specific bug (selector broke, false positive) | Platform agent CLAUDE.md → Known bugs section |
| Confidence score change | `features/{feature}/tests/findings.md` → Confidence table |
| New meeting type or URL format discovered | `features/multi-platform/README.md` + `tests/findings.md` |
| Security finding | `security/tests/findings.md` |
| Doc inconsistency | Fix it now, log: `DOCS: fixed X in Y` |

## How to decide where

1. **Does it apply to ALL agents?** → `agents.md`
2. **Does it apply to a specific feature?** → that feature's README.md or CLAUDE.md
3. **Does it apply to a specific service?** → that service's CLAUDE.md
4. **Is it a confidence score?** → `tests/findings.md` in the relevant feature/service

## Format

When adding a lesson, include:
- **What happened** (the concrete event)
- **Why it matters** (the impact)
- **What to do differently** (the rule)

Example:
```
### False positive admission (2026-03-17)
Bot reported "admitted" while host screenshot showed lobby dialog. UI indicators (Leave button)
visible in lobby too. Impact: bot silently produced 0 transcriptions.
Rule: verify admission from BOTH sides — bot detects AND host confirms.
```

## When to run /learn

- After discovering a bug that wasted debugging time
- After a false assumption led you down the wrong path
- After finding that two agents didn't coordinate correctly
- After a confidence score drops (regression)
- After testing on real meetings reveals mock inaccuracies
- When a human corrects you

## Don't save

- Ephemeral debugging steps (those go in test.log)
- Things already in the code (the code is the source of truth)
- Duplicate of existing lessons (check first)
