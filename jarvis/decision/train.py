"""Train, calibrate and version a LocalJDE model.

    python -m jarvis.decision.train                 # default offline encoder (hash)
    python -m jarvis.decision.train --encoder minilm+hash
    python -m jarvis.decision.train --encoder bge-small+hash --promote

Steps: training pool -> TRAIN / VALIDATION split -> one shared input (text embedding + rule/context
signals) -> heads (route, complexity, 9 binary, multi-label families) -> calibration on VALIDATION
(temperature for route/complexity, Platt for binary heads) -> fusion weight + semantic scale on
VALIDATION -> risk thresholds on VALIDATION -> save under models/jde/<version>/.
Evaluation suites (dev / holdout / adversarial / generalization holdout) never enter training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from jarvis.decision.calibration import fit_platt, fit_temperature
from jarvis.decision.catalog import RouteCatalog
from jarvis.decision.classifier import LinearHead, MultiHead, MultiLabelHead, softmax
from jarvis.decision.dataset import split, training_pool
from jarvis.decision.encoder import make_encoder
from jarvis.decision.engine import MODEL_ROOT, LocalJDE, ModelMeta
from jarvis.decision.features import FEATURE_NAMES, rule_features
from jarvis.decision.schemas import BINARY_HEADS, COMPLEXITY_LEVELS, ROUTE_FAMILIES, LabeledExample
from jarvis.decision.semantic_router import SemanticRouter
from jarvis.decision.thresholds import Thresholds


def featurize(encoder, examples: list[LabeledExample]) -> tuple[np.ndarray, np.ndarray]:
    E = encoder.encode([e.text for e in examples])
    R = np.vstack([rule_features(e.state()) for e in examples])
    return np.hstack([E, R]).astype(np.float32), E


def labels(examples: list[LabeledExample]) -> dict[str, np.ndarray]:
    fam_idx = {f: i for i, f in enumerate(ROUTE_FAMILIES)}
    y = {"route_family": np.array([fam_idx[e.route] for e in examples]),
         "complexity": np.array([min(4, max(0, e.complexity)) for e in examples])}
    for h in BINARY_HEADS:
        y[h] = np.array([e.binary(h) for e in examples])
    fams = np.zeros((len(examples), len(ROUTE_FAMILIES)), dtype=np.float32)
    for i, e in enumerate(examples):
        for f in set(e.families or [e.route]):
            fams[i, fam_idx[f]] = 1.0
    y["families"] = fams
    return y


def train(encoder_spec: str = "hash", seed: int = 13, epochs: int = 300, l2: float = 3e-4, log=print) -> tuple[LocalJDE, dict]:
    t0 = time.time()
    catalog = RouteCatalog.build()
    pool = training_pool(seed=seed)
    tr, va = split(pool)
    encoder = make_encoder(encoder_spec)
    log(f"pool={len(pool)} train={len(tr)} val={len(va)} encoder={encoder.name}")
    Xtr, Etr = featurize(encoder, tr)
    Xva, Eva = featurize(encoder, va)
    ytr, yva = labels(tr), labels(va)

    heads: dict = {
        "route_family": LinearHead("route_family", ROUTE_FAMILIES).fit(Xtr, ytr["route_family"], l2=l2, epochs=epochs, seed=seed),
        "complexity": LinearHead("complexity", COMPLEXITY_LEVELS).fit(Xtr, ytr["complexity"], l2=l2, epochs=epochs, seed=seed),
        "families": MultiLabelHead("families", ROUTE_FAMILIES).fit(Xtr, ytr["families"], l2=l2, epochs=epochs, seed=seed),
    }
    for h in BINARY_HEADS:
        heads[h] = LinearHead(h, ("no", "yes")).fit(Xtr, ytr[h], l2=l2, epochs=epochs, seed=seed)
    mh = MultiHead(heads)
    log(f"heads trained in {time.time() - t0:.1f}s")

    # --- semantic router over registry-derived prototypes; scale + fusion weight picked on VALIDATION
    semantic = SemanticRouter.from_texts(encoder, catalog.prototypes(), list(ROUTE_FAMILIES))
    lv = mh.logits(Xva)
    p_clf = softmax(lv["route_family"])
    sims = semantic.similarities(Eva)
    best = (float("inf"), 12.0, 0.0, 1.0)
    for scale in (4.0, 8.0, 12.0, 20.0, 30.0):
        p_sem = softmax(sims * scale)
        for w in (0.0, 0.15, 0.3, 0.5, 0.75, 1.0):
            fused = np.log(p_clf + 1e-9) + w * np.log(p_sem + 1e-9)
            t = fit_temperature(fused, yva["route_family"])
            p = softmax(fused / t)
            nll = -np.log(p[np.arange(len(va)), yva["route_family"]] + 1e-12).mean()
            if nll < best[0]:
                best = (nll, scale, w, t)
    _, scale, w_sem, t_route = best
    semantic.scale = scale
    log(f"fusion: semantic weight={w_sem} scale={scale} route T={t_route:.2f}")

    platt = {}
    for h in BINARY_HEADS:
        z = lv[h][:, 1] - lv[h][:, 0]
        platt[h] = list(fit_platt(z, yva[h]))
    t_cx = fit_temperature(lv["complexity"], yva["complexity"])

    blob = json.dumps([encoder_spec, len(tr), seed, epochs, l2, catalog.version]).encode()
    version = f"jde-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{hashlib.sha1(blob).hexdigest()[:6]}"
    meta = ModelMeta(
        decision_model_version=version, encoder=encoder_spec, encoder_version=encoder.name,
        route_catalog_version=catalog.version, threshold_version=f"thr-{version}", feature_names=list(FEATURE_NAMES),
        classes={"route_family": list(ROUTE_FAMILIES), "complexity": list(COMPLEXITY_LEVELS),
                 "families": list(ROUTE_FAMILIES), **{h: ["no", "yes"] for h in BINARY_HEADS}},
        multilabel=["families"], route_temperature=t_route, platt=platt, complexity_temperature=t_cx,
        fusion_semantic_weight=w_sem, semantic_scale=scale,
        trained_on={"train": len(tr), "validation": len(va)}, created=datetime.now().isoformat(timespec="seconds"),
    )
    engine = LocalJDE(mh, meta, encoder, semantic, Thresholds(version=meta.threshold_version), catalog=catalog)

    # --- risk-gated thresholds on VALIDATION (calibrated fused confidence vs correctness, by advisory risk)
    out = engine.raw_outputs(Xva, Eva)
    route = out["route"]
    conf = route.max(axis=1)
    correct = (route.argmax(axis=1) == yva["route_family"]).astype(float)
    risks = []
    for i, ex in enumerate(va):
        risk = "READ_ONLY"
        if ex.is_action:
            risk = catalog.risk_of(ex.route)
            risk = "DESTRUCTIVE" if risk == "PRIVILEGED" else risk
        if ex.external_effect:
            risk = "EXTERNAL_EFFECT"
        if ex.destructive:
            risk = "DESTRUCTIVE"
        risks.append(risk)
    engine.thresholds = Thresholds.fit(conf, correct, risks, version=meta.threshold_version)
    log(f"thresholds: {engine.thresholds.execute} (n={engine.thresholds.fitted_from})")
    stats = {"train": len(tr), "validation": len(va), "val_route_acc": float(correct.mean()), "seconds": time.time() - t0}
    return engine, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--encoder", default="hash")
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--promote", action="store_true", help="make this version CURRENT (only after the benchmark says so)")
    args = ap.parse_args(argv)
    engine, stats = train(args.encoder, epochs=args.epochs)
    path = MODEL_ROOT / engine.meta.decision_model_version
    engine.save(path)
    print(f"saved {path} ({stats})")
    if args.promote:
        (MODEL_ROOT / "CURRENT").write_text(engine.meta.decision_model_version, encoding="utf-8")
        print("promoted to CURRENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
