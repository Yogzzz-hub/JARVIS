"""Measure local semantic-only latency; excludes retrieval, policy and tools."""

import json
import pickle
import time

import numpy as np

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.train_tanglish_semantic_stage2 import MODEL_DIR, input_text, read


with (MODEL_DIR / "model.pkl").open("rb") as stream:
    action = pickle.load(stream)
with (MODEL_DIR / "speech_alternative.pkl").open("rb") as stream:
    speech = pickle.load(stream)
phases = {name: [] for name in ("normalization", "char_encoder", "action_decode", "word_encoder", "speech_gate_decode", "total_semantic")}
for row in list(read("test"))[:300]:
    t0 = time.perf_counter()
    value = input_text(row)
    t1 = time.perf_counter()
    char = action["vectorizer"].transform([value])
    t2 = time.perf_counter()
    action["action_head"].predict(char)
    t3 = time.perf_counter()
    word = speech["vectorizer"].transform([value])
    t4 = time.perf_counter()
    speech["gate"].predict_proba(word)
    speech["speech"].predict_proba(word)
    t5 = time.perf_counter()
    for name, value in zip(phases, (t1-t0, t2-t1, t3-t2, t4-t3, t5-t4, t5-t0)):
        phases[name].append(value * 1000)
result = {"n": 300, "unit": "ms", "scope": "semantic only; excludes capability retrieval, policy, execution and verifier",
          "phases": {name: {"p50": float(np.quantile(values, .5)), "p95": float(np.quantile(values, .95)),
                            "p99": float(np.quantile(values, .99))} for name, values in phases.items()}}
(BASE / "manifests/semantic_stage2_latency.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result["phases"]["total_semantic"], indent=2))
