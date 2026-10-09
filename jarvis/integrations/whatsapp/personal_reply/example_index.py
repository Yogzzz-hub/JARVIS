"""Private per-contact index of the owner's historical replies (contact RAG).

Vectors are hashed word + character n-grams (the decision engine's ``HashingEncoder``): local,
deterministic, and robust to Tanglish spelling variation ("varuviya" / "varuveengala" share n-grams).
Queries always run inside ONE contact's namespace; there is no cross-contact search path.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from jarvis.decision.encoder import HashingEncoder
from jarvis.integrations.whatsapp.personal_reply.models import Authorship, ExampleSource, ReplyExample
from jarvis.integrations.whatsapp.personal_reply.store import VECTOR_DIM, PersonalReplyStore

_encoder = HashingEncoder(dim=VECTOR_DIM)
_QUESTION = re.compile(r"\?|\b(?:what|when|where|why|how|who|which|can|could|will|are|is|do|did|enna|epdi|eppo|enga|yen|yaaru|"
                       r"\w+(?:ya|la|aa|ah|va))\b\s*[?!.]*$", re.I)
_SOURCE_BONUS = {ExampleSource.USER_EDITED: 0.10, ExampleSource.APPROVED: 0.08, ExampleSource.LIVE_USER: 0.05,
                 ExampleSource.IMPORT: 0.0}
_LEXICAL_STOP = {'a', 'an', 'the', 'i', 'you', 'u', 'me', 'my', 'your', 'it', 'is', 'are', 'to',
                 'in', 'on', 'for', 'at', 'and', 'or', 'da', 'di', 'bro', 'ah', 'aa', 'la'}


def lexical_overlap(query: str, context: str) -> float:
    """Same-contact keyword signal; embeddings still enforce the measured floor."""
    q = set(re.findall(r'\w+', query.casefold())) - _LEXICAL_STOP
    c = set(re.findall(r'\w+', context.casefold())) - _LEXICAL_STOP
    return len(q & c) / max(1, len(q)) if q else 0.0


def embed(texts: list[str]) -> np.ndarray:
    return _encoder.encode(texts)


def is_question(text: str) -> bool:
    return bool(_QUESTION.search((text or "").strip().lower()))


@dataclass
class RetrievedExample:
    example: ReplyExample
    score: float
    similarity: float


class ContactExampleIndex:
    def __init__(self, store: PersonalReplyStore) -> None:
        self.store = store
        self._cache: dict[str, tuple[float, list[ReplyExample], np.ndarray]] = {}

    def invalidate(self, contact_id: Optional[str] = None) -> None:
        if contact_id is None:
            self._cache.clear()
        else:
            self._cache.pop(contact_id, None)

    def _load(self, contact_id: str) -> tuple[list[ReplyExample], np.ndarray]:
        hit = self._cache.get(contact_id)
        if hit and time.time() - hit[0] < 300:
            return hit[1], hit[2]
        exs, vecs = self.store.examples(contact_id, splits=("TRAIN",))
        self._cache[contact_id] = (time.time(), exs, vecs)
        return exs, vecs

    def copied_reply_similarity(self, contact_id: str, reply: str, query: str) -> Optional[float]:
        """If ``reply`` is word-for-word one of the owner's past replies to this contact, how similar was the message
        it originally answered to ``query``? (None when the reply is not a copy.)"""
        norm = " ".join((reply or "").lower().split())
        exs, vecs = self._load(contact_id)
        idx = [i for i, e in enumerate(exs) if " ".join(e.reply.lower().split()) == norm]
        if not norm or not idx:
            return None
        q = embed([query])[0]
        return float(max(vecs[i] @ q for i in idx))

    def retrieve(self, contact_id: str, query: str, k: int = 6, min_k: int = 0, now: Optional[float] = None,
                 exclude_ids: frozenset[int] = frozenset(), min_similarity: float = 0.21) -> list[RetrievedExample]:
        """Return only relevant prior same-contact examples; zero is a valid result.

        The 0.21 conservative floor separates two clearly relevant and five
        clearly unrelated top hits in the small verified development audit.
        ``min_k`` is retained for caller compatibility but never forces weak hits.
        """
        exs, vecs = self._load(contact_id)
        if not exs:
            return []
        now = time.time() if now is None else now
        q = embed([query])[0]
        sims = vecs @ q
        newest, oldest = max(e.timestamp for e in exs), min(e.timestamp for e in exs)
        span = max(1.0, newest - oldest)
        q_is_question = is_question(query)
        scores = np.empty(len(exs), dtype=np.float32)
        for i, e in enumerate(exs):
            if e.timestamp > now:
                scores[i] = -1e9
                continue
            recency = 0.12 * (e.timestamp - oldest) / span
            intent = 0.05 if is_question(e.context) == q_is_question else 0.0
            provenance_bonus = {
                Authorship.USER_TYPED: .30,
                Authorship.VERIFIED_MANUAL_OWNER_SEND: .30,
                Authorship.USER_EDITED_AI_DRAFT: .25,
                Authorship.VERIFIED_LEGACY_OWNER: .18,
                Authorship.USER_APPROVED_AI_DRAFT: .13,
                Authorship.LEGACY_OWNER_LIKELY: 0.0,
            }.get(e.provenance, 0.0)
            lexical = 0.08 * lexical_overlap(query, e.context)
            scores[i] = sims[i] + lexical + recency + _SOURCE_BONUS.get(e.source, 0.0) + intent + provenance_bonus + 0.12 * e.evidence_weight
            if e.example_id in exclude_ids:
                scores[i] = -1e9
        order = [int(i) for i in np.argsort(-scores) if scores[i] > -1e8 and sims[i] >= min_similarity]
        chosen: list[int] = []
        k = max(0, min(8, k))
        while order and len(chosen) < k:
            best, best_val = None, -1e9
            for idx in order[:40]:
                redundancy = max((float(vecs[idx] @ vecs[j]) for j in chosen), default=0.0)
                val = 0.75 * float(scores[idx]) - 0.25 * redundancy
                if val > best_val:
                    best, best_val = idx, val
            order.remove(best)
            chosen.append(best)
        return [RetrievedExample(exs[i], float(scores[i]), float(sims[i])) for i in chosen]
