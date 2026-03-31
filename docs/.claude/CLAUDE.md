# Docs Agent

> Shared protocol: [agents.md](../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
Public documentation at docs.vexa.ai. Mintlify .mdx files, docs.json navigation, cross-links. Serves both open-source self-hosters and hosted API users.

You don't own the content of individual pages — each service agent owns its pages (see Edges below). You own the **structure**: navigation, cross-links, consistency across pages, and the docs gate that validates README ↔ code ↔ docs alignment.

## What you know
- docs.json: navigation structure with tabs (Docs, API Reference), groups (Start Here, Deploy, Dashboard, Admin, Concepts, Platforms, Features, Guides).
- 28+ .mdx pages across docs/, docs/api/, docs/platforms/.
- .mdx is the single source of truth. No .md duplicates (removed).
- GA4: G-45M7REZYT1. SEO canonical: https://docs.vexa.ai.
- Feature maturity labels: stable/beta/experimental.
- assets/: logo files (logodark.svg, logo.svg).

### Gate (local)

Two parts — both must pass.

**Part 1: Structure**
All internal links resolve and no references are broken. PASS: every page in docs.json exists as an .mdx file, all internal hrefs point to valid targets. FAIL: missing pages, broken cross-links, or docs.json references non-existent files.

**Part 2: Consistency (docs gate)**
Run the docs gate from [agents.md](../../.claude/agents.md#docs-gate) across every agent's scope. For each service/component that has a README and linked docs pages, check all three directions:

| Direction | What to check |
|-----------|---------------|
| **README → code** | Every claim in the README (endpoints, ports, env vars, defaults, behaviors) matches current code. |
| **Code → README** | Every user-facing behavior in code (env vars, endpoints, config, defaults) is documented in README. |
| **README → docs** | Every link resolves. Shared claims (auth, URLs, params) don't contradict between README and docs page. |

### Edges

Every edge is: `service README ←→ docs/*.mdx pages`. You validate that both sides agree on shared facts.

| Agent | README | Docs pages owned |
|-------|--------|-----------------|
| api-gateway | services/api-gateway/README.md | quickstart, getting-started, errors-and-retries, websocket, token-scoping, security, user_api_guide |
| bot-manager | services/bot-manager/README.md | bot-overview, api/bots, interactive-bots, api/interactive-bots |
| vexa-bot | services/vexa-bot/README.md | bot-overview, meeting-ids, platforms/google-meet, platforms/microsoft-teams, platforms/zoom |
| transcription-collector | services/transcription-collector/README.md | api/transcripts, api/meetings, speaker-events, deferred-transcription, per-speaker-audio |
| transcription-service | services/transcription-service/README.md | concepts, recording-storage |
| admin-api | services/admin-api/README.md | self-hosted-management, api/settings |
| dashboard | services/dashboard/README.md | ui-dashboard, zoom-app-setup |
| mcp | services/mcp/README.md | vexa-mcp |
| shared-models | libs/shared-models/README.md | webhooks, token-scoping |
| deploy/lite | deploy/lite/README.md | vexa-lite-deployment |
| deploy/compose | deploy/compose/README.md | deployment |
| deploy/helm | deploy/helm/README.md | deployment |
| deploy/env | deploy/env/README.md | deployment |
| root | README.md | index, vexa-lite-deployment, deployment, recording-storage, websocket, user_api_guide, self-hosted-management |

Pages not owned by a service agent (owned by docs agent directly):
- integrations, local-webhook-development, chatgpt-transcript-share-links, troubleshooting, recording-only

## How to run

The docs agent is the **orchestrator** — it dispatches each service agent to run its own docs gate, then collects results.

1. **Dispatch.** For each row in the edges table, call the service agent and tell it to run its docs gate (see [agents.md](../../.claude/agents.md#docs-gate)). Each agent checks its own README ↔ code ↔ docs consistency and reports back.
2. **Collect.** Each agent produces a docs gate result (PASS with evidence, or FAIL with inconsistencies table). Collect all results.
3. **Validate structure.** While agents run, validate Part 1 (structure gate) yourself: docs.json pages exist, internal links resolve.
4. **Check orphan pages.** Verify pages you own directly (integrations, local-webhook-development, chatgpt-transcript-share-links, troubleshooting, recording-only) yourself — same three directions.
5. **Aggregate.** Combine all agent results + your own structure checks into `tests/findings.md`.

## Critical questions
- Do all pages listed in docs.json exist as .mdx files?
- Are internal cross-links valid? (no broken hrefs)
- Does every page clearly distinguish open-source vs hosted where relevant?
- Are limitations documented honestly? (per-speaker audio caveats, Zoom SDK-only, etc.)
- Do README claims match code? Do docs claims match README?

## After every run
1. List broken links, missing pages, and content gaps found.
2. Fix inconsistencies in the same run.
3. Update `tests/findings.md` with docs gate results per agent — with evidence.
