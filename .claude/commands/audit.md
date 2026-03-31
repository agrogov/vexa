# Change Audit

Review all uncommitted changes and challenge each one. For every changed file, determine: KEEP, REVERT, SIMPLIFY, or ESCALATE. This is the automated version of a rigorous code review — assume every change is guilty until proven necessary.

## Usage

Run from anywhere in the Vexa repo after making code changes, before committing. Takes no arguments.

## Procedure

### Phase 1: Gather changes

Run these commands to understand the full scope of uncommitted work:

```bash
cd /home/dima/dev/vexa
echo "=== Staged changes ==="
git diff --cached --stat
echo ""
echo "=== Unstaged changes ==="
git diff --stat
echo ""
echo "=== Untracked files ==="
git ls-files --others --exclude-standard
echo ""
echo "=== Full diff (staged + unstaged) ==="
git diff HEAD
```

If there are no changes, report "Nothing to audit" and stop.

### Phase 2: Analyze each changed file

For EACH file that appears in the diff, read the full diff for that file and answer these questions. Do not skip any file.

#### Necessity
- Is this change necessary? What breaks without it?
- If this file was changed during a debugging session, was it the actual fix or a side-effect of trial-and-error? Look for changes that were added speculatively and never reverted.
- Could the goal be achieved without touching this file at all?

#### Minimality
- Is this the simplest possible solution? Could fewer lines achieve the same result?
- Does this add new abstractions, config options, feature flags, dependencies, or parameters? Could any of those be avoided?
- Are there any lines that could be deleted without changing the outcome? (Extra imports, unused variables, defensive code that defends against nothing.)

#### Correctness
- Is this a proper fix or a workaround? If it's a workaround, where should the real fix live?
- Does it fix the root cause or just suppress the symptom? (e.g., adding a try/except around a crash vs. fixing why it crashes)
- Could this mask a deeper problem? (e.g., adding a default value that hides a missing config)
- If this changes behavior, is the new behavior correct in ALL cases, not just the one that was tested?

#### Safety
- What's the blast radius? List every service, feature, or user flow that could be affected.
- Does this weaken security? (broader permissions, disabled auth checks, exposed debug endpoints, CORS changes)
- Does it touch shared code (libs/shared-models, shared config, docker-compose, .env templates)? If so, who else depends on it?
- Edge cases: What happens with empty input, null values, concurrent requests, network failures?

#### Cleanup
- Are there debug prints, console.logs, commented-out code, or TODOs that should not be committed?
- Are there formatting-only changes mixed in with functional changes? Those should be separate commits.
- Are test file changes mixed with production code changes? Flag if they should be split.

### Phase 3: Render verdicts

For each changed file, output exactly one verdict:

```
KEEP: path/to/file — [why it's correct, necessary, and minimal]
REVERT: path/to/file — [why it's unnecessary, speculative, or a workaround]
SIMPLIFY: path/to/file — [what's excessive and how to reduce it]
ESCALATE: path/to/file — [this is a workaround; the real fix belongs in X]
```

Rules for verdicts:
- **KEEP** means you would mass-approve this in code review without a single comment. It's correct, minimal, and safe.
- **REVERT** means this change should not be committed. Either it's unnecessary, it was a debugging artifact, or it makes things worse.
- **SIMPLIFY** means the direction is right but the implementation is heavier than needed. Suggest the simpler version.
- **ESCALATE** means this is papering over a problem that should be fixed elsewhere. Name where.

Be aggressive. The default answer is REVERT. A change must justify its existence.

### Phase 4: Log results

```bash
# Log each verdict
echo "[$(date -Iseconds)] [audit] VERDICT: path/to/file — reason" >> /home/dima/dev/vexa/test.log
```

Log one line per file. Use the actual verdict (KEEP/REVERT/SIMPLIFY/ESCALATE) as the level.

### Phase 5: Revert commands

If any files got REVERT verdicts, output the exact git commands to undo them:

```bash
# For tracked files that should be fully reverted:
git checkout HEAD -- path/to/file

# For specific hunks within a file (when only part should be reverted):
# Describe which hunks to revert and why, then:
git checkout -p HEAD -- path/to/file
# (interactive — agent should describe which hunks to accept)

# For untracked files that should be removed:
rm path/to/file
```

### Phase 6: Summary

End with a one-line summary:

```
AUDIT COMPLETE: X files reviewed — Y KEEP, Z REVERT, W SIMPLIFY, V ESCALATE
```

If all verdicts are KEEP, say so clearly — the changes are clean.
If any verdicts are REVERT, warn: "Do NOT commit until reverts are applied."

## Examples of what to catch

- A flag added to a function signature that is always passed as the same value (unnecessary abstraction)
- A try/except that swallows an error instead of fixing why the error happens
- An `autoplay` attribute added to a media element during debugging that was never the actual fix
- A config value changed from a sensible default to a hardcoded workaround
- Imports added but never used
- Permissions broadened "just to be safe" without understanding why the original scope failed
- Changes to docker-compose.yml or .env that affect all services when only one needed a fix
- Debug logging left in production code paths
