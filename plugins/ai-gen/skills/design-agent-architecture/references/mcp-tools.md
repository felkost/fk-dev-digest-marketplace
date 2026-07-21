# Connecting models to tools via MCP

MCP (Model Context Protocol) standardizes how an LLM app discovers and calls external tools:
an MCP *server* exposes tools/resources/prompts; the *client* (Claude Code, an SDK app, a
LangChain/LangGraph adapter) lists them and routes model tool-calls to them. The win over ad-hoc
function calling is reuse: one server serves any MCP-capable client, so the integration is built
once per service instead of once per agent.

## Contents

- The three primitives and who controls each
- The protocol substrate
- Transports and deployment shapes
- When MCP vs plain function calling
- Tool design rules (apply to both)
- Handling tool failure as normal control flow
- Security (non-negotiable)
- Operational notes
- Worked example

## The three primitives and who controls each

A server can expose three different kinds of thing, and the spec is explicit about *who decides*
when each one is used — a distinction most treatments skip in favor of talking only about tools:

| Primitive | Control | Description | Example |
|---|---|---|---|
| **Prompts** | User-controlled | Interactive templates invoked by user choice | Slash commands, menu options |
| **Resources** | Application-controlled | Contextual data attached and managed by the client | File contents, git history |
| **Tools** | Model-controlled | Functions exposed to the LLM to take actions | API POST requests, file writing |

(<https://modelcontextprotocol.io/specification/2025-11-25/server>, checked 2026-07-21 —
resolve the current revision through
<https://modelcontextprotocol.io/specification/versioning> rather than trusting this date.)

In practice: a **tool** is what the model decides to call mid-turn based on its description (which
is why the design rules below treat descriptions as prompts). A **resource** is data the
*application* chooses to attach — a client might list resources in a picker and let the user
attach one, or attach one automatically based on context; the model never independently reaches
for a resource the way it reaches for a tool. A **prompt** is a template the *user* invokes on
purpose (a slash command is the clearest instance). Building everything as a tool works, but
throws away this distinction — a "fetch the current file" resource and a "run this saved query"
prompt both get flattened into tools the model has to decide to call, when the application or the
user already knew it wanted that data.

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

## Transports and deployment shapes

The spec (revision 2025-11-25, checked 2026-07-21 via the versioning page above) currently defines
**exactly two** standard transports:

- **stdio** — the client launches the server as a subprocess and speaks JSON-RPC over its
  stdin/stdout. "Clients **SHOULD** support stdio whenever possible." No network, no auth
  handshake; the server inherits the environment (and its credentials) from the launching process.
- **Streamable HTTP** — the server runs as an independent, long-lived process behind a single HTTP
  endpoint (both POST and GET), optionally using Server-Sent Events to stream individual
  responses. This **replaces** the older HTTP+SSE transport "from protocol version 2024-11-05";
  the compatibility section names that older transport **deprecated**.

**Two ways to get this wrong in opposite directions.** A source that is otherwise current can
still teach "the two transports are stdio and SSE" — SSE was never a standalone transport in the
current spec; it is a streaming *mechanism* Streamable HTTP may use inside its one endpoint. The
opposite error is "SSE is gone" — it isn't; it survives exactly there. Neither "two transports:
stdio and SSE" nor "SSE is gone" is correct. (This is the plugin's own finding this round — see
`HANDOFF.md` round 13 — from a 2026-published source that got the protocol right for an earlier
revision and never updated the prose.)

**Deployment shapes are a property of an agent's *set* of servers, never of one server.** A given
server is either local (stdio, launched by the client) or remote (Streamable HTTP, an independent
process); there is no third "hybrid" transport. "Hybrid deployment" describes an agent connected to
several servers where some are local and some are remote — the hybridity lives at the agent's
connection list, not inside any single server's code.

**The protocol's price.** Every MCP call adds a process (for stdio) or a network hop and a
session (for Streamable HTTP) beyond a plain function call — extra latency and an extra failure
mode (the server process can crash or the connection can drop, independent of your own code).
Reach for MCP when the tool is genuinely external — reusable across agents, owned by another team,
or wrapping a whole system. For logic private to one agent, an in-process function call has none
of that cost; see "When MCP vs plain function calling" below.

**The state-semantics shift.** A module-level variable that was private to one agent's process
(e.g. a Python list backing an in-memory log) does not change *how it's written* when you wrap it
in an MCP server — but it does change *who shares it*. Once that module is reachable as a server,
every client connected to it reads and writes the same state. This is an architectural change
dressed as copy-paste: nothing in the code marks the moment a private variable became shared
state. `references/mcp-example.md`'s worked example names this concretely in its own module-level
journal.

## When MCP vs plain function calling

- **Plain function calling** (tools defined in your own process): fewer moving parts, no protocol
  hop; right for tools private to one app.
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
  destroys the context budget. **The next step past truncation is offloading**: persist the full
  result somewhere addressable (a log, a blob store, a scratch file) and put a compact reference —
  an id, a path — in context instead. Truncation *loses* data the agent might need two turns
  later; offloading keeps it reachable on demand instead of paying for it up front.
- **The tool-count tax.** Every registered tool's full schema and description ride in context on
  every turn, and a large or overlapping toolset does not just cost tokens — it costs accuracy.
  Two tools with near-identical descriptions (a book example: `search_documents` vs
  `search_files`) measurably increase the model's mis-selection rate, because the model is
  choosing from prose, not from a lookup table (source: the book's ch. 4 §4.2.1, not ch. 3, even
  though it is filed here because the destination is tool design either way). Two responses, not
  mutually exclusive: keep each agent's toolset small and non-overlapping by construction, or
  retrieve only the relevant subset. **Semantic tool discovery** is the retrieval answer — index
  tool definitions (name, description, schema) in a vector store and fetch only the top-k relevant
  tools into context for a given turn, instead of loading the whole registry every time.
  `langgraph-bigtool` (`langchain-ai` org, `pip install langgraph-bigtool`) is a concrete
  implementation checked this round: a `create_agent()` wrapper over a tool-name→tool registry,
  backed by LangGraph's `Store` (in-memory or Postgres) for the embedding index, with a
  `retrieve_tools_function` hook for custom selection logic. Verify the exact API against the
  package's current docs before using it — this is a young library.
- Timeouts and error text designed for the model: a clear "what went wrong + what to try"
  string beats a stack trace.
- Registering a tool does not make the model use it. When a tool result must ground the answer,
  the agent's instructions have to say so — call the tool first, and constrain the output to what
  it returned. "You have a search tool" leaves the model free to answer from its training data
  instead; "begin by calling `search`, and use only the sources it returns" is what actually
  binds the answer to the tool. This is a persona/instruction job (`engineer-prompt-context`),
  not something the tool schema can enforce on its own.

## Handling tool failure as normal control flow

Timeouts, malformed arguments, rate limits, and downstream outages are not edge cases for an
agent that calls tools in a loop — they are the common case at scale, and how they're handled is
what separates a demo from a production agent. **Verified live, not just asserted:** an MCP tool
that raises inside its own handler does not raise on the client — it comes back as an ordinary
result with `isError` set, so "surface the failure and let the agent decide" is the *only* path a
well-behaved MCP client has; there is no separate exception channel to accidentally skip. Treat a
tool failure the same way you'd treat any other observation: surface the error text back to the
model (a clear "what went wrong" beats a raw stack trace — see the tool design rules above) and
let the agent choose among a bounded set of moves, not an open-ended retry:

- **Retry** — for transient failures (timeout, rate limit); cap the count, and back off between
  attempts (exponential backoff with jitter — fixed-interval retries from many failed calls at
  once resynchronize into another wave of the same collision, "thundering herd"; jitter spreads
  them back out). **Retries of a mutating call need an idempotency key** — a stable identifier
  derived from the call's intent (e.g. a hash of the tool name plus its arguments plus a
  caller-assigned operation id) that the tool implementation checks before acting, so a retried
  `create_` call cannot execute twice. This is ordinary distributed-systems practice (the same
  shape as an HTTP `Idempotency-Key` header); it matters here because a looping agent retries far
  more casually than a human clicking "submit" twice.
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
- **Streamable HTTP has its own non-negotiables, from the spec's security-warning section**
  (checked 2026-07-21 against revision 2025-11-25): servers **MUST** validate the incoming
  `Origin` header and respond `403 Forbidden` to an invalid one (this guards against DNS
  rebinding — a page in the user's browser making requests to a server listening on their own
  machine); a local server **SHOULD** bind to `127.0.0.1`, not `0.0.0.0`, so it is not reachable
  from the network at all; and servers **SHOULD** implement real authentication. A demo that binds
  to all interfaces with no `Origin` check is not a smaller version of a production server — it is
  missing the specific protections the spec calls out by name.

## Operational notes

- Log every tool call (name, args hash, duration, outcome) — agent debugging is tool-log
  reading.
- Rate-limit and budget tools independently of the model (a looping agent can hammer an API).
- Test tools without the model first (unit tests on schemas/edge cases), then with scripted
  model scenarios; most "agent bugs" are tool contract bugs.
- **The MCP inspector** (`npx @modelcontextprotocol/inspector <command>`) is the debugging surface
  built for this protocol specifically: a browser UI (default port 6274) plus a local proxy
  (default port 6277, bound to localhost by default) that connects to a server over stdio,
  SSE, or Streamable HTTP and lets you call tools, read resources, and get prompts by hand,
  watching the raw JSON-RPC traffic. Reach for it before writing a second or third primitive by
  hand against an untested client.

## Worked example

`build-ai-examples/references/mcp-example.md` — a scratchpad-journal MCP server (all three
primitives, both current transports) plus a LangGraph agent reaching it through
`langchain-mcp-adapters`; code in `build-ai-examples/scripts/mcp_example/`. Verified live this
round: the stdio round-trip (`tools/list`, `tools/call`, both resource forms, `prompts/get`), the
Streamable HTTP transport via a raw `curl` request, and the MCP-to-LangChain tool bridge — not
just written and assumed to work.
