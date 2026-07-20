# RAG pipeline: stages, failure modes, and the levers that actually help

RAG is two pipelines, not one: an **offline ingestion** pipeline that compiles a corpus into a
searchable index, and an **online serving** pipeline that answers a question from it. Most
"our RAG is bad" reports are a defect in one specific stage, and the fix is cheap once you know
which. Debugging RAG as a single black box is the most expensive way to work on it.

The original formulation (Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive
NLP Tasks", NeurIPS 2020, <https://arxiv.org/abs/2005.11401>) frames it as combining
**parametric memory** — knowledge in the generator's weights — with **non-parametric memory**,
a dense vector index reached through a retriever. That split is still the useful mental model:
you are choosing what the model should know versus what it should look up.

Scope note: chunking policy, store selection, hybrid search and the same-model embedding rule
live in `memory-vector-db.md` and are cross-referenced here rather than restated. What a
retrieval failure means for the *architecture* decision is in `architectures.md`; whether RAG is
the right rung at all is `select-genai-models/references/build-vs-use.md`. Questions this
pipeline cannot answer *by construction* — global, thematic, and multi-hop ones — are
`graph-rag.md`.

## What RAG fixes, and what it does not

| Symptom | Is RAG the fix? |
|---|---|
| Answers are out of date, or miss private/internal facts | **Yes** — this is the case RAG exists for |
| Answers need to cite a source a human can check | **Yes** — retrieval gives you the citation surface |
| Wrong format, wrong tone, ignores instructions | **No** — behavior defect; rungs 0–1, or fine-tuning |
| Reasoning is weak on facts already supplied | **No** — the context was there and the model failed to use it |
| Corpus is small and static and fits in the context window | **Probably not** — just put it in the prompt and skip the pipeline |
| Question is about the corpus *as a whole* ("main themes across all reports?"), or joins facts that never share a chunk | **Not this pipeline** — top-k cannot cover a corpus and reranking cannot fix it; see `graph-rag.md` |

The last row matters more than it looks: a pipeline you do not build cannot break. Recommend
long-context stuffing when the corpus genuinely fits and is stable, and say what would change
the answer (corpus growth, per-call token cost, latency).

## Ingestion pipeline (offline)

Stage order follows the standard workshop decomposition — load → split → embed → store (Tom Yeh,
"Beginner's Guide to RAG — AI by Hand", 2024, <https://by-hand.ai/rag>; the deck is a by-hand
exercise workbook, used here as a stage map, not as an explanation to cite).

### 1. Load

Get documents out of their source format into text plus metadata.

- **Failure mode:** silent extraction loss. PDFs with columns interleave, tables flatten into
  word soup, scanned pages yield nothing, HTML drags in navigation chrome. The pipeline reports
  success and the content is already destroyed.
- **Counter-measure:** eyeball the extracted text for a sample of every source *type* before
  building anything on top. Keep source URI, section, and date as metadata from this stage —
  you cannot reconstruct them later, and citations depend on them. Format-by-format mechanics
  (PDF layout, tables, OCR, speech-to-text, multimodal parsing) plus index-time enrichment are
  in `build-ai-examples/references/document-loading.md`.

### 2. Split

Cut documents into retrievable units.

- **Failure mode:** chunks that sever the answer from its context (definition in one chunk, the
  qualifying condition in the next), or chunks so large the relevant sentence is diluted among
  irrelevant ones.
- **Counter-measure:** split on semantic units with overlap; see `memory-vector-db.md` for the
  chunking policy. Tune chunk size against your own retrieval eval, not against a blog default.
  Overlap is the cheap insurance against boundary-severed answers, and it costs index size.

### 3. Embed

Turn each chunk into a vector.

- **Failure mode:** a model mismatch between query and corpus embeddings (silent degradation to
  noise — the same-model rule in `memory-vector-db.md`), or an embedding model that was never
  suited to the domain/language.
- **Counter-measure:** version the index by embedding-model ID; changing the model means
  re-embedding the corpus, and that must be a planned migration, not a config edit.

### 4. Store

Write vectors plus metadata into an index.

- **Failure mode:** staleness. The corpus moves and the index does not, so the system answers
  confidently from deleted or superseded documents.
- **Counter-measure:** treat re-ingestion as a scheduled job with a freshness metric, and carry a
  document timestamp into the metadata so answers can be filtered or caveated by age.

## Serving pipeline (online)

### 1. Query construction

What actually gets embedded is rarely the raw user message: in a chat, the question may be
elliptical ("and the second one?"). Rewrite the query against conversation history before
retrieval.

- **Failure mode:** retrieving on a pronoun. Recall collapses and nobody looks here first.

### 2. Retrieve

Nearest-neighbour search, usually hybrid (dense + keyword) — see `memory-vector-db.md`.

- **Failure mode:** the relevant passage is not in the top-k at all. Everything downstream is
  then decoration; the generator cannot cite what it never received.
- **Counter-measure:** measure recall@k on a labelled question→passage set *before* touching the
  prompt or the model. This is the single highest-value measurement in RAG work.

### 3. Rerank (optional)

Reorder the retrieved candidates with a stronger, slower scorer. See the next section.

### 4. Assemble the context

Order the passages, deduplicate, attach source labels, and fit the token budget.

- **Failure mode:** dumping every retrieved chunk in arbitrary order. Attention is finite (see
  the context-budget discussion in `memory-vector-db.md`); burying the best passage in the
  middle of ten mediocre ones measurably wastes it.
- **Counter-measure:** fewer, better passages beat more passages. Label each with its source so
  the model can cite it, and so a human can audit the citation.

### 5. Generate, grounded

- **Failure mode:** the model answers from parametric memory while retrieved text sits unused —
  fluent, confident, and unsupported by the sources shown next to it.
- **Counter-measure:** instruct explicitly to answer *only* from the context, to cite the source
  label per claim, and to say "not in the provided sources" when it is not. Then measure
  groundedness rather than trusting the instruction — see `evaluate-optimize-models`.

## Choosing the embedding model (a procedure, not a leaderboard)

MTEB (Muennighoff, Tazi, Magne & Reimers, "MTEB: Massive Text Embedding Benchmark", 2022,
<https://arxiv.org/abs/2210.07316>) covers 8 task types across 58 datasets and 112 languages.
Its headline finding is the reason to treat it as a *filter* rather than a ranking: the paper
reports that **no single text embedding method dominates across all tasks**.

So the procedure is:

1. Filter the leaderboard by the task type that matches your use (retrieval — not classification
   or clustering, which are different columns and different winners).
2. Filter by your language(s) and by the domain closest to your corpus.
3. Filter by hard constraints: max sequence length versus your chunk size, vector dimensionality
   versus what your store supports, licence, and whether it can be self-hosted if privacy
   requires it.
4. Take the 2–3 survivors and measure them **on your own labelled retrieval set**. A public
   score is a shortlist input; your recall@k on your corpus is the decision.

Never quote a current MTEB position as a fact in an answer: the leaderboard changes constantly.
Teach the filter, and tell the user to read the live board at decision time.

## Advanced retrieval: what each buys and what it costs

Reach for these only when the measurement says retrieval is the bottleneck. Each adds latency,
cost, and a component that can fail on its own.

### Cross-encoder reranking

Retrieve a wide candidate set with the fast bi-encoder, then rescore the top candidates with a
cross-encoder that reads query and passage *together*.

- **Buys:** the largest quality gain per unit of effort in most pipelines, because it fixes
  ranking without touching ingestion.
- **Costs:** one model inference per candidate — latency grows with the candidate count.
- **Fails by:** reranking a candidate set that never contained the answer. Reranking cannot
  recover recall it was not given; widen k first, then rerank.

### LLM reranking (RankGPT-style)

Have an LLM order the passages by relevance. Introduced by Sun et al., "Is ChatGPT Good at
Search? Investigating Large Language Models as Re-Ranking Agents" (EMNLP 2023,
<https://arxiv.org/abs/2304.09542>), which uses a permutation-generation approach.

- **Buys:** strong zero-shot ranking with no ranking-specific training data.
- **Costs:** the most expensive option per query — it puts a full LLM call in the retrieval path.
- **Note worth citing:** the same paper distils this ability into small specialist models,
  reporting a distilled 440M model outperforming a 3B supervised model on BEIR. The practical
  reading: if LLM reranking helps your case, a small dedicated reranker is likely the deployable
  form, not the LLM call itself.

### Multi-query retrieval

Have an LLM generate several paraphrases of the question, retrieve for each, and merge the
results (a LangChain `MultiQueryRetriever`-style pattern; the technique is folk-standard
practice, not a single canonical paper).

- **Buys:** robustness to vocabulary mismatch between how users ask and how documents are written.
- **Costs:** one extra LLM call plus N retrievals per question; merging needs a rule
  (reciprocal-rank fusion is the usual choice).
- **Fails by:** paraphrases that all drift the same way, multiplying cost while retrieving the
  same wrong neighbourhood.

### Contextual compression

After retrieval, use a model to strip each passage down to the parts relevant to the query.

- **Buys:** more effective passages inside a fixed token budget; less distraction for the
  generator.
- **Costs:** an extra model pass over every retrieved passage.
- **Fails by:** compressing away the qualifier that made the answer correct. This is a real risk
  and it fails *silently* — the answer looks better sourced while being subtly wrong.

### HyDE (hypothetical document embeddings)

Gao, Ma, Lin & Callan, "Precise Zero-Shot Dense Retrieval without Relevance Labels" (2022,
<https://arxiv.org/abs/2212.10496>). An instruction-following model writes a *hypothetical*
answer document; that document is embedded by an unsupervised encoder, and the resulting vector
is used to find real documents nearby. The generated text is never shown to the user — the paper
describes the encoder's dense bottleneck as filtering out the hypothetical document's incorrect
details.

- **Buys:** better zero-shot retrieval when no relevance labels exist and the query is short or
  phrased unlike the corpus.
- **Costs:** an LLM call before every retrieval.
- **Fails by:** hallucinating a document from a domain the model does not know, which lands the
  search in the wrong neighbourhood. Weakest exactly where private-corpus RAG is most needed.

## Order of work when RAG underperforms

Diagnose before adding components. In payoff order:

| Measurement | What it means | First lever |
|---|---|---|
| recall@k is low | The answer never reaches the generator | Chunking, query rewriting, hybrid search, wider k |
| recall@k fine, answer wrong | Ranking or assembly | Reranking; fewer/better passages; passage order |
| Answer ignores good context | Prompt/grounding defect | Explicit grounding instructions; measure groundedness |
| Answer right, citation wrong | Metadata or labelling | Carry source metadata from the load stage |
| Everything fine, too slow/expensive | Efficiency, not quality | Cache, shrink k, drop the LLM from the retrieval path |

Adding HyDE, multi-query, and reranking all at once to an untested pipeline is the standard
mistake: cost triples, latency triples, and nobody can attribute the change.

## Production concerns the stage list does not cover

Everything above gets a pipeline working. The three below decide whether it survives contact
with real traffic, real users, and a corpus other people can write to. They are **engineering
practice** rather than results from a paper — where a specific claim has a source, it is cited;
where it does not, it is stated as practice and you should check it against your own system.

### Hallucination: detect, then *correct*

Detection is the part most pipelines implement and stop at. Groundedness has to be checked
**per claim**, not per answer — an answer that is 90% supported is not 90% correct, it is one
false sentence away from misleading someone. Workable checks, cheapest first:

- **Mechanical citation verification.** Require the generator to emit an explicit claim →
  source-label mapping, then check *in code* that each cited chunk was actually retrieved and
  actually contains supporting text. A surprising share of hallucination is a citation pointing
  at a passage that does not say what the sentence claims, and that is catchable without a model.
- **Entailment scoring.** Score each claim against its cited passage with an NLI-style model.
  Cheaper than an LLM judge and it produces a per-claim number you can threshold.
- **Self-consistency.** Sample the answer several times; claims that appear inconsistently across
  samples are the unstable ones. Costs N generations, so reserve it for high-stakes paths.

**Correction is the missing half.** Once a claim fails, decide by *where* the failure lives:

| Diagnosis | Correction |
|---|---|
| Claim is unsupported, but the corpus does contain the fact | Re-retrieve **using the failed claim as the query** — a specific claim is often a better query than the original question — then regenerate |
| Claim is unsupported and the corpus has nothing | Strip the claim and re-answer from what remains; if nothing remains, abstain |
| Claim is supported but cited to the wrong passage | Repair the citation, keep the claim — a labelling defect, not a hallucination |
| Whole answer drifts from the retrieved set | Regenerate with the failed claims named explicitly in the instruction |

Two rules around this loop:

- **Abstention is a first-class outcome and must be measured.** A system that never says "not in
  the provided sources" is not grounded, it is confident. Track the abstention rate the way you
  track accuracy; both a zero and a runaway rate are defects.
- **The corrector must not share the generator's context and prompt**, or it rehearses the same
  reasoning and confirms the same error — the maker-checker rule in `loop-engineering.md`.

### The retrieval surface is an attack surface

`architectures.md` states the general rule: tool output is data, not commands. **Retrieved
documents are tool output.** A document containing instructions is therefore a delivery
mechanism, and anyone who can put a document into the corpus can attempt to steer the model.

Start from the write paths, because that list *is* the threat model. In most real deployments
it is longer than the design assumed: shared drives, ticket systems, wiki pages anyone can edit,
customer-submitted attachments, scraped web pages, and auto-ingested email. If ingestion is
automatic, a hostile document is one upload away from being ranked first for the query it
targets.

Counter-measures, none of which is sufficient alone:

- **Structural delimitation.** Retrieved text goes in a clearly bounded region, with an explicit
  instruction that content inside it is never an instruction. Weak on its own, free to add.
- **No tool calls triggered by retrieved content** without an independent check. This is the
  control that actually prevents damage, because it breaks the path from "model was fooled" to
  "something irreversible happened".
- **Provenance and trust tiers in metadata.** A customer-submitted document must not be able to
  outrank a policy document. Trust is a retrieval-time filter, not a prompt-time hope.
- **Output-side guardrails independent of the generator** — a separate check that the answer
  contains no exfiltrated secrets and no attempt to trigger an action.

This is not hypothetical. A review of agent-based annotation systems records adversarial control
of an agent's output corrupting stored records at scale before rollback, and concludes that
hallucination, bias and adversarial control are measurable failures already disrupting real
pipelines rather than theoretical risks — while also noting that robustness against
adversarial and prompt-injection attacks is *rarely covered* in the literature (Karim, Khan, Van,
Liu, Wang & Qu, "Transforming Data Annotation with AI Agents", *Future Internet* 2025, 17(8),
353, <https://doi.org/10.3390/fi17080353>, §1 and §10.1). Read that second half as the reason to
design this yourself rather than expecting the field to have solved it.

### Index freshness at scale

The Store stage says to schedule re-ingestion and carry a timestamp. At scale that is the
beginning, not the answer:

- **Deletion is the hard direction.** A document removed at the source must be removed from the
  index, or the system answers confidently from retracted material — the failure with legal
  consequences attached. Full rebuilds mask the problem; incremental pipelines need an explicit
  tombstone path, and it needs a test.
- **Measure staleness of what was *retrieved*, not of the job.** "The indexer ran at 04:00" says
  nothing about whether the passage that answered this question is current. Log the age of the
  passages behind each answer and alert on the tail.
- **Re-embedding is a migration, not a config change** (`memory-vector-db.md`): build the new
  index alongside the old one and cut over, rather than mutating in place and serving a half-
  migrated index.
- **A graph index has a second staleness surface.** Community summaries are pregenerated, so they
  can be stale even when the underlying graph is current — see `graph-rag.md`.

## Evaluation hooks

The two-stage split is non-negotiable, and `evaluate-optimize-models/references/evaluation.md`
carries the metrics: **retrieval** by recall@k and MRR on labelled question→passage pairs;
**generation** by groundedness and citation correctness. Evaluate them separately or you cannot
localize a failure — which is the same point this file opens with, and the reason it is worth
repeating.
