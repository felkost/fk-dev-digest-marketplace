# Worked example: an MCP server + LangGraph agent (`mcp_example`)

Runnable code lives in `scripts/mcp_example/`. A `server.py` exposes a scratchpad journal through
all three MCP primitives (tool, resource, prompt) on the official Python SDK; `agent.py` reaches
it from a LangGraph agent via `langchain-mcp-adapters`. The concepts — primitives, transports,
tool design, failure handling — are in `design-agent-architecture/references/mcp-tools.md`; this
file covers the build, and the two concrete corrections this example makes to a source the plugin
already triaged (see `HANDOFF.md` round 13).

## Contents

- Run it
- Layout
- Decisions worth explaining
- What the tests pin (47 offline total, this file's share 9, + 10 live, all actually run)
- Production deltas

## Run it

```bash
cd scripts/mcp_example
pip install -r requirements.txt
python test_live_stdio.py                 # free: no key, no network beyond localhost
cp .env.example .env                       # fill in OPENROUTER_API_KEY -- get one at openrouter.ai
python agent.py "jot down that the meeting moved to 3pm"
```

`server.py` needs no key at all — an MCP tool call is not a model call. Only `agent.py` spends
OpenRouter credit, and only when you run it.

## Layout

```
scripts/mcp_example/
├── journal.py          # pure: note store (add/get/list/format), no `mcp` import
├── server.py           # framework: FastMCP wiring, all 3 primitives, transport CLI flag
├── agent.py             # framework: LangGraph agent reaching server.py via langchain-mcp-adapters
├── test_live_stdio.py  # free live check: real subprocess, real protocol round-trip
├── .env.example
└── requirements.txt
```

## Decisions worth explaining

### 1. The companion repo's two bugs, corrected here

The book's companion repo (`cxbxmxcx/AI-Agent-Workflows`, `chapter_03/`) supplied the shape and
two things not to copy:

- `01_complete_mcp_server.py`'s `welcome()` prompt calls `get_greeting(name)` **directly, as a
  plain Python function**, bypassing the resource protocol — it works only because everything
  happens to share one process. `summarize_notes()` here does not do that: it returns an
  instruction naming `journal://notes`; the caller fetches the resource itself, through the
  protocol, the same as a remote client would have to. Verified live: `test_live_stdio.py`'s
  "prompt names the resource instead of inlining its contents" check asserts the prompt text
  contains the resource URI and does **not** contain a note's actual content.
- `06_mcp_time_travel_tracker.py` ends in `mcp.run(transport="sse")` — the transport the current
  spec (revision 2025-11-25, checked 2026-07-21 via the versioning page) deprecates.
  `server.py` defaults to `stdio` and accepts `--transport streamable-http`; both were run for
  real this round (see "What the tests pin" below), not just written.

### 2. Two spellings for "streamable HTTP" in the same two-package stack

Verified against source, not remembered: the official SDK's own `FastMCP.run()` takes
`transport: Literal["stdio", "sse", "streamable-http"]` — **hyphenated**. `langchain-mcp-adapters`'
client-side connection config takes `transport: Literal["stdio", "sse", "streamable_http"]` —
**underscored** (its `create_session()` also accepts `"streamable-http"` and `"http"` as aliases,
but the base type is the underscored form). `server.py` and `agent.py` each use the spelling their
own library expects; the mismatch is exactly the kind of cross-library identifier drift
`CLAUDE.md`'s "tool documentation is a moving target" rule warns about — re-check both spellings
against current source before copying either into new code.

### 3. Tool errors are data, not exceptions — confirmed live, not just asserted

`add_note("   ")` raises `ValueError` inside `journal.py`. Over the wire, that does **not** raise
on the client: `test_live_stdio.py` calls it and asserts `result.isError is True` on an ordinary
`CallToolResult`, with no `try`/`except` needed. This is `mcp-tools.md`'s "handling tool failure
as normal control flow" section, confirmed at the protocol level rather than only stated in prose.

### 4. Why `stdio` is the default transport, and how `streamable-http` was actually checked

The spec itself says "Clients SHOULD support stdio whenever possible", and the plugin's test
ladder needs a subprocess-only free check — both point at `stdio` as the default. `streamable-http`
is real code, not a documented-but-untested flag: this round started `server.py --transport
streamable-http` and sent a raw JSON-RPC `initialize` request with `curl`, receiving back
`{"protocolVersion":"2025-11-25", ..., "serverInfo":{"name":"Scratchpad","version":"1.28.1"}}`
over HTTP 200. That check is manual (spinning up and tearing down a bound port does not belong in
an offline suite) — re-run it by hand if you change the HTTP path, the same way you would after
touching `docker-compose.yml` in `rag_example`.

### 5. The MCP-to-LangChain bridge was verified live, without spending a model call

`client.get_tools()` (from `langchain_mcp_adapters.client.MultiServerMCPClient`) launches
`server.py` as a real subprocess and converts `add_note` into a LangChain tool — this was run for
real this round and returned the tool's name, its docstring as the description, and its
JSON-schema args, all pulled from the live server, not asserted from documentation. Getting this
far costs nothing; only the model call inside `agent.py`'s `ainvoke` spends OpenRouter credit.

## What the tests pin

Two tiers, both actually run this round — not just written.
`python tests/smoke_test.py` has 47 checks total, all four examples this plugin ships;
mcp_example's share is checks 19-27 (the other three examples' shares are in `rag-example.md`,
`reflexion-example.md` and `guardrail-example.md`):

| Tier | Where | What it needs | Result |
|---|---|---|---|
| Offline pure logic | `tests/smoke_test.py` checks 19-27 | bare interpreter | 9/9 this file's share (47/47 whole file) |
| Live protocol round-trip | `scripts/mcp_example/test_live_stdio.py` | `mcp` installed, no key/network | 10/10 |

The offline tier pins `journal.py` only: sequential ids, blank text rejected, an unknown id reads
as `None` rather than raising, and an empty journal names itself `"(journal is empty)"` instead of
returning `""` (silently-empty output and a genuinely absent resource are different failures for a
caller to distinguish).

The live tier drives `server.py` as a subprocess exactly the way `langchain-mcp-adapters` or any
other MCP client would: `initialize`, `tools/list`, `tools/call`, `resources/list`,
`resources/read` (both the fixed `journal://notes` and the templated `journal://notes/{note_id}`),
`prompts/list`, `prompts/get`. It is what caught decision 3 above — the first version of this test
asserted the wrong thing (a raised exception) and failed against a server that was already correct;
the test was wrong, not the server, and only running it for real surfaced that.

**Not run this round, and it needs the user's OpenRouter key to change that:** `agent.py`'s actual
`ainvoke` call. The bridge up to that point (tool discovery, subprocess launch) was verified live;
the model turn itself was not, per the plugin's standing rule that spending the user's credit
needs their say-so first.

## Production deltas (state these with the example)

This is a teaching scaffold. Before it carries real traffic:

- **Persistent journal.** `_journal = Journal()` is an in-memory, per-process list — restart the
  server and it is gone. This is also the concrete instance of `mcp-tools.md`'s "state-semantics
  shift": the moment more than one client reaches this same process, `_journal` stops meaning "my
  notes" and starts meaning "everyone's notes," and nothing in the code marks that transition.
- **Auth and network exposure for `streamable-http`.** This example binds to `127.0.0.1` (the
  SDK's own default) and does no authentication — fine for a local demo, exactly what the spec's
  security section forbids shipping as-is: validate `Origin`, and add real authentication before
  this leaves localhost.
- **Idempotency on retries.** `add_note` has no idempotency key; calling it twice files two notes.
  Fine for a scratchpad, wrong for anything that mutates money or inventory — see `mcp-tools.md`'s
  retry section for the mechanism.
- **Structured logging per call**, not the plain `stderr` a bare `FastMCP` instance writes —
  `mcp-tools.md`'s operational notes.
- **The MCP inspector** (`npx @modelcontextprotocol/inspector python server.py`) is the tool to
  reach for once you are adding a fourth or fifth primitive and want to see the live schema rather
  than re-reading decorator source.
