# Text / NLP EDA

Text follows the same leakage-safe discipline as the other modalities; it adds
tokenization, vocabulary, and pretrained-embedding specifics. The deliverable
is a **validated text dataset + manifests**, not a trained model. Pretrained
embeddings/encoders are allowed as diagnostic probes and as documented feature
extractors.

## 1. Raw-text profiling (audit)

`text_profile.text_summary` + `token_frequencies`:

- **NaN vs empty string are different defects.** `replace(nan, '')` before the
  audit destroys the distinction between "no record" and "recorded as empty";
  count both separately and decide the policy explicitly.
- Length distributions (chars/tokens, median and p95) — they drive truncation
  and padding choices for NN pipelines; a heavy tail means silent truncation
  for the longest documents.
- **Duplicates of normalized text** (case/whitespace-folded): boilerplate and
  re-posts inflate metrics and cross splits (leakage) — route to the
  duplicate/split checks.
- Token frequency spectrum (Zipf log-log), vocabulary size, hapax share,
  non-alphabetic token share; a plateau of identical counts hints at templated
  text.
- Language/script mix and encoding artifacts (mojibake) on a sample.

## 2. Vocabulary coverage vs a pretrained model (audit)

`text_profile.vocabulary_coverage` against the embedding/tokenizer vocab:

- **OOV rate** by token occurrence and by unique token, per split and per
  class — a class with systematically higher OOV gets systematically poorer
  vectors (a shortcut/bias risk).
- **All-OOV documents:** mean-pooled embeddings become NaN for them. Never
  patch with a silent constant (`np.nan_to_num(nan=0.1)` style); choose and
  record a policy — zero vector + `all_oov` flag feature, drop with
  provenance, or a different representation.
- **Case mismatch:** if tokens are OOV as-is but in-vocab after lowercasing
  (or the reverse), the tokenizer's casing disagrees with the vocabulary's
  (the classic `TfidfVectorizer(lowercase=True)` vs cased gensim vocab
  warning). Normalization must match end to end.
- `vocab_overlap` between train and val/test: high unseen-token rate is the
  text analog of unseen categorical levels — train-fitted tf-idf/embeddings
  will zero or drop that much of the evaluation data.

## 3. Text features (engineer)

- Pooled embeddings via `feature_builders.PooledTextEmbedding`: mean pooling
  as the baseline, **tf-idf-weighted pooling** as the cheap upgrade (idf is a
  *learned* statistic — fit on train only). Weighted pooling typically beats
  plain mean by a small but real margin.
- Sparse TF-IDF (+ TruncatedSVD) remains a strong tabular-probe path; fit the
  vectorizer on train only, and keep the tokenizer identical between the
  vectorizer and any embedding lookup (see case mismatch above).
- Length/quality metadata features (chars, tokens, OOV share, all-OOV flag)
  are legitimate features with availability at inference — record them in the
  feature contract.

## 4. Embedding sanity and bias probes (discover)

Before shipping embedding-derived features:

- **Neighbor smell test:** nearest neighbors of a handful of domain words
  should make sense; garbage neighbors mean a corpus/domain mismatch.
- Analogy arithmetic is a demo, not a metric — do not use analogy accuracy as
  a quality gate.
- **Social-bias probe:** pretrained embeddings encode gender/ethnicity
  associations from their training corpus; when embeddings feed features that
  affect people, check bias directions relevant to the domain and record the
  finding in the fairness section of the dataset card.

## 5. Split and leakage specifics

- Near-duplicate questions/documents across splits (`embedding_eda.near_duplicate_pairs`
  on pooled vectors, or normalized-text hashes) — the text analog of image
  near-duplicates.
- **Anti-pattern to avoid:** tuning a similarity/decision threshold on the
  full dataset (train+evaluation pooled). The threshold is model policy: fit
  it on validation/OOF only, exactly like any other learned parameter.
- Author/thread/session are group keys: the same author's posts in train and
  test leak style, not signal.
