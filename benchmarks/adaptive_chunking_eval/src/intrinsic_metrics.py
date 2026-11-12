"""Intrinsic chunking-quality metrics inspired by Adaptive Chunking (arXiv:2603.25333).

Implements offline, dependency-light analogues of:
  - Size Compliance (SC)
  - Intrachunk Cohesion (ICC)
  - Document Contextual Coherence (DCC)
  - Block Integrity (BI)
  - References Completeness (RC)  [filtered missing-reference heuristic]

ICC/DCC use deterministic hashed character n-gram embeddings so evaluation
runs without GPU or external embedding APIs. Swap in a SentenceTransformer /
Jina embedder via the optional ``embed_fn`` hook for paper-grade semantic scores.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)

PERSONAL_PRONOUNS = {
    "i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself",
    "she", "her", "hers", "herself", "it", "its", "itself", "they", "them",
    "their", "theirs", "themselves", "one", "oneself",
}

EmbedFn = Callable[[Sequence[str]], list[list[float]]]


def _tokenize_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_']+", text.lower())


def _hash_embed(texts: Sequence[str], dim: int = 256) -> list[list[float]]:
    """Deterministic bag-of-character-trigram hashing (L2-normalized)."""
    out: list[list[float]] = []
    for text in texts:
        vec = [0.0] * dim
        padded = f"  {text.lower()}  "
        for i in range(max(0, len(padded) - 2)):
            tri = padded[i : i + 3]
            h = hash(tri) % dim
            vec[h] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def _sentence_splits(text: str) -> list[int]:
    """Character offsets of sentence-ish boundaries inside text."""
    points = [0]
    for m in re.finditer(r"[.!?]+\s+", text):
        points.append(m.end())
    if points[-1] != len(text):
        points.append(len(text))
    return sorted(set(points))


def _locate_chunks(chunks: list[str], full_text: str) -> list[tuple[int, int]]:
    """Greedy sequential locate (handles mild overlap)."""
    bounds: list[tuple[int, int]] = []
    cursor = 0
    for chunk in chunks:
        idx = full_text.find(chunk, cursor)
        if idx < 0:
            idx = full_text.find(chunk)
        if idx < 0:
            # fallback: approximate by cursor advance
            idx = min(cursor, max(0, len(full_text) - 1))
            end = min(len(full_text), idx + len(chunk))
        else:
            end = idx + len(chunk)
        bounds.append((idx, end))
        cursor = max(cursor, idx + 1)
    return bounds


def compute_size_compliance(
    chunks: list[str],
    *,
    min_tokens: int = 100,
    max_tokens: int = 1100,
) -> Optional[float]:
    if not chunks:
        return None
    bad = 0
    for c in chunks:
        n = estimate_tokens(c)
        if n < min_tokens or n > max_tokens:
            bad += 1
    return 1.0 - bad / len(chunks)


def compute_intrachunk_cohesion(
    chunks: list[str],
    full_text: str,
    *,
    embed_fn: Optional[EmbedFn] = None,
    max_chunks: int = 24,
    max_sents_per_chunk: int = 4,
) -> Optional[float]:
    if not chunks:
        return None
    embed = embed_fn or _hash_embed
    # Sample chunks for expensive neural embedders while keeping coverage.
    if len(chunks) > max_chunks:
        step = max(1, len(chunks) // max_chunks)
        selected_idx = list(range(0, len(chunks), step))[:max_chunks]
    else:
        selected_idx = list(range(len(chunks)))
    selected_chunks = [chunks[i] for i in selected_idx]
    bounds = _locate_chunks(chunks, full_text)
    # Collect sentence bags first, then one batched embed for chunks+sentences.
    sent_bags: list[list[str]] = []
    for local_i, chunk in enumerate(selected_chunks):
        start, end = bounds[selected_idx[local_i]]
        local = full_text[start:end] if start < end else chunk
        splits = _sentence_splits(local)
        sents = [local[splits[i] : splits[i + 1]].strip() for i in range(len(splits) - 1)]
        sents = [s for s in sents if s]
        if len(sents) > max_sents_per_chunk:
            step = max(1, len(sents) // max_sents_per_chunk)
            sents = sents[::step][:max_sents_per_chunk]
        sent_bags.append(sents)
    flat_sents = [s for bag in sent_bags for s in bag]
    all_embs = embed(selected_chunks + flat_sents)
    chunk_embs = all_embs[: len(selected_chunks)]
    sent_embs_flat = all_embs[len(selected_chunks) :]
    scores: list[float] = []
    cursor = 0
    for emb, bag in zip(chunk_embs, sent_bags):
        n = len(bag)
        if n < 2:
            cursor += n
            continue
        sent_embs = sent_embs_flat[cursor : cursor + n]
        cursor += n
        sims = [_cosine(se, emb) for se in sent_embs]
        scores.append(sum(sims) / len(sims))
    if not scores:
        return None
    return max(0.0, min(1.0, sum(scores) / len(scores)))


def compute_contextual_coherence(
    chunks: list[str],
    full_text: str,
    *,
    embed_fn: Optional[EmbedFn] = None,
    window_chunks: int = 3,
    max_chunks: int = 32,
) -> Optional[float]:
    if not chunks:
        return None
    if len(chunks) < 2:
        return 1.0
    embed = embed_fn or _hash_embed
    if len(chunks) > max_chunks:
        step = max(1, len(chunks) // max_chunks)
        idxs = list(range(0, len(chunks), step))[:max_chunks]
        sampled = [chunks[i] for i in idxs]
    else:
        idxs = list(range(len(chunks)))
        sampled = chunks
    windows: list[str] = []
    for global_i in idxs:
        left = max(0, global_i - window_chunks // 2)
        right = min(len(chunks), left + window_chunks)
        left = max(0, right - window_chunks)
        windows.append("\n".join(chunks[left:right]))
    all_embs = embed(sampled + windows)
    chunk_embs = all_embs[: len(sampled)]
    win_embs = all_embs[len(sampled) :]
    scores = [_cosine(chunk_embs[i], win_embs[i]) for i in range(len(sampled))]
    return max(0.0, min(1.0, sum(scores) / len(scores)))


def compute_block_integrity(
    chunks: list[str],
    full_text: str,
    *,
    gold_split_points: Optional[list[int]] = None,
    tolerance_chars: int = 5,
) -> Optional[float]:
    if not chunks:
        return None
    if len(chunks) == 1:
        return 1.0
    if gold_split_points is None:
        # paragraph / blank-line blocks as structural gold
        gold_split_points = [m.end() for m in re.finditer(r"\n\s*\n", full_text)]
    bounds = _locate_chunks(chunks, full_text)
    predicted = sorted({b[0] for b in bounds[1:]})
    block_bounds = [0] + sorted(gold_split_points) + [len(full_text)]
    intact = 0
    for left, right in zip(block_bounds, block_bounds[1:]):
        broken = any(
            left < p < right and (p - left) > tolerance_chars and (right - p) > tolerance_chars
            for p in predicted
        )
        if not broken:
            intact += 1
    total = len(block_bounds) - 1
    return intact / total if total else None


def compute_references_completeness(
    chunks: list[str],
    full_text: str,
) -> Optional[float]:
    """Heuristic RC: fraction of pronoun mentions whose nearest preceding proper/noun
    antecedent remains inside the same chunk (filtered missing-reference analogue).
    """
    if not chunks:
        return None
    bounds = _locate_chunks(chunks, full_text)
    # Build token stream with char spans
    tokens = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[A-Za-z0-9_']+", full_text)]
    if not tokens:
        return 1.0

    def chunk_index(pos: int) -> int:
        for i, (s, e) in enumerate(bounds):
            if s <= pos < e:
                return i
        # nearest
        best, bestd = 0, 10**9
        for i, (s, e) in enumerate(bounds):
            d = min(abs(pos - s), abs(pos - e))
            if d < bestd:
                bestd, best = d, i
        return best

    intact = 0
    total = 0
    for i, (tok, start, _end) in enumerate(tokens):
        low = tok.lower()
        if low not in PERSONAL_PRONOUNS:
            continue
        # look back for a capitalized / noun-like antecedent
        antecedent_pos = None
        for j in range(i - 1, max(-1, i - 40), -1):
            prev, ps, _pe = tokens[j]
            if prev.lower() in PERSONAL_PRONOUNS:
                continue
            if prev[:1].isupper() or len(prev) > 3:
                antecedent_pos = ps
                break
        if antecedent_pos is None:
            continue
        total += 1
        if chunk_index(start) == chunk_index(antecedent_pos):
            intact += 1
    if total == 0:
        return 1.0
    return intact / total


@dataclass
class IntrinsicScore:
    sc: Optional[float]
    icc: Optional[float]
    dcc: Optional[float]
    bi: Optional[float]
    rc: Optional[float]

    @property
    def mean(self) -> Optional[float]:
        vals = [v for v in (self.sc, self.icc, self.dcc, self.bi, self.rc) if v is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)

    def as_percent_dict(self) -> dict[str, Optional[float]]:
        def pct(v: Optional[float]) -> Optional[float]:
            return None if v is None else round(100.0 * v, 2)

        return {
            "SC": pct(self.sc),
            "ICC": pct(self.icc),
            "DCC": pct(self.dcc),
            "BI": pct(self.bi),
            "RC": pct(self.rc),
            "Mean": pct(self.mean),
        }


def score_chunks(
    chunks: list[str],
    full_text: str,
    *,
    min_tokens: int = 100,
    max_tokens: int = 1100,
    gold_split_points: Optional[list[int]] = None,
    embed_fn: Optional[EmbedFn] = None,
) -> IntrinsicScore:
    return IntrinsicScore(
        sc=compute_size_compliance(chunks, min_tokens=min_tokens, max_tokens=max_tokens),
        icc=compute_intrachunk_cohesion(chunks, full_text, embed_fn=embed_fn),
        dcc=compute_contextual_coherence(chunks, full_text, embed_fn=embed_fn),
        bi=compute_block_integrity(chunks, full_text, gold_split_points=gold_split_points),
        rc=compute_references_completeness(chunks, full_text),
    )
