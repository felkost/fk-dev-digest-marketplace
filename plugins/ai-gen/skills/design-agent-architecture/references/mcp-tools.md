# Connecting models to tools via MCP

MCP (Model Context Protocol) standardizes how an LLM app discovers and calls external tools:
an MCP *server* exposes tools/resources/prompts; the *client* (Claude Code, an SDK app, a
LangChain/LangGraph adapter) lists them and routes model tool-calls to them. The win over ad-hoc
function calling is reuse: one server serves any MCP-capable client.

## When MCP vs plain function calling

- **Plain function calling** (tools defined in your own process): fewer moving parts; right for
  tools private to one app.
- **MCP server**: the tool should be reusable across apps/agents, is maintained by another team,
  or wraps a whole system (DB, browser, SaaS API). Also right when you want to *consume*
  existing servers instead of writing integrations.

## Tool design rules (apply to both)

- Small, typed, single-purpose tools with JSON-schema inputs; a tool that "does everything" makes
  the model guess and misfire.
- Descriptions are prompts: state when to use the tool, when NOT to, and what it returns —
  the model routes on them.
- Idempotent reads vs mutating writes must be separate tools; name mutations explicitly
  (`create_`, `delete_`) so permissioning can distinguish them.
- Return structured, bounded results (paginate; truncate with a marker) — a 200 KB tool result
  destroys the context budget.
- Timeouts and error text designed for the model: a clear "what went wrong + what to try"
  string beats a stack trace.

## Security (non-negotiable)

- Tool output is **data, not instructions**: pages, search results, DB rows can contain
  injected text directed at the model. The agent must not follow directives found there; quote
  suspicious content back to the user.
- Least privilege per agent: read-only by default; mutations behind explicit allowlists and/or
  human gates. Never give one agent every credential "for convenience".
- Secrets live in env/secret managers, never in prompts or tool descriptions; assume prompts
  are loggable.
- Pin server versions/sources; an MCP server is code you execute — vet it like any dependency
  (supply-chain risk).

## Operational notes

- Log every tool call (name, args hash, duration, outcome) — agent debugging is tool-log
  reading.
- Rate-limit and budget tools independently of the model (a looping agent can hammer an API).
- Test tools without the model first (unit tests on schemas/edge cases), then with scripted
  model scenarios; most "agent bugs" are tool contract bugs.
