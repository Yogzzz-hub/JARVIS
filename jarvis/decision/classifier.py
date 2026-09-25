"""Lightweight multi-head linear classifiers on one shared input vector (numpy only).

One forward pass = one matrix product per head. Heads are multinomial / binary logistic regression
trained with Adam, L2 regularisation and class-balanced weights. Tiny, CPU-fast, and easy to
calibrate; bigger models are only worth it if the benchmark says so.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


@dataclass
class LinearHead:
    """Softmax head (n_classes >= 2). Binary heads use 2 classes so everything shares one code path."""
    name: str
    classes: tuple[str, ...]
    W: Optional[np.ndarray] = None
    b: Optional[np.ndarray] = None
    history: list[float] = field(default_factory=list)

    def logits(self, X: np.ndarray) -> np.ndarray:
        return X @ self.W + self.b

    def fit(self, X: np.ndarray, y: np.ndarray, l2: float = 1e-4, epochs: int = 250, lr: float = 0.05,
            balance: bool = True, seed: int = 7, sample_weight: Optional[np.ndarray] = None) -> "LinearHead":
        n, d = X.shape
        k = len(self.classes)
        rng = np.random.default_rng(seed)
        self.W = (rng.standard_normal((d, k)) * 0.01).astype(np.float32)
        self.b = np.zeros(k, dtype=np.float32)
        Y = np.zeros((n, k), dtype=np.float32)
        Y[np.arange(n), y] = 1.0
        w = np.ones(n, dtype=np.float32) if sample_weight is None else sample_weight.astype(np.float32)
        if balance:
            counts = np.bincount(y, minlength=k).astype(np.float32)
            counts[counts == 0] = 1.0
            w = w * (n / (k * counts))[y]
            w = np.minimum(w, 10.0)
        w = w / w.mean()
        mW, vW = np.zeros_like(self.W), np.zeros_like(self.W)
        mb, vb = np.zeros_like(self.b), np.zeros_like(self.b)
        b1, b2, eps = 0.9, 0.999, 1e-8
        for t in range(1, epochs + 1):
            P = softmax(self.logits(X))
            G = (P - Y) * w[:, None] / n
            gW = X.T @ G + l2 * self.W
            gb = G.sum(axis=0)
            mW = b1 * mW + (1 - b1) * gW
            vW = b2 * vW + (1 - b2) * gW * gW
            mb = b1 * mb + (1 - b1) * gb
            vb = b2 * vb + (1 - b2) * gb * gb
            step = lr * np.sqrt(1 - b2 ** t) / (1 - b1 ** t)
            self.W -= (step * mW / (np.sqrt(vW) + eps)).astype(np.float32)
            self.b -= (step * mb / (np.sqrt(vb) + eps)).astype(np.float32)
            if t % 50 == 0 or t == epochs:
                self.history.append(float(-(np.log(P[np.arange(n), y] + 1e-9) * w).mean()))
        return self

    def predict_proba(self, X: np.ndarray, temperature: float = 1.0) -> np.ndarray:
        return softmax(self.logits(X) / max(temperature, 1e-3))


@dataclass
class MultiLabelHead:
    """Independent sigmoid per label (e.g. all route families a request needs)."""
    name: str
    classes: tuple[str, ...]
    W: Optional[np.ndarray] = None
    b: Optional[np.ndarray] = None

    def logits(self, X: np.ndarray) -> np.ndarray:
        return X @ self.W + self.b

    def fit(self, X: np.ndarray, Y: np.ndarray, l2: float = 1e-4, epochs: int = 250, lr: float = 0.05, seed: int = 11) -> "MultiLabelHead":
        n, d = X.shape
        k = Y.shape[1]
        rng = np.random.default_rng(seed)
        self.W = (rng.standard_normal((d, k)) * 0.01).astype(np.float32)
        self.b = np.zeros(k, dtype=np.float32)
        pos = Y.mean(axis=0).clip(1e-3, 1 - 1e-3)
        wpos, wneg = (0.5 / pos).astype(np.float32), (0.5 / (1 - pos)).astype(np.float32)
        mW, vW, mb, vb = np.zeros_like(self.W), np.zeros_like(self.W), np.zeros_like(self.b), np.zeros_like(self.b)
        for t in range(1, epochs + 1):
            P = sigmoid(self.logits(X))
            G = (P - Y) * (Y * wpos + (1 - Y) * wneg) / n
            gW = X.T @ G + l2 * self.W
            gb = G.sum(axis=0)
            mW = 0.9 * mW + 0.1 * gW
            vW = 0.999 * vW + 0.001 * gW * gW
            mb = 0.9 * mb + 0.1 * gb
            vb = 0.999 * vb + 0.001 * gb * gb
            step = lr * np.sqrt(1 - 0.999 ** t) / (1 - 0.9 ** t)
            self.W -= (step * mW / (np.sqrt(vW) + 1e-8)).astype(np.float32)
            self.b -= (step * mb / (np.sqrt(vb) + 1e-8)).astype(np.float32)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return sigmoid(self.logits(X))


class MultiHead:
    """Shared input -> {head name: LinearHead}."""

    def __init__(self, heads: dict[str, "LinearHead | MultiLabelHead"]):
        self.heads = heads

    def logits(self, X: np.ndarray) -> dict[str, np.ndarray]:
        return {name: head.logits(X) for name, head in self.heads.items()}

    def to_arrays(self) -> dict[str, np.ndarray]:
        out = {}
        for name, head in self.heads.items():
            out[f"{name}__W"] = head.W
            out[f"{name}__b"] = head.b
        return out

    @classmethod
    def from_arrays(cls, arrays: dict[str, np.ndarray], classes: dict[str, tuple[str, ...]],
                    multilabel: tuple[str, ...] = ()) -> "MultiHead":
        heads: dict = {}
        for name, cls_names in classes.items():
            kind = MultiLabelHead if name in multilabel else LinearHead
            heads[name] = kind(name, tuple(cls_names), W=arrays[f"{name}__W"], b=arrays[f"{name}__b"])
        return cls(heads)
