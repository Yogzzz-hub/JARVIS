"""Embedding-similarity router over registry-derived family prototypes.

The user text is embedded once (shared with the classifier heads); similarity to every prototype of
a family is combined as max + mean (nearest example and family centroid), then turned into a
distribution with a validated scale. Wrapped behind this class so a library such as Aurelio
Semantic Router (with a local encoder) can replace it without touching the engine.
"""
from __future__ import annotations

import numpy as np

from jarvis.decision.classifier import softmax


class SemanticRouter:
    def __init__(self, families: list[str], proto_vectors: np.ndarray, proto_labels: np.ndarray, scale: float = 12.0):
        self.families = families
        self.P = proto_vectors.astype(np.float32)
        self.labels = proto_labels.astype(np.int32)
        self.scale = scale
        self._masks = [(self.labels == i) for i in range(len(families))]

    @classmethod
    def from_texts(cls, encoder, prototypes: dict[str, list[str]], families: list[str], scale: float = 12.0) -> "SemanticRouter":
        texts, labels = [], []
        for i, fam in enumerate(families):
            for t in prototypes.get(fam, []):
                texts.append(t)
                labels.append(i)
        vecs = encoder.encode(texts) if texts else np.zeros((0, getattr(encoder, "dim", 1)), dtype=np.float32)
        return cls(families, vecs, np.asarray(labels), scale)

    def similarities(self, E: np.ndarray) -> np.ndarray:
        """(n, n_families) family similarity: 0.6 * max + 0.4 * mean over the family's prototypes."""
        S = E @ self.P.T
        out = np.full((E.shape[0], len(self.families)), -1.0, dtype=np.float32)
        for i, m in enumerate(self._masks):
            if m.any():
                sub = S[:, m]
                out[:, i] = 0.6 * sub.max(axis=1) + 0.4 * sub.mean(axis=1)
        return out

    def probabilities(self, E: np.ndarray) -> np.ndarray:
        return softmax(self.similarities(E) * self.scale)
