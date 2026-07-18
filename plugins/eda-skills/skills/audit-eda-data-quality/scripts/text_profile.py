"""Raw-text audit for the text modality (audit steps 2-5).

Profile documents BEFORE any tokenizer/embedding decision: lengths, NaN vs
empty (never silently convert NaN to ''), duplicates of normalized text, token
frequency structure (Zipf), and coverage of a pretrained vocabulary (OOV) --
including documents whose every token is OOV, which turn mean-pooled
embeddings into NaN downstream.

Tokenization here is a simple regex so the audit has no nltk dependency; pass
the pipeline's own tokenizer for exact parity with the model.

Core-library only (numpy, pandas).
"""

from __future__ import annotations

import re
from typing import Callable, Iterable, Optional

import numpy as np
import pandas as pd

_TOKEN_RE = re.compile(r"[\w'-]+", re.UNICODE)


def simple_tokenize(text: str, lowercase: bool = True) -> list[str]:
    """Regex word tokenizer (letters/digits/underscore/apostrophe/hyphen)."""
    s = str(text)
    if lowercase:
        s = s.lower()
    return _TOKEN_RE.findall(s)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())


def text_summary(texts, tokenizer: Optional[Callable] = None) -> dict:
    """Corpus-level profile of a text column.

    Counts NaN separately from empty/whitespace strings -- replacing NaN with
    '' before the audit destroys the distinction between "no record" and
    "recorded as empty", and the two usually have different mechanisms.
    Duplicate rate is computed on normalized text (case/whitespace-folded):
    near-identical documents inflate any downstream metric and can cross
    splits (leakage).
    """
    tok = tokenizer or simple_tokenize
    s = pd.Series(texts)
    n = len(s)
    is_nan = s.isna()
    str_part = s[~is_nan].astype(str)
    is_empty = str_part.str.strip() == ""
    valid = str_part[~is_empty]

    norm = valid.map(_normalize)
    dup_rate = float(1 - norm.nunique() / len(norm)) if len(norm) else 0.0

    token_lists = valid.map(tok)
    n_tokens = token_lists.map(len)
    all_tokens: list[str] = [t for row in token_lists for t in row]
    vc = pd.Series(all_tokens).value_counts() if all_tokens else pd.Series(dtype=int)
    total = int(vc.sum()) if len(vc) else 0
    non_alpha = sum(c for t, c in vc.items() if not any(ch.isalpha() for ch in t))

    return {
        "n_docs": int(n),
        "n_nan": int(is_nan.sum()),
        "n_empty_string": int(is_empty.sum()),
        "n_empty_after_tokenization": int((n_tokens == 0).sum()),
        "duplicate_rate_normalized": round(dup_rate, 4),
        "chars_median": float(valid.str.len().median()) if len(valid) else np.nan,
        "chars_p95": float(valid.str.len().quantile(0.95)) if len(valid) else np.nan,
        "tokens_median": float(n_tokens.median()) if len(n_tokens) else np.nan,
        "tokens_p95": float(n_tokens.quantile(0.95)) if len(n_tokens) else np.nan,
        "vocab_size": int(len(vc)),
        "hapax_share": round(float((vc == 1).mean()), 4) if len(vc) else np.nan,
        "top10_token_share": round(float(vc.head(10).sum() / total), 4) if total else np.nan,
        "non_alpha_token_share": round(float(non_alpha / total), 4) if total else np.nan,
    }


def token_frequencies(texts, tokenizer: Optional[Callable] = None,
                      top: int = 1000) -> pd.DataFrame:
    """Token frequency table (token, count, rank) for Zipf/log-log inspection.

    A frequency spectrum far from the usual power law (e.g. a plateau of
    identical counts) hints at templated/duplicated text or boilerplate.
    """
    tok = tokenizer or simple_tokenize
    s = pd.Series(texts).dropna().astype(str)
    vc = pd.Series([t for row in s.map(tok) for t in row]).value_counts()
    out = vc.head(top).rename_axis("token").reset_index(name="count")
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def vocabulary_coverage(texts, vocab, tokenizer: Optional[Callable] = None,
                        lowercase: bool = True) -> dict:
    """Coverage of a pretrained vocabulary (embedding model, tokenizer vocab).

    ``vocab`` is any container supporting ``in`` (set, dict, gensim
    ``key_to_index``). Reports the OOV rate by token occurrence and by unique
    token, **documents whose every token is OOV** (mean-pooled embeddings
    become NaN there -- decide a policy explicitly instead of
    ``np.nan_to_num``-style silent constants), and case mismatches: tokens
    that are OOV as-is but in-vocab after lowercasing (or the reverse) mean
    the tokenizer's casing and the vocabulary's casing disagree.
    """
    tok = tokenizer or (lambda t: simple_tokenize(t, lowercase=lowercase))
    s = pd.Series(texts)
    doc_rows = []
    occ_total = occ_oov = 0
    types: set[str] = set()
    types_oov: set[str] = set()
    case_mismatch: set[str] = set()
    for idx, text in s.items():
        if pd.isna(text):
            doc_rows.append({"index": idx, "n_tokens": 0, "n_known": 0, "all_oov": True})
            continue
        tokens = tok(str(text))
        known = 0
        for t in tokens:
            occ_total += 1
            types.add(t)
            if t in vocab:
                known += 1
            else:
                occ_oov += 1
                types_oov.add(t)
                alt = t.lower() if t != t.lower() else None
                if (alt is not None and alt in vocab) or (alt is None and t.upper() in vocab):
                    case_mismatch.add(t)
        doc_rows.append({"index": idx, "n_tokens": len(tokens), "n_known": known,
                         "all_oov": known == 0})
    docs = pd.DataFrame(doc_rows)
    return {
        "token_oov_rate": round(float(occ_oov / occ_total), 4) if occ_total else np.nan,
        "type_oov_rate": round(float(len(types_oov) / len(types)), 4) if types else np.nan,
        "n_all_oov_docs": int(docs["all_oov"].sum()),
        "all_oov_indices": docs.loc[docs["all_oov"], "index"].tolist(),
        "n_case_mismatch_types": int(len(case_mismatch)),
        "case_mismatch_examples": sorted(case_mismatch)[:10],
        "per_doc": docs,
    }


def vocab_overlap(train_texts, other_texts, tokenizer: Optional[Callable] = None) -> dict:
    """Vocabulary overlap between train and another split.

    ``unseen_token_rate`` is the share of the other split's token occurrences
    never seen in train -- the text analog of unseen categorical levels. High
    values mean train-fitted vocabularies (tf-idf, learned embeddings) will
    drop or zero much of val/test.
    """
    tok = tokenizer or simple_tokenize
    a = pd.Series(train_texts).dropna().astype(str).map(tok)
    b = pd.Series(other_texts).dropna().astype(str).map(tok)
    va = set(t for row in a for t in row)
    b_tokens = [t for row in b for t in row]
    vb = set(b_tokens)
    unseen = sum(1 for t in b_tokens if t not in va)
    return {
        "train_vocab": int(len(va)),
        "other_vocab": int(len(vb)),
        "jaccard": round(float(len(va & vb) / len(va | vb)), 4) if va | vb else np.nan,
        "unseen_type_rate": round(float(len(vb - va) / len(vb)), 4) if vb else np.nan,
        "unseen_token_rate": round(float(unseen / len(b_tokens)), 4) if b_tokens else np.nan,
    }


__all__ = ["simple_tokenize", "text_summary", "token_frequencies",
           "vocabulary_coverage", "vocab_overlap"]
