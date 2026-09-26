"""Precision layer for retrieval: rerank candidates and drop the ones that do not answer the query.

Fusion (RRF) only orders candidates; it never says "none of these are relevant", so the top-k was always
handed to the chat model even for unrelated questions - a direct cause of confident, wrong answers.
This module scores every candidate against the query itself:

* term coverage   - share of the query's content words (light stemming) found in the chunk text/title,
                    weighted by rarity inside the candidate set (a word every chunk has says little);
* phrase bonus    - adjacent query word pairs that also appear adjacent in the chunk;
* dense evidence  - the candidate's own cosine similarity when a vector search produced it;
* fused rank      - the original fused order, as a weak prior.

Candidates below ``min_score`` are dropped (abstention beats a plausible-sounding guess), near-duplicate
chunks are collapsed so the context carries more distinct evidence, and the rest are reordered.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable, List, Sequence

_STOP = frozenset("""a an the and or but if then than so to of in on at by for with from into onto over under about as
is are was were be been being do does did doing have has had having i me my mine we our you your yours he she it its they
them their this that these those there here what which who whom whose when where why how can could should would will
shall may might must not no yes please tell show give find get let know say said says also just only any some all
each every more most much many few other such own same very too again once up down out off new old
long take takes taking need needs want like way thing things kind sort
""".split())
_WORD = re.compile(r"[a-z0-9][a-z0-9'-]*")


def stem(word: str) -> str:
    w = word.lower().strip("'-")
    for suf in ("ingly", "edly", "ation", "ments", "ment", "ness", "ings", "ing", "ies", "ied", "ers", "est", "ed",
                "es", "ly", "er", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf in ("ies", "ied") else "")
    return w


def terms(text: str) -> List[str]:
    return [stem(w) for w in _WORD.findall((text or "").lower()) if w not in _STOP and len(w) > 1]


def _text_of(item: Any) -> str:
    title = getattr(item, "title", "") or ""
    snippet = getattr(item, "snippet", "") or getattr(item, "content", "") or ""
    return f"{title}\n{snippet}"


def score_candidates(query: str, items: Sequence[Any]) -> List[float]:
    q = list(dict.fromkeys(terms(query)))
    if not q or not items:
        return [0.0] * len(items)
    docs = [terms(_text_of(it)) for it in items]
    sets = [set(d) for d in docs]
    n = len(items)
    # rarity of each query term inside this candidate set (smoothed idf); a term absent everywhere still counts
    idf = {t: math.log(1.0 + (n + 1) / (1 + sum(t in s for s in sets))) for t in q}
    total = sum(idf.values()) or 1.0
    pairs = list(zip(q, q[1:]))
    scores = []
    for rank, (it, d, s) in enumerate(zip(items, docs, sets)):
        coverage = sum(idf[t] for t in q if t in s) / total
        if pairs:
            adjacent = set(zip(d, d[1:]))
            phrase = sum(1 for p in pairs if p in adjacent) / len(pairs)
        else:
            phrase = 0.0
        dense = _dense_sim(it)
        prior = 1.0 / (1.0 + rank * 0.35)
        # a query word in the chunk's heading / file name is strong topical evidence ("refund" -> "Refund policy")
        title_terms = set(terms(getattr(it, "title", "") or ""))
        heading = sum(idf[t] for t in q if t in title_terms) / total
        scores.append(0.62 * coverage + 0.18 * phrase + 0.12 * dense + 0.08 * prior + 0.2 * heading)
    return scores


def _dense_sim(item: Any) -> float:
    meta = getattr(item, "citation_metadata", None) or {}
    try:
        return float(meta.get("dense_sim", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _near_duplicate(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= 0.8


def rerank(query: str, items: Iterable[Any], limit: int = 5, min_score: float = 0.27,
           min_coverage_terms: int = 1, relative: float = 0.6) -> List[Any]:
    """Best ``limit`` candidates that really match ``query`` (possibly none)."""
    items = list(items)
    if not items:
        return []
    scores = score_candidates(query, items)
    q = set(terms(query))
    order = sorted(range(len(items)), key=lambda i: scores[i], reverse=True)
    chosen: List[Any] = []
    seen: List[set[str]] = []
    for i in order:
        it = items[i]
        t = set(terms(_text_of(it)))
        hits = len(q & t)
        strong_dense = _dense_sim(it) >= 0.55
        if scores[i] < min_score and not strong_dense:
            continue
        if chosen and scores[i] < relative * scores[order[0]] and not strong_dense:
            continue  # far weaker than the best match: noise, not extra evidence
        if hits < min(min_coverage_terms, len(q)) and not strong_dense:
            continue
        if any(_near_duplicate(t, s) for s in seen):
            continue
        try:
            it.relevance = round(max(0.05, min(1.0, scores[i])), 3)
        except Exception:
            pass
        chosen.append(it)
        seen.append(t)
        if len(chosen) >= limit:
            break
    return chosen
