"""Verify acquired Tanglish artifacts and row counts against the manifest."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/tanglish"
manifest = json.loads((BASE / "dataset_manifest.json").read_text(encoding="utf-8"))
for item in manifest["sources"]:
    assert item["original_rows"] >= item["usable_rows"] > 0, item["id"]
    assert sum(x["rows"] for x in item["processed_artifacts"]) == item["usable_rows"], item["id"]
    for artifact in item["artifacts"] + item["processed_artifacts"]:
        path = ROOT / artifact["path"]
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        assert digest.hexdigest() == artifact["sha256"], artifact["path"]
        assert path.stat().st_size == artifact["bytes"], artifact["path"]
    for artifact in item["processed_artifacts"]:
        with (ROOT / artifact["path"]).open(encoding="utf-8") as stream:
            assert sum(1 for _ in stream) == artifact["rows"], artifact["path"]
    if item["decision"] == "EVALUATION_ONLY":
        assert all("train" not in path["path"] or item["id"] == "tamiltech_qa" for path in item["processed_artifacts"])
print(f"Verified {len(manifest['sources'])} sources, hashes, and processed row counts")
