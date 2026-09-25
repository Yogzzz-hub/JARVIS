"""JARVIS Decision Engine (JDE): local, calibrated, abstention-aware System-One decisions.

One request -> one text encoding -> every decision head in a single pass -> calibrated, fused typed
answers + a gate. JDE never executes anything and never authorizes anything: callers map the
decision to a structured route/capability and the existing PolicyEvaluator, ConfirmationManager,
ledger and verifier stay the final authority.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

import numpy as np

from jarvis.decision.cache import DecisionCache
from jarvis.decision.calibration import sigmoid
from jarvis.decision.classifier import MultiHead, softmax
from jarvis.decision.encoder import DecisionEncoder, make_encoder, normalize_text
from jarvis.decision.features import FEATURE_NAMES, rule_features
from jarvis.decision.schemas import (
    BINARY_HEADS, COMPLEXITY_LEVELS, ROUTE_FAMILIES, ChoiceAnswer, DecisionRequest, DecisionResult, DecisionState,
    Gate, ProbabilityAnswer, ScoreAnswer,
)
from jarvis.decision.semantic_router import SemanticRouter
from jarvis.decision.thresholds import Thresholds

logger = logging.getLogger("jarvis.decision")

MODEL_ROOT = Path(__file__).resolve().parents[2] / "models" / "jde"
HIGH_RISK = ("EXTERNAL_EFFECT", "DESTRUCTIVE", "PRIVILEGED")


class DecisionEngine(Protocol):
    """Anything that answers typed routing questions (LocalJDE today; a hosted adapter could be benchmarked later)."""

    def decide(self, request: DecisionRequest) -> DecisionResult: ...


@dataclass
class ModelMeta:
    decision_model_version: str
    encoder: str
    encoder_version: str
    route_catalog_version: str
    threshold_version: str
    feature_names: list[str]
    classes: dict[str, list[str]]
    multilabel: list[str]
    route_temperature: float = 1.0
    platt: dict[str, list[float]] = field(default_factory=dict)
    complexity_temperature: float = 1.0
    fusion_semantic_weight: float = 0.5
    semantic_scale: float = 12.0
    thresholds: dict[str, Any] = field(default_factory=dict)
    trained_on: dict[str, int] = field(default_factory=dict)
    created: str = ""


class LocalJDE:
    """The default DecisionEngine. Thread-safe for concurrent ``decide`` calls (read-only model)."""

    def __init__(self, heads: MultiHead, meta: ModelMeta, encoder: DecisionEncoder, semantic: SemanticRouter,
                 thresholds: Thresholds, catalog: Any = None, cache_size: int = 2048):
        self.heads = heads
        self.meta = meta
        self.encoder = encoder
        self.semantic = semantic
        self.thresholds = thresholds
        self.catalog = catalog
        self.cache = DecisionCache(cache_size)
        self.families = list(meta.classes["route_family"])
        self._fam_index = {f: i for i, f in enumerate(self.families)}

    # ---------------------------------------------------------------- persistence
    @classmethod
    def load(cls, path: Path | str | None = None, encoder: Optional[DecisionEncoder] = None, catalog: Any = None) -> "LocalJDE":
        path = Path(path) if path else latest_model_dir()
        if path is None or not (path / "meta.json").exists():
            raise FileNotFoundError("No trained JDE model. Run: python -m jarvis.decision.train")
        meta = ModelMeta(**json.loads((path / "meta.json").read_text(encoding="utf-8")))
        arrays = dict(np.load(path / "heads.npz"))
        heads = MultiHead.from_arrays(arrays, {k: tuple(v) for k, v in meta.classes.items()}, tuple(meta.multilabel))
        enc = encoder or make_encoder(meta.encoder)
        protos = dict(np.load(path / "prototypes.npz"))
        semantic = SemanticRouter(list(meta.classes["route_family"]), protos["vectors"], protos["labels"], meta.semantic_scale)
        th = Thresholds(**meta.thresholds) if meta.thresholds else Thresholds()
        return cls(heads, meta, enc, semantic, th, catalog=catalog)

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path / "heads.npz", **self.heads.to_arrays())
        np.savez_compressed(path / "prototypes.npz", vectors=self.semantic.P, labels=self.semantic.labels)
        self.meta.thresholds = asdict(self.thresholds)
        (path / "meta.json").write_text(json.dumps(asdict(self.meta), indent=1), encoding="utf-8")

    @property
    def versions(self) -> dict[str, str]:
        return {"decision_model_version": self.meta.decision_model_version, "encoder_version": self.meta.encoder_version,
                "route_catalog_version": self.meta.route_catalog_version, "threshold_version": self.thresholds.version}

    # ---------------------------------------------------------------- inference
    def featurize(self, states: list[DecisionState]) -> tuple[np.ndarray, np.ndarray]:
        E = self.encoder.encode([s.text for s in states])
        R = np.vstack([rule_features(s) for s in states])
        return np.hstack([E, R]).astype(np.float32), E

    def raw_outputs(self, X: np.ndarray, E: np.ndarray) -> dict[str, np.ndarray]:
        """Calibrated head outputs for a batch (used by decide() and by the evaluator)."""
        logits = self.heads.logits(X)
        m = self.meta
        p_clf = softmax(logits["route_family"])
        p_sem = self.semantic.probabilities(E)
        w = m.fusion_semantic_weight
        fused = np.log(p_clf + 1e-9) + w * np.log(p_sem + 1e-9)
        route = softmax(fused / max(m.route_temperature, 1e-3))
        out = {"route": route, "route_clf": p_clf, "route_sem": p_sem,
               "complexity": softmax(logits["complexity"] / max(m.complexity_temperature, 1e-3))}
        for head in BINARY_HEADS:
            z = logits[head][:, 1] - logits[head][:, 0]
            a, b = m.platt.get(head, [1.0, 0.0])
            out[head] = sigmoid(a * z + b)
        if "families" in logits:
            out["families"] = sigmoid(logits["families"])
        return out

    def decide(self, request: DecisionRequest | DecisionState | str) -> DecisionResult:
        t0 = time.perf_counter()
        if isinstance(request, str):
            request = DecisionRequest(DecisionState(text=request))
        elif isinstance(request, DecisionState):
            request = DecisionRequest(request)
        state = request.state
        key = "|".join([normalize_text(state.text), state.signature(), *self.versions.values()])
        cached = self.cache.get(key)
        if cached is not None:
            res = DecisionResult(**{**cached.__dict__})
            res.cache_hit = True
            res.latency_ms = (time.perf_counter() - t0) * 1000
            return res
        X, E = self.featurize([state])
        out = {k: v[0] for k, v in self.raw_outputs(X, E).items()}
        res = self._interpret(state, out)
        res.latency_ms = (time.perf_counter() - t0) * 1000
        self.cache.put(key, res)
        return res

    def _interpret(self, state: DecisionState, out: dict[str, np.ndarray]) -> DecisionResult:
        fams = self.families
        route = out["route"]
        order = np.argsort(-route)
        top, second = int(order[0]), int(order[1])
        route_value, conf = fams[top], float(route[top])
        answers: dict[str, Any] = {
            "route_family": ChoiceAnswer(route_value, conf, {f: float(route[i]) for i, f in enumerate(fams)},
                                         [(fams[i], float(route[i])) for i in order[:5]]),
        }
        cx = out["complexity"]
        level = int(np.argmax(cx))
        answers["complexity"] = ScoreAnswer(COMPLEXITY_LEVELS[level], float((cx * np.arange(len(cx))).sum() / (len(cx) - 1)))
        for head in BINARY_HEADS:
            answers[head] = ProbabilityAnswer(float(out[head]))
        p = {h: float(out[h]) for h in BINARY_HEADS}

        # multi-family top-K (primary always first)
        fam_scores: dict[str, float] = {route_value: conf}
        if "families" in out:
            for i, f in enumerate(self.meta.classes["families"]):
                if out["families"][i] >= 0.35 and f not in ("CLARIFY", "UNKNOWN"):
                    fam_scores[f] = max(fam_scores.get(f, 0.0), float(out["families"][i]))
        families = sorted(fam_scores.items(), key=lambda kv: -kv[1])[:5]

        clf_top = int(np.argmax(out["route_clf"]))
        sem_top = int(np.argmax(out["route_sem"]))
        disagreement = clf_top != sem_top and (conf - float(route[second])) < self.thresholds.disagreement_margin

        # advisory risk class (policy still decides): worst of route family and risk heads
        risk = "READ_ONLY"
        if self.catalog is not None:
            risk = self.catalog.risk_of(route_value)
            if risk == "PRIVILEGED":
                risk = "DESTRUCTIVE"
        if p["is_action"] < 0.5:
            risk = "READ_ONLY"
        if p["external_effect"] >= 0.5:
            risk = "EXTERNAL_EFFECT" if risk not in ("DESTRUCTIVE",) else risk
        if p["destructive"] >= 0.5:
            risk = "DESTRUCTIVE"
        threshold = float(self.thresholds.execute.get(risk, 0.9))

        informational = route_value in ("KNOWLEDGE", "RAG", "WEB")
        # consistency: an external/destructive request must land on a family that can have that effect
        fam_risk = self.catalog.risk_of(route_value) if self.catalog is not None else "READ_ONLY"
        incoherent = (p["is_action"] >= 0.5 and not informational
                      and ((p["external_effect"] >= 0.5 and fam_risk not in ("EXTERNAL_EFFECT", "DESTRUCTIVE", "PRIVILEGED"))
                           or (p["destructive"] >= 0.5 and fam_risk not in ("DESTRUCTIVE", "PRIVILEGED"))))
        if route_value == "UNKNOWN" or p["supported"] < 0.35:
            gate = Gate("UNSUPPORTED", risk, threshold, "outside supported capabilities")
        elif not informational and route_value not in ("CLARIFY", "PLANNER") and p["is_action"] < 0.5:
            # a question about an action, or a negated one: never executes a tool
            gate = Gate("FALLBACK", "READ_ONLY", threshold, "not an action request (question about it, or negated)")
        elif incoherent:
            gate = Gate("CLARIFY", risk, threshold, f"{route_value} cannot have the predicted side effect; routes disagree")
        elif risk in HIGH_RISK and (self.families[int(np.argmax(out["route_clf"]))] != self.families[int(np.argmax(out["route_sem"]))]
                                    and self.meta.fusion_semantic_weight > 0):
            gate = Gate("CLARIFY", risk, threshold, "consequential and the two routers disagree")
        elif route_value == "CLARIFY" or p["ambiguous"] >= self.thresholds.ambiguity:
            gate = Gate("CLARIFY", risk, threshold, "ambiguous or unresolved reference")
        elif disagreement:
            gate = Gate("CLARIFY" if risk in HIGH_RISK else "FALLBACK", risk, threshold,
                        f"semantic router ({fams[sem_top]}) and classifier ({fams[clf_top]}) disagree")
        elif conf >= threshold:
            gate = Gate("EXECUTE", risk, threshold, "confident")
        elif risk in HIGH_RISK:
            gate = Gate("CLARIFY", risk, threshold, "consequential and not confident enough")
        elif conf >= self.thresholds.fallback_min:
            gate = Gate("FALLBACK", risk, threshold, "below execute gate")
        else:
            gate = Gate("ABSTAIN", risk, threshold, "low confidence")

        if p["needs_planner"] >= 0.5 or level >= 3 or route_value == "PLANNER":
            model_class = "PLANNER"
        elif route_value == "DESKTOP" and p["needs_llm"] >= 0.5:
            model_class = "VISION"
        elif p["needs_llm"] >= 0.5 or route_value in ("KNOWLEDGE", "RAG", "WEB"):
            model_class = "SMALL"
        elif gate.action == "FALLBACK":
            model_class = "TINY"          # the small Qwen router may arbitrate
        else:
            model_class = "NONE"

        availability = "NOT_CONFIGURED" if route_value in state.unavailable else "AVAILABLE"
        return DecisionResult(answers=answers, gate=gate, model_class=model_class, families=families,
                              disagreement=disagreement, availability=availability, versions=self.versions,
                              signals={"route_clf_top": float(out["route_clf"][clf_top]), "route_sem_top": float(out["route_sem"][sem_top])})


class HostedJevAdapter:
    """Placeholder for benchmarking a hosted decision API later. Disabled unless explicitly configured;
    never used when JDE_LOCAL_ONLY is set (the default)."""

    def __init__(self, endpoint: str = "", api_key: str = ""):
        if local_only():
            raise RuntimeError("JDE_LOCAL_ONLY is enabled: hosted decision engines are not allowed")
        if not endpoint:
            raise RuntimeError("HostedJevAdapter needs an endpoint; LocalJDE is the default engine")
        self.endpoint, self.api_key = endpoint, api_key

    def decide(self, request: DecisionRequest) -> DecisionResult:  # pragma: no cover - not implemented by design
        raise NotImplementedError("Hosted decision engines are not part of the default build")


def local_only() -> bool:
    return os.environ.get("JDE_LOCAL_ONLY", "true").strip().lower() not in ("0", "false", "no")


def latest_model_dir(root: Path = MODEL_ROOT) -> Optional[Path]:
    current = root / "CURRENT"
    if current.exists():
        name = current.read_text(encoding="utf-8").strip()
        if (root / name / "meta.json").exists():
            return root / name
    dirs = sorted([d for d in root.glob("jde-*") if (d / "meta.json").exists()])
    return dirs[-1] if dirs else None


_engine: Optional[LocalJDE] = None
_engine_error: str = ""


def get_engine() -> Optional[LocalJDE]:
    """Process-wide engine, loaded once. Returns None (never raises) so JDE can never break routing."""
    global _engine, _engine_error
    if _engine is None and not _engine_error:
        first = latest_model_dir()
        others = sorted((d for d in MODEL_ROOT.glob("jde-*") if (d / "meta.json").exists() and d != first), reverse=True)
        # CURRENT first; if its encoder assets are missing on this machine (e.g. GloVe not downloaded),
        # fall back to the newest model that does load.
        for path in ([first] if first else []) + others:
            try:
                from jarvis.decision.catalog import default_catalog
                _engine = LocalJDE.load(path, catalog=default_catalog())
                break
            except Exception as exc:
                _engine_error = f"{type(exc).__name__}: {exc}"
        if _engine is not None:
            _engine_error = ""
        else:
            _engine_error = _engine_error or "no trained model"
            logger.info("JDE unavailable (%s); the existing router continues alone", _engine_error)
    return _engine


def set_engine(engine: Optional[LocalJDE]) -> None:
    global _engine, _engine_error
    _engine, _engine_error = engine, ""


__all__ = ["DecisionEngine", "LocalJDE", "HostedJevAdapter", "get_engine", "set_engine", "FEATURE_NAMES"]
