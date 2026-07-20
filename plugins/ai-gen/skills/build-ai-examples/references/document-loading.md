# Loading documents: getting text out of real files without losing it

`design-agent-architecture/references/rag-pipeline.md` names this stage's failure mode — **silent
extraction loss** — and tells you to eyeball a sample of every source type. This file is the
*how*: format by format, what breaks, what to reach for, and what to do at ingest time that
retrieval can never recover later.

Everything here is **practitioner technique checked against current tool documentation**, not
results from a paper. Tool and class names drift between releases (the LangChain integrations
page today foregrounds Unstructured, Docling and PyMuPDF-family loaders rather than the
per-format classes it used to lead with), so this file names *mechanisms and tool families* and
expects you to check the current identifier before writing code.

## Contents

- The rule that governs the whole stage
- Format by format
- Choosing a parsing tier
- Index-time enrichment
- Structured outputs
- What to change for production

## The rule that governs the whole stage

**Every loader succeeds.** It returns a string, the pipeline moves on, and nothing anywhere
reports that the tables became word soup or that half the pages were images. By the time
retrieval is bad, the damage is three stages upstream and invisible.

So the deliverable of the Load stage is not text. It is text **plus a sample a human has
actually read**. For each *source type*, pull three documents and check five things:

1. **Reading order** — did a two-column page interleave into nonsense?
2. **Tables** — did rows survive as rows, or collapse into a run-on line?
3. **Headers/footers** — is the same page furniture repeated into every chunk, diluting it?
4. **Footnotes and captions** — did they land attached to the wrong sentence?
5. **Non-text content** — how many images, charts and scanned pages were silently dropped?

Then automate a degeneracy check so this holds after you stop looking: flag any document whose
extracted text is near-empty, whose non-alphanumeric ratio is high, or whose length is wildly
out of line with its file size. Route those to a quarantine queue instead of the index.

## Format by format

| Source | What actually breaks | Reach for |
|---|---|---|
| **Word (.docx)** | Tracked changes and comments extracted as if they were body text; text boxes and headers lost; style information discarded, taking the heading hierarchy with it | A loader that preserves styles — headings are the chunking signal that `memory-vector-db.md` calls structural splitting |
| **PDF (text layer)** | Multi-column interleaving; reading order is *not* guaranteed by the format; ligatures and hyphenation splitting words; page furniture repeated | A layout-aware parser (Docling / Unstructured / PyMuPDF-family). Plain text extraction is the cheap tier and it loses layout |
| **PDF (scanned)** | Yields nothing at all, or a page of noise — and "nothing" looks like success | Detect it first (text length per page ≈ 0), then OCR. Never let a scanned PDF pass as an empty document |
| **Excel / CSV** | A sheet is not prose. Row-per-chunk drops the header, so numbers arrive unlabelled; merged cells, multi-row headers, and numerals stored as text all corrupt silently | Carry the header row into every chunk (the table-aware rule in `memory-vector-db.md`); consider rendering rows through a sentence template instead of embedding raw rows |
| **SQL / Postgres** | Embedding whole tables is almost always the wrong move — you are converting structured data you can already query into fuzzy vectors | Render rows or groups into text via a template, or skip RAG: a query language answers this better (`design-agent-architecture/references/graph-rag.md` on NL→query) |
| **Audio** | ASR errors become permanent corpus errors; no speaker attribution; no structure at all | Speech-to-text (Whisper-family), with timestamps and speaker labels kept as metadata, and a pointer back to the audio so a human can check a disputed passage |
| **Images / diagrams** | OCR reads text but not meaning; charts, flow diagrams and screenshots carry information no OCR returns | OCR (Tesseract-family) for text-bearing scans; a multimodal model for description when the *content* matters |
| **Video** | Slides and on-screen text carry as much as the narration | STT for the audio track plus sampled frames through a multimodal model; timestamps are the join key |

## Choosing a parsing tier

Three tiers, increasing in cost and capability. Pick per source type, not per project.

| Tier | What it does | Cost | Where it fails |
|---|---|---|---|
| **Text extraction** | Pulls the text layer out | Milliseconds, no model | Layout, tables, anything not in the text layer |
| **Layout-aware parsing** | Reconstructs reading order, tables and structure | Seconds per document, CPU | Handwriting, poor scans, semantically loaded graphics |
| **Multimodal model parsing** | A model *looks* at the page and describes it | An inference call per page or image | It is **generative**: it can describe something that is not there |

That last row deserves emphasis, because it is the trap of the fanciest option. A generated
image description or table summary is a **model artifact, not source text**. Store it with
explicit provenance (`derived: true`, plus the model and prompt version), keep the original
alongside it, and never let a citation point at a generated description as if it were the
document. Otherwise a hallucinated caption becomes a "cited fact" that a human auditor cannot
distinguish from the real thing — the exact failure that grounding was supposed to prevent.

## Index-time enrichment: where recall is actually won

Retrieval quality is decided here more than in the retriever. Three techniques, in the order
they pay off:

### Metadata for filtering

Attach at load time, because you cannot reconstruct it later: source URI, section/heading path,
document date, version, tenant/owner, and a **trust tier**. The trust tier is what stops a
customer-submitted document from outranking a policy document — the retrieval-surface rule in
`rag-pipeline.md`. Filtering on metadata is also the cheapest possible recall improvement:
narrowing the candidate set beats any reranker on a query that names a date, a product, or a
customer.

### Vocabulary normalization

Users search in their own words; documents are written in the organization's. Expand
abbreviations, acronyms and internal codes at ingest — **and keep the original string too**,
because the abbreviation is exactly the rare token that dense embeddings lose and lexical search
finds (`memory-vector-db.md` on why BM25 refuses to die). Normalizing *instead of* keeping is a
net loss.

### Hypothetical questions

Generate the questions each chunk answers, embed those, and point them at the chunk. This is the
**index-time inverse of HyDE**: HyDE writes a hypothetical *answer* at query time
(`rag-pipeline.md`), this writes hypothetical *questions* at ingest time.

- **Buys:** the index now contains text phrased the way users ask, not the way documents are
  written — the vocabulary-mismatch problem attacked from the other side, with no per-query cost.
- **Costs:** one LLM call per chunk at ingest, and a larger index.
- **Fails by:** generated questions drifting from what the chunk actually supports, so retrieval
  confidently returns a chunk that cannot answer the question it matched. Sample and read them,
  and never let a generated question become the *only* embedded representation of a chunk.

## Structured outputs: turning messy input into typed records

Much of loading is extraction into a schema — invoice fields, contract clauses, ticket
attributes. Do it with a schema the code owns, not with prose parsing.

Define the schema as a Pydantic model and pass it as a JSON Schema. **OpenRouter documents this**:
`response_format` with `"type": "json_schema"`, a nested `json_schema` object carrying `name`,
`strict` and `schema`, with `"strict": true` to hold the model to the schema, and streaming
supported. The caveats are the load-bearing part:

- **Support is per model.** OpenRouter documents the feature as available on models that support
  it, and a request to one that does not **fails**. Check the model, do not assume the feature
  travels with the provider — the same discipline that `SKILL.md` states about embeddings, applied
  in the opposite direction (here the capability *is* documented; assuming its absence would be
  the error).
- **Validate the parse anyway.** Re-parse the returned JSON through the Pydantic model in code.
  A schema constraint is a contract with the decoder, not a guarantee your object is well-formed
  after transport.
- **Structured output guarantees *format*, never *truth*.** A response can satisfy every type and
  enum while inventing the invoice number. Validation passing is not evidence the field was read
  off the document — for that you need the extracted value traceable to a span, or a human check
  on a sample.
- Keep schemas shallow and required-heavy. Deeply nested optionals give the model room to return
  a technically valid, semantically empty object.
- **Model a keyed or numbered collection as a list of typed records, not an open-ended map.** A
  strict schema enumerates its properties explicitly and forbids extras (OpenRouter's own schema
  example sets `additionalProperties: false`), and a dict keyed on arbitrary values cannot be
  expressed that way — so a field typed as `dict[int, str]` is exactly the shape strict mode
  cannot pin down. Use a list of small typed objects (e.g. a Pydantic model or `TypedDict` with
  `id`/`description` fields) and forbid extra keys on it. Practitioner technique, verified against
  OpenRouter's structured-output schema example; confirm the exact strict-mode constraints in the
  reference for the model you actually call.

## What to change for production

- **Idempotent re-ingest.** Key documents by a content hash, not by filename or upload time.
  Re-running the pipeline must update, not duplicate — duplicate chunks quietly distort ranking
  and inflate every recall number.
- **Record the extractor and its version in metadata.** When a parser improves, you need to know
  which documents were loaded with the old one so you can re-extract *those* rather than
  rebuilding everything.
- **Deletion path.** A document withdrawn at the source must leave the index (`rag-pipeline.md`
  on freshness); loading and unloading are the same subsystem.
- **Quarantine, don't drop.** Failed and degenerate extractions go to a queue a human reviews.
  A silently skipped document is indistinguishable from a document whose answer simply is not in
  the corpus.
- **Cost awareness for the multimodal tiers.** An inference call per page turns a large PDF
  archive into a real bill; measure on a sample before running the corpus, and consider the
  cheaper tier for source types where layout does not carry meaning.

The runnable end-to-end example that consumes what this stage produces is
[rag-example.md](rag-example.md); the chunking strategies that follow it are in
`design-agent-architecture/references/memory-vector-db.md`.
