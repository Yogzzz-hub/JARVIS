"""Probability calibration and calibration metrics.

* temperature scaling (multiclass): one scalar T fitted on validation NLL,
* Platt scaling (binary): p = sigmoid(a * logit + b) fitted on validation,
* ECE (15 equal-width bins), Brier score, reliability table (for docs / reports).
"""
from __future__ import annotations

import numpy as np

from jarvis.decision.classifier import sigmoid, softmax


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    best_t, best = 1.0, float("inf")
    for t in np.concatenate([np.linspace(0.3, 3.0, 55), np.linspace(3.2, 8.0, 13)]):
        p = softmax(logits / t)
        nll = -np.log(p[np.arange(len(y)), y] + 1e-12).mean()
        if nll < best:
            best, best_t = nll, float(t)
    return best_t


def fit_platt(logit: np.ndarray, y: np.ndarray, iters: int = 400, lr: float = 0.1) -> tuple[float, float]:
    """1-D logistic regression on the head's logit margin (Newton-free, small and stable)."""
    a, b = 1.0, 0.0
    y = y.astype(np.float64)
    # Platt's target smoothing avoids over-confidence on tiny validation sets
    n_pos, n_neg = y.sum(), len(y) - y.sum()
    t = np.where(y > 0, (n_pos + 1) / (n_pos + 2), 1 / (n_neg + 2))
    for _ in range(iters):
        p = sigmoid(a * logit + b)
        g = p - t
        a -= lr * float((g * logit).mean())
        b -= lr * float(g.mean())
    return float(a), float(b)


def ece(conf: np.ndarray, correct: np.ndarray, bins: int = 15) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total, err = len(conf), 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if m.any():
            err += m.sum() / total * abs(conf[m].mean() - correct[m].mean())
    return float(err)


def brier_multiclass(probs: np.ndarray, y: np.ndarray) -> float:
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(y)), y] = 1
    return float(((probs - onehot) ** 2).sum(axis=1).mean())


def brier_binary(p: np.ndarray, y: np.ndarray) -> float:
    return float(((p - y) ** 2).mean())


def reliability_table(conf: np.ndarray, correct: np.ndarray, bins: int = 10) -> list[tuple[str, int, float, float]]:
    rows = []
    edges = np.linspace(0, 1, bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if m.any():
            rows.append((f"{lo:.1f}-{hi:.1f}", int(m.sum()), float(conf[m].mean()), float(correct[m].mean())))
    return rows
