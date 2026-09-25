"""JARVIS Decision Engine: unit tests (no network, no LLM). Uses the committed hash-encoder model."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

from jarvis.decision.calibration import brier_binary, ece, fit_platt, fit_temperature
from jarvis.decision.classifier import softmax
from jarvis.decision.dataset import holdout_texts, load_suite, parse_suite, training_pool
from jarvis.decision.encoder import HashingEncoder, normalize_text
from jarvis.decision.engine import MODEL_ROOT, HostedJevAdapter, LocalJDE
from jarvis.decision.runtime import JDERuntime
from jarvis.decision.schemas import ROUTE_FAMILIES, DecisionState
from jarvis.decision.thresholds import MIN_THRESHOLD, Thresholds


def _hash_model_dir() -> Path | None:
    for d in sorted(MODEL_ROOT.glob("jde-*"), reverse=True):
        meta = d / "meta.json"
        if meta.exists() and json.loads(meta.read_text(encoding="utf-8"))["encoder"] == "hash":
            return d
    return None


@pytest.fixture(scope="module")
def engine():
    path = _hash_model_dir()
    if path is None:
        pytest.skip("no trained hash JDE model in models/jde")
    return LocalJDE.load(path)


# ------------------------------------------------------------------ encoder / data
def test_hashing_encoder_is_deterministic_and_normalised():
    enc = HashingEncoder()
    a, b = enc.encode(["open chrome please"]), enc.encode(["open chrome please"])
    assert np.allclose(a, b)
    assert abs(np.linalg.norm(a[0]) - 1.0) < 1e-5
    assert enc.encode([""]).sum() == 0


def test_normalize_text_masks_volatile_tokens():
    t = normalize_text("Send report.pdf to +91 98765 43210 and https://x.com/a at 5")
    assert "filetoken pdf" in t and "phonenumbertoken" in t and "urltoken" in t and "5" not in t


def test_suites_have_the_required_sizes_and_valid_labels():
    sizes = {s: len(load_suite(s)) for s in ("dev", "holdout", "adversarial")}
    assert sizes == {"dev": 350, "holdout": 100, "adversarial": 50}
    for s in sizes:
        for ex in load_suite(s):
            assert ex.route in ROUTE_FAMILIES


def test_training_pool_never_contains_evaluation_texts():
    held = holdout_texts()
    pool = {normalize_text(e.text) for e in training_pool()}
    assert not (pool & held)


def test_suite_parser_reads_flags_and_context(tmp_path):
    suite = tmp_path / "s.txt"
    suite.write_text("# comment\nWHATSAPP | alx1 | tell him yes | res=ContactResource;prev=WHATSAPP\n", encoding="utf-8")
    [ex] = parse_suite(suite)
    assert ex.route == "WHATSAPP" and ex.is_action and ex.needs_llm and ex.external_effect and not ex.destructive
    st = ex.state()
    assert st.resources == ["ContactResource"] and st.previous_route == "WHATSAPP"


# ------------------------------------------------------------------ calibration / thresholds
def test_temperature_and_platt_reduce_overconfidence():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 400)
    logits = rng.normal(0, 1, (400, 3))
    logits[np.arange(400), y] += 1.0
    logits *= 4  # overconfident
    t = fit_temperature(logits, y)
    assert t > 1.5
    def route_ece(p):
        return ece(p.max(axis=1), (p.argmax(axis=1) == y).astype(float))
    assert route_ece(softmax(logits / t)) < route_ece(softmax(logits))
    z = rng.normal(0, 3, 500)
    yb = (rng.random(500) < 1 / (1 + np.exp(-z / 3))).astype(float)
    a, b = fit_platt(z, yb)
    assert brier_binary(1 / (1 + np.exp(-(a * z + b))), yb) <= brier_binary(1 / (1 + np.exp(-z)), yb) + 1e-9


def test_thresholds_are_fitted_to_target_precision_not_hardcoded():
    rng = np.random.default_rng(1)
    conf = rng.random(400)
    correct = rng.random(400) < conf  # accuracy grows with confidence
    th = Thresholds.fit(conf, correct, ["REVERSIBLE"] * 400, "t")
    t = th.execute["REVERSIBLE"]
    assert t >= MIN_THRESHOLD["REVERSIBLE"]
    assert correct[conf >= t].mean() >= 0.97
    thin = Thresholds.fit(conf[:10], correct[:10], ["EXTERNAL_EFFECT"] * 10, "t")
    assert thin.execute["EXTERNAL_EFFECT"] >= 0.92  # too little data -> conservative fallback


# ------------------------------------------------------------------ engine behaviour
def test_engine_answers_every_typed_question(engine):
    r = engine.decide(DecisionState(text="open notepad"))
    assert r.route.value in ROUTE_FAMILIES
    for name in ("is_action", "needs_llm", "needs_planner", "needs_context", "needs_web", "external_effect",
                 "destructive", "ambiguous", "supported"):
        assert 0.0 <= r.p(name) <= 1.0
    assert r.model_class in ("NONE", "TINY", "SMALL", "PLANNER", "VISION")
    assert set(r.versions) >= {"decision_model_version", "encoder_version", "route_catalog_version", "threshold_version"}
    d = r.to_dict()
    assert d["gate"]["action"] in ("EXECUTE", "FALLBACK", "CLARIFY", "ABSTAIN", "UNSUPPORTED")


def test_obvious_routes(engine):
    assert engine.decide("open notepad").route.value == "APP"
    assert engine.decide("what is photosynthesis").route.value == "KNOWLEDGE"
    assert engine.decide("send a whatsapp message to ravi saying i'm late").route.value == "WHATSAPP"


def test_high_risk_route_never_executes_below_its_gate(engine):
    for text in ("delete it", "send it", "tell him yes", "uninstall that"):
        r = engine.decide(text)
        if r.gate.action == "EXECUTE":
            assert r.route.confidence >= r.gate.threshold
            assert r.gate.risk_class not in ("EXTERNAL_EFFECT", "DESTRUCTIVE") or r.gate.threshold >= 0.85


def test_questions_about_actions_are_not_executed_as_actions(engine):
    r = engine.decide("how do i uninstall steam")
    assert not (r.gate.action == "EXECUTE" and r.route.value == "PACKAGE")


def test_cache_hits_and_context_changes_the_key(engine):
    engine.cache.clear()
    a = engine.decide(DecisionState(text="close it"))
    b = engine.decide(DecisionState(text="close it"))
    c = engine.decide(DecisionState(text="close it", resources=["ApplicationResource"]))
    assert not a.cache_hit and b.cache_hit and not c.cache_hit


def test_decision_latency_is_system_one_fast(engine):
    engine.cache.clear()
    engine.decide("warm up")
    t = time.perf_counter()
    for i in range(200):
        engine.decide(f"open the file number {i} alpha")
    assert (time.perf_counter() - t) / 200 < 0.02  # < 20 ms each even on a slow CI box (≈1 ms typical)


def test_hosted_adapter_is_refused_when_local_only(monkeypatch):
    monkeypatch.setenv("JDE_LOCAL_ONLY", "true")
    with pytest.raises(RuntimeError):
        HostedJevAdapter("https://example.invalid", "key")


# ------------------------------------------------------------------ runtime / stages
class _FakeDecision:
    lane = "LANE_0"
    intent = "open_app"
    confidence = 0.99
    source = "EXACT"
    context_trace = None


def test_shadow_runtime_logs_without_affecting_routing(engine, tmp_path):
    rt = JDERuntime(stage="shadow", engine=engine, log_path=tmp_path / "shadow.jsonl")
    rt.observe("open notepad", _FakeDecision(), channel="whatsapp:123")
    rt.flush()
    rec = json.loads((tmp_path / "shadow.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rec["router"]["intent"] == "open_app" and rec["router"]["family"] == "APP"
    assert rec["jde"]["route"] in ROUTE_FAMILIES and rec["channel"] == "whatsapp"
    assert rt.answer_as_knowledge("what is photosynthesis") is False  # shadow never diverts


def test_runtime_off_and_broken_engine_are_harmless(tmp_path):
    off = JDERuntime(stage="off", log_path=tmp_path / "a.jsonl")
    off.observe("open notepad", _FakeDecision())
    assert off.engine() is None and not (tmp_path / "a.jsonl").exists()

    class Broken:
        def decide(self, state):
            raise RuntimeError("boom")

    rt = JDERuntime(stage="read_only", engine=Broken(), log_path=tmp_path / "b.jsonl")
    rt.observe("open notepad", _FakeDecision())
    rt.flush()
    assert rt.answer_as_knowledge("what is a cpu") is False


def test_stage_b_only_diverts_calibrated_knowledge_questions(engine, tmp_path):
    rt = JDERuntime(stage="read_only", engine=engine, log_path=tmp_path / "s.jsonl")
    assert rt.answer_as_knowledge("send a whatsapp message to ravi saying i'm late") is False
    assert rt.answer_as_knowledge("delete everything in my downloads folder") is False
