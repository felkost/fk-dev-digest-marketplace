# Generative model landscape

What each kind of model is, what it is for, and where its boundary lies. The point is routing:
match the *kind* to the sub-task before arguing about specific checkpoints.

## Decoder-only LLMs (GPT/Claude/Llama/Qwen class)

Autoregressive next-token prediction over text (and code). The default engine for open-ended
generation, instruction following, reasoning chains, tool calling, structured extraction.
Boundaries: no grounding by themselves (hallucination), context window limits, cost scales with
tokens, weak at exact arithmetic/retrieval without tools.

## Vision-language models (VLM)

An image encoder projected into an LLM's token space; the LLM reasons over both. For: describing
and comparing images, document/chart/screenshot understanding, visual QA, UI grounding.
Boundaries: fine-grained counting/measurement, small text in images, spatial precision —
verify on your own samples; classical CV beats VLMs on fixed-label high-volume perception.

## Encoders (embedding models, BERT class)

Text (or image) → fixed vector. No generation. For: semantic search, retrieval (the R in RAG),
clustering, dedup, classification with a small head, similarity/rerank. Cheap and fast at scale.
Boundaries: vectors are task-shaped (a model tuned for retrieval ranks poorly for clustering
without checking); cross-lingual quality varies — test on Ukrainian data explicitly if that is
the corpus language.

## Encoder-decoder (T5/BART class, and most translation/ASR models)

Sequence-to-sequence with an explicit input encoder. Still competitive for translation,
summarization-style transforms, and speech (Whisper class is encoder-decoder). In practice most
new systems use decoder-only LLMs here too; prefer encoder-decoder when a strong task-specific
checkpoint already exists.

## Diffusion / image-audio generators

Iterative denoising conditioned on text/image. For image/audio/video synthesis and editing.
Different serving profile from LLMs (GPU-heavy bursts, seconds-long jobs) — plan queueing, not
streaming.

## Combinations that recur in practice

| Pattern | Components | Use when |
|---|---|---|
| RAG | Encoder + vector DB + LLM | Knowledge is external, changing, or must be cited |
| Router + specialists | Cheap classifier/LLM → per-task models | Traffic is heterogeneous; most requests are easy |
| Draft + verify | Small LLM drafts, large LLM (or rules) verifies | Cost control with a quality floor |
| Perceive + reason | CV detector or VLM → LLM | Pixels in, decisions out |
| Generate + rerank | LLM candidates → encoder/reward rerank | Quality via selection, not bigger models |

Name which component owns which failure mode; a hybrid without ownership boundaries is
undebuggable.
