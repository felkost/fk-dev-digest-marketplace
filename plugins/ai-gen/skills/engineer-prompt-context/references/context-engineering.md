# Context engineering: curating what the model attends to

Prompt engineering asks "what do I write?". Context engineering asks "what should be in the
window *at this step*, and what should not?" — a question that only appears once a system runs
for many turns with tools, retrieval and history competing for the same finite space.

Primary source: Anthropic, "Effective context engineering for AI agents"
(<https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>).

## The distinction

| | Prompt engineering | Context engineering |
|---|---|---|
| Scope | Writing and organizing the instructions | Curating **all** tokens present at inference, including what arrives from tools, retrieval and history |
| Unit of work | One call | A whole trajectory of calls |
| Typical question | "How do I phrase this task?" | "What should this step see, and what should be dropped or summarized?" |
| Fails as | Ambiguous or under-specified instructions | A window full of low-signal tokens; the model losing the thread mid-task |
| Owner in this plugin | `references/prompt-techniques.md` | this file |

The source defines context engineering as the strategies for curating and maintaining the
optimal set of tokens during inference, and prompt engineering as methods for writing and
organizing instructions. The second is a component of the first — not a rival to it.

## Why context is a finite resource

The constraint is architectural, not a product limitation. In a transformer every token attends
to every other token, so relationships grow quadratically with length. The source describes
models as having an **attention budget** that each new token depletes, and names the observed
degradation **context rot**: quality falls as token count rises, well before any hard limit is
reached.

Two consequences worth stating to users, because both are counter-intuitive:

1. **A bigger context window is not a solution.** It raises the ceiling on what fits; it does
   not raise the ceiling on what is *attended to*.
2. **Adding relevant information can make output worse.** If it displaces or dilutes the
   critical part, net signal falls. The goal is the smallest set of high-signal tokens, not the
   largest set of true ones.

The common shorthand — "the window is the model's RAM" — is a useful analogy for teaching, but
it is folk framing, not from the source. The attention-budget formulation is the one to cite.

## Techniques for long-horizon work

All three are from the source, and all three are ways of keeping durable state **outside** the
window.

### Compaction

When the conversation approaches the limit, summarize it and reinitialize with the summary plus
the most recent turns. What survives should be architectural decisions and unresolved issues —
what gets discarded is redundant tool output.

- **Fails by:** compacting away the constraint that made a decision correct. The summary is now
  the only memory, so anything it drops is gone. Test what a compaction actually preserves.

### Structured note-taking

The agent maintains an external file (a `NOTES.md`-style artifact) and writes progress to it, so
state persists without occupying the window.

- **Fails by:** notes that accumulate without consolidation — the file becomes a second context
  problem. Write decisions and reasons, not a transcript.

### Sub-agent context isolation

A focused sub-agent does detailed work in its own window and returns only a condensed summary
(the source cites roughly 1,000–2,000 tokens), keeping the search trace out of the main thread.

- **Fails by:** a summary that drops what the caller needed, with no way to ask again. And note
  the tension with `design-agent-architecture/references/loop-engineering.md`: isolation is the
  mechanism that makes a *checker* independent, so this is not merely an efficiency trick.

These are the same problem at three scopes as the memory hierarchy in
`design-agent-architecture/references/memory-vector-db.md` — session (compaction), project
(notes / persistent knowledge base), and task (`autonomy-contracts.md`). Link, don't restate.

## Just-in-time retrieval

Rather than pre-loading everything a task might need, keep **lightweight identifiers** — file
paths, queries, links — and load the content at the moment it is needed. The source likens this
to how people work: you do not memorize the filing cabinet, you remember where it is.

- **Buys:** the window holds pointers instead of payloads; the agent discovers context
  progressively.
- **Costs:** more round-trips, and latency that a pre-loaded context does not pay.
- **Fails by:** identifiers the agent cannot resolve, or a corpus where finding the right
  pointer is itself the hard problem — then you need retrieval quality first
  (`design-agent-architecture/references/rag-pipeline.md`).

## Tool design is context design

Every tool schema sits in the window on every call, and every tool result lands in it. The
source's guidance for tools: self-contained, unambiguous, minimally overlapping, and
token-efficient in what they return. Its bluntest test — if an engineer cannot say definitively
which tool applies to a situation, the model will not do better.

Practical rules that follow:

- Trim tool descriptions like you trim a system prompt; they are paid on every call.
- Return the fields the caller needs, not whole API responses. A verbose tool poisons every
  subsequent turn of the trajectory.
- Overlapping tools force a decision the model will sometimes get wrong; merge or delete them.
- Tool *permissions* and the injection surface are architecture, not phrasing —
  `design-agent-architecture/references/mcp-tools.md`.

## Working procedure

1. **Establish the budget.** What must be present every call (instructions, tool schemas) versus
   what is per-step. The fixed part is paid on every call — audit it first.
2. **Order for the position effects.** Stable prefix first (it is also what prompt caching
   rewards), volatile content last. See the Valley of Meh in `prompt-techniques.md`.
3. **Decide the eviction policy before you need it.** Which of compaction, notes, or sub-agent
   isolation applies, and what each is required to preserve.
4. **Externalize state early.** By the time the window overflows, the information you needed to
   save is already gone.
5. **Measure.** Track tokens per solved task alongside quality — a context change that improves
   quality while tripling cost is a trade to state explicitly, not a win
   (`evaluate-optimize-models/references/token-latency-cost.md`).

## Failure modes

- **Optimizing tokens instead of outcomes.** Cutting context until quality drops is not
  efficiency. The metric is cost *per solved task*.
- **Compaction as a background detail.** It is a lossy transformation of the agent's only
  memory; treat it as a designed step with stated invariants.
- **Dumping retrieved documents in whole.** Retrieval quality and context budget are the same
  fight — fewer, better passages (`rag-pipeline.md`).
- **A stable prefix that is not stable.** Injecting a timestamp or session ID near the top
  invalidates prompt caching on every call, for no benefit.
- **Confusing "it fits" with "it works".** Fitting is a precondition; attention is the
  constraint that actually binds.
