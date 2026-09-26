"""Risk-class confidence gates, fitted on validation data (never hardcoded blindly).

A route may execute only when the calibrated confidence reaches the gate of its risk class; the
target is the precision required among auto-executed predictions of that class.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

RISK_CLASSES = ("READ_ONLY", "REVERSIBLE", "EXTERNAL_EFFECT", "DESTRUCTIVE", "PRIVILEGED")
TARGET_PRECISION = {"READ_ONLY": 0.95, "REVERSIBLE": 0.97, "EXTERNAL_EFFECT": 0.99, "DESTRUCTIVE": 0.995, "PRIVILEGED": 0.995}
# Used only when validation data for a class is too small to fit anything (documented, conservative).
FALLBACK_THRESHOLDS = {"READ_ONLY": 0.70, "REVERSIBLE": 0.80, "EXTERNAL_EFFECT": 0.92, "DESTRUCTIVE": 0.97, "PRIVILEGED": 0.98}
MIN_THRESHOLD = {"READ_ONLY": 0.55, "REVERSIBLE": 0.65, "EXTERNAL_EFFECT": 0.85, "DESTRUCTIVE": 0.93, "PRIVILEGED": 0.95}


def wilson_lower(successes: int, n: int, z: float = 1.645) -> float:
    """One-sided 95% Wilson score lower bound of a proportion."""
    if n <= 0:
        return 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return float((centre - margin) / denom)


@dataclass
class Thresholds:
    execute: dict[str, float] = field(default_factory=lambda: dict(FALLBACK_THRESHOLDS))
    fallback_min: float = 0.40          # below this the engine abstains instead of handing to the old router
    ambiguity: float = 0.5
    disagreement_margin: float = 0.15
    version: str = "thr-default"
    fitted_from: dict[str, int] = field(default_factory=dict)

    @classmethod
    def fit(cls, conf: np.ndarray, correct: np.ndarray, risk: list[str], version: str) -> "Thresholds":
        th = cls(version=version)
        for rc in RISK_CLASSES:
            m = np.asarray([r == rc for r in risk])
            n = int(m.sum())
            th.fitted_from[rc] = n
            if n < 25:
                continue
            c, ok = conf[m], correct[m]
            chosen = None
            for t in np.linspace(MIN_THRESHOLD[rc], 0.995, 90):
                sel = c >= t
                k = int(sel.sum())
                # Precision must hold with 95% confidence (Wilson lower bound), not just on this sample:
                # small validation sets otherwise yield optimistic, too-low gates for risky classes.
                if k >= max(5, int(0.1 * n)) and wilson_lower(int(ok[sel].sum()), k) >= TARGET_PRECISION[rc]:
                    chosen = float(t)
                    break
            th.execute[rc] = chosen if chosen is not None else max(FALLBACK_THRESHOLDS[rc], 0.99)
        return th
