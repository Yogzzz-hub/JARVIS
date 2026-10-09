"""Record immutable Stage-2 artifact hashes and frozen Stage-1 baseline hashes."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
paths = [
    "data/tanglish/dataset_manifest.json", "reports/TANGLISH_DATA_AUDIT.md",
    "data/tanglish/generated/semantic_stage2/train.jsonl.gz",
    "data/tanglish/generated/semantic_stage2/dev.jsonl.gz",
    "data/tanglish/generated/semantic_stage2/test.jsonl.gz",
    "data/tanglish/generated/semantic_stage2/locked_holdout.jsonl.gz",
    "data/tanglish/manifests/semantic_stage2_build.json",
    "data/tanglish/manifests/semantic_stage2_leakage.json",
    "data/tanglish/manifests/semantic_stage2_training.json",
    "data/tanglish/manifests/semantic_stage2_raw_test.json",
    "data/tanglish/manifests/semantic_stage2_gate.json",
    "data/tanglish/manifests/semantic_stage2_speech_alternative.json",
    "data/tanglish/manifests/semantic_stage2_latency.json",
    "data/tanglish/manifests/semantic_stage2_encoder_benchmark.json",
    "scripts/build_tanglish_semantic_stage2.py",
    "reports/TANGLISH_SEMANTIC_LEAKAGE.md",
    "reports/TANGLISH_SEMANTIC_TRAINING.md",
    "models/tanglish_stage2/model.pkl", "models/tanglish_stage2/action_gate.pkl",
    "models/tanglish_stage2/speech_alternative.pkl",
]
records = []
for relative in paths:
    path = ROOT / relative
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    records.append({"path": relative, "bytes": path.stat().st_size, "sha256": h.hexdigest()})
manifest = {"sealed_utc": datetime.now(timezone.utc).isoformat(), "artifacts": records,
            "locked_holdout_policy": "No model selection or error inspection; never overwrite this artifact."}
output = ROOT / "data/tanglish/manifests/semantic_stage2_artifacts.json"
output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print("Sealed", len(records), "artifacts")
