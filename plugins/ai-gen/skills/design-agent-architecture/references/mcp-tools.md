# Connecting models to tools via MCP

MCP (Model Context Protocol) standardizes how an LLM app discovers and calls external tools:
an MCP *server* exposes tools/resources/prompts; the *client* (Claude Code, an SDK app, a
LangChain/LangGraph adapter) lists them and routes model tool-calls to them. The win over ad-hoc
function calling is reuse: one server serves any MCP-capable client, so the integration is built
once per service instead of once per agent.

## Contents

- When MCP vs plain function calling
- The protocol substrate
- Tool design rules (apply to both)
- Handling tool failure as normal control flow
- Security (non-negotiable)
- Operational notes

## The protocol substrate

All messages between an MCP client and server follow the
[JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification) — this is a **MUST** in the
spec, not a convention. That is what makes the protocol language-agnostic: a server written in
Python, TypeScript, or Go exposes the same request/response shape, so a client library needs to
speak JSON-RPC once, not one dialect per server language.

Discovery and invocation are two separate JSON-RPC methods (verify the exact method names
against the current spec at <https://modelcontextprotocol.io/specification> — protocol versions
can rename or add fields): the client asks the server to list its tools, gets back each tool's
name, description and JSON-schema input shape, and later calls a tool by name with arguments
that must validate against that schema. The description is not documentation for a human — it is
what the model reads to decide whether and how to call the tool, which is why the tool design
rules below treat descriptions as prompts.

Authorization is scoped to the transport: MCP's authorization framework applies to HTTP-based
transports; a server running over stdio is expected to get its credentials from the environment
instead, not from an MCP-level auth handshake. Don't assume one auth story covers both.

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

## Handling tool failure as normal control flow

Timeouts, malformed arguments, rate limits, and downstream outages are not edge cases for an
agent that calls tools in a loop — they are the common case at scale, and how they're handled is
what separates a demo from a production agent. Treat a tool failure the same way you'd treat any
other observation: surface the error text back to the model (a clear "what went wrong" beats a
raw stack trace — see the tool design rules above) and let the agent choose among a bounded set
of moves, not an open-ended retry:

- **Retry** — for transient failures (timeout, rate limit); cap the count, because an
  uncapped retry loop is a cost incident waiting to happen.
- **Fall back** — to a cheaper tool, a cached result, or a narrower query.
- **Ask** — surface the failure to the user/orchestrator rather than guessing past it, when the
  tool result was load-bearing for a consequential next step.
- **Abandon** — return a partial result or an explicit "could not complete" rather than
  fabricating what the tool would have returned.

The cap is the part teams skip. Without one, a model that decides "let me try again" on every
observed failure turns a single flaky dependency into an unbounded loop — the same failure mode
`loop-engineering.md` names for autonomous loops generally, just triggered by a tool instead of a
missing stop condition.

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
