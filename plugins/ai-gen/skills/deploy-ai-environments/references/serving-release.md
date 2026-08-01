# Serving topology and release engineering

`local-docker.md` and `cloud-aws-gcp-azure.md` answer **where** an agent runs. This file
answers what happens once it is user-facing: which runtime and communication channel fit the
latency target, how a request reaches the right backend, how a service degrades instead of
erroring, and how a change ships without surprising anyone.

## Choosing a runtime by latency, not by habit

Latency is the deciding variable, not architecture preference:

- **Edge (browser/mobile)** — agent logic runs client-side and streams to a realtime model.
  Lowest perceived latency, best for conversational/voice UI. Keep tools simple and stateless,
  or proxy them through the backend; never mint long-lived secrets into client code (see
  "Browser deployment" below).
- **Synchronous API microservice** — an agent wrapped in a web service, called request/response.
  The default for lookup, formatting, summarization, image generation — anything a caller can
  wait a bounded time for.
- **Event-driven worker** — long or bursty tasks go to a queue; a worker processes them
  asynchronously, with retries and concurrency control the queue gives for free. The fit for
  anything that would exceed an HTTP timeout.

Start with the synchronous API — it is the simplest runtime with the fewest moving parts. Move a
path to edge only once its latency requirement demands it; move a path to event-driven workers
only once its duration or burstiness demands it. Picking the more complex runtime by default is
the more common mistake than picking the simpler one and having to upgrade it.

## The three communication "wires" — and where MCP actually fits

Communication between a client and an agent (or between agents) runs over one of three
practical channels, each with a different latency/complexity tradeoff:

- **WebRTC/WebSocket (realtime)** — full-duplex, minimal overhead, supports interruption
  ("barge-in") and token-by-token streaming. The right choice for voice UX and interactive
  canvases; overkill for anything that tolerates request/response latency.
- **HTTP with streaming output (SSE or chunked)** — simple request/response with a streamed
  body. Easy to proxy, log, and cache. The right default for tool calls and for web clients that
  want streamed text but do not need full duplex.
  **This wire is not MCP, and naming it "(MCP)" is a mislabel worth correcting explicitly**
  (a genuine and repeated error in one popular source): MCP is an application-layer protocol
  with its own transport story — **stdio** for a locally-launched server, **Streamable HTTP**
  for a remote one, with SSE as a streaming *mechanism* Streamable HTTP may use internally, not
  a standalone transport (`mcp-tools.md` has the full correction and the deprecated
  "stdio + SSE" pairing to watch for). If MCP is the actual protocol in play, cite
  `mcp-tools.md`'s transport section — do not describe MCP's wire as "HTTP + SSE."
- **Message bus (queues)** — Redis/NATS/Kafka-class decoupling for tool execution that should
  not block the session. The user keeps talking while a slow tool runs; the result posts back
  when ready. The event-driven-worker runtime's natural communication wire.

Pick the wire the same way as the runtime: by the latency and duplex requirement of the specific
interaction, not uniformly across the whole system — a single front-door deployment legitimately
mixes wires, one per worker, as below.

## The front-door pattern

A single user-facing entry point fans out to backend workers or services, each free to use the
runtime and wire that fits its own latency profile — this is `architectures.md`'s
orchestrator-workers pattern applied specifically to serving topology, not a new architecture.
The front-door agent should stay as thin as possible: routing and light orchestration, with the
actual work and control kept inside each worker. A voice-realtime front door might dispatch to a
synchronous-API worker for a quick lookup and to an event-driven worker (queue) for a slow
image-generation job — different wires, different runtimes, one entry point for the user.

## Browser deployment is a security decision, not a convenience one

Running agent logic directly in the browser is the simplest way to ship a prototype, and it has
three failure modes worth naming before committing to it in anything customer-facing:

- **API keys in client-side code are extractable** by anyone who opens developer tools —
  effectively public, regardless of intent.
- **CORS blocks direct browser calls** to most LLM and tool endpoints by default; the fix is
  either backend CORS configuration or a server-side proxy, not working around the block.
- **Shared vs. per-browser rate limits both fail**, in opposite directions: one key shared
  across browsers means one user can exhaust the quota for everyone; a key per browser
  reintroduces the extractability problem above.

Browser-embedded agents are reasonable for prototypes, internal tools with trusted users, and
apps that already proxy LLM calls through their own backend. Anything customer-facing with cost
or security stakes belongs behind an authenticated backend that holds the credentials, handles
CORS, and manages rate limits server-side — with **ephemeral, server-minted secrets** handed to
the browser only after the backend's own auth, never a standing key.

## Tunnels are a development tool, not a deployment

`ngrok`/`localtunnel`-class tunnels expose a locally running service to the public internet
through an externally reachable URL. Useful for demos and debugging; wrong for anything beyond
that, because the tunnel inherits none of a real deployment's security boundary — the endpoint is
reachable by anyone with the URL for as long as the tunnel runs, and whatever the local agent can
reach becomes reachable too. When a tunnel would need to run "for a while" or handle real traffic,
that is the signal to deploy instead — cloud deployment provides the security boundary,
networking, scaling, and access control a tunnel deliberately does not.

## Reliability: a ladder, not a single check

Treat each critical path's failure handling as an ordered ladder, each rung catching what the
one before it did not:

1. **Time budget, enforced at the caller.** Every critical path gets an SLA (a quick-reply path
   and a tool-call path have different budgets); a call that exceeds its budget is treated as a
   failure and handed to the next rung — the budget is enforced by the code that made the call,
   never trusted to the callee.
2. **Fallback.** On failure or budget breach: a best-effort answer, a smaller/faster model, or
   dropping non-essential decoration (an image, a citation list) rather than failing the whole
   turn.
3. **Circuit breaker.** Repeated failures on the same dependency trip the breaker: stop calling
   it for a cooldown window and shed load immediately instead of paying the timeout cost on every
   request while a downstream service is down.
4. **Graceful degradation.** The end user never sees a raw error. If a voice path fails, continue
   as text; if an image tool is slow, return a link to retrieve it later. The ladder's whole point
   is that something usable comes out the other end.

See `build-ai-examples/references/reliability-example.md` for this ladder as a tested state
machine.

## State, memory, and idempotency (design rule; the failure mode is the worked example)

Conversational (short-term) state and long-term knowledge belong in different stores — fast
session storage (Redis/Postgres-class) for turns, a dedicated retrieval service for semantic
knowledge — the same split `memory-vector-db.md` already makes; nothing new here.

Design every tool call to be **idempotent and keyed by an explicit, caller-supplied operation
id** — not by hashing the call's arguments. Hashing only the arguments is the specific,
reproducible failure this round's worked example is built to catch: two *legitimately distinct*
operations that happen to share arguments (a retry of the same logical action vs. two separate
actions that look identical on the wire) collide under an argument-only key, and the second one
silently returns the first's cached result instead of executing. The cache key must include
something that distinguishes *intent to execute this specific operation* from *these particular
argument values* — that is what an operation id is for.

## Release engineering: agents are software, ship them like software

Three practices, in order of how often they get skipped:

- **Version everything** — prompts, tool schemas, tool-server versions, safety switches, model
  selections. Versioning prompts alongside code is usually sufficient; versioning them
  separately buys the ability to change a prompt without a code deploy, at the cost of another
  thing to track.
- **Promote with gates** — offline evaluation first (see `evaluate-optimize-models`), then
  shadow traffic (real requests, response not shown to the user, compared against the current
  version), then a small canary (a limited slice of real users), then full rollout with
  automatic rollback if service-level objectives degrade. Skipping straight from offline eval to
  full rollout is the release-engineering equivalent of skipping the minimum-change ladder in
  `agent-tdad.md` — the same discipline, one level up.
- **Pin and record exact versions per turn** — which model, which tool endpoint, which prompt
  version answered *this specific turn*, not just "which version is deployed now." Without this,
  reproducing an incident from a trace is guesswork; trajectory tracing (`agent-ops.md`) is what
  makes the record possible, this is the discipline that makes it complete.
