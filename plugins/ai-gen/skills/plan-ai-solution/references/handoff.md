# Session handoff protocol

Work on an AI system spans many sessions; a fresh session has no conversation history. The
`HANDOFF.md` file at the user's project root is the transfer mechanism. Rules first, template
below.

## Rules

- **Read the whole file before touching anything** at the start of a session; if the handoff
  contradicts the actual state of the code, say so out loud instead of silently trusting either.
- **Write decisions and their reasons**, not just a file list. The next session must understand
  *why* a choice was made so it does not blindly re-litigate it.
- **Record verified state, not intended state.** "Tests pass (12/12, `pytest`, exit 0)" is a
  handoff fact; "tests should pass" is not. If something is unverified, label it unverified.
- **Environment gotchas are first-class content**: API keys location, model IDs pinned, ports,
  Docker quirks, OS-specific traps. These cost the most time to rediscover.
- The file belongs to the user — never silently overwrite their manual edits; append/update
  sections and date them.
- Update at the end of every substantial session, or immediately when asked ("зроби handoff").

## Template

```markdown
# Session handoff — <project name>

Written <date> at the end of a working session, for a fresh session with no history.
Read this whole file before touching anything.

## What this project is
<2–5 sentences: the decision the system supports, the chosen model class and why,
the stack (e.g. Python + LangGraph + OpenRouter + React 19), where things live.>

## Current verified state
<Bullet list of facts verified this session: what runs, what passes, exact commands
and their results. Label anything unverified.>

## What just happened (this session)
<What was done and — critically — why. Alternatives that were rejected and the reason.>

## Key decisions so far
<Running list: decision → reason → date. E.g. "RAG over fine-tuning: corpus changes
weekly, no training budget (2026-07-19)".>

## Environment gotchas
<Keys/secrets location (never the values), pinned model IDs, ports, Docker/OS quirks.>

## Open threads / not done
<What is half-finished, what is deliberately deferred and why, next logical step.>
```
