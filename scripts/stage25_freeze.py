"""Pin and verify Stage 2.5 data, ontology, and offline policy revisions."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.stage25_gold_data import AFFORDANCES, OUT, ROOT, SLOTS, SPEECH
from scripts.tanglish_stage24_ontology import ACTION_FAMILY

MANIFEST = OUT / "stage25_freeze_manifest.json"
FILES = {
    "corpus": OUT / "stage25_candidates.jsonl",
    "audit_queue": OUT / "independent_audit_queue.jsonl",
    "generation_manifest": OUT / "stage25_generation_manifest.json",
    "queue_manifest": OUT / "independent_audit_queue_manifest.json",
    "final_gate": OUT / "stage25_final_gate.json",
    "generator": ROOT / "scripts" / "stage25_generate.py",
    "validator_and_frame_schema": ROOT / "scripts" / "stage25_gold_data.py",
    "ontology": ROOT / "scripts" / "tanglish_stage24_ontology.py",
    "conversation_state_policy": ROOT / "scripts" / "stage25_conversation_state.py",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def snapshot() -> dict:
    gate = json.loads(FILES["final_gate"].read_text(encoding="utf-8"))
    queue = json.loads(FILES["queue_manifest"].read_text(encoding="utf-8"))
    files = {name: {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": digest(path)} for name, path in FILES.items()}
    if not gate.get("passed") or len(gate.get("checks", {})) != 16 or not all(gate["checks"].values()):
        raise ValueError("Stage 2.5 final machine gate is not 16/16 PASS")
    if gate.get("corpus_sha256") != files["corpus"]["sha256"] or queue.get("source_sha256") != files["corpus"]["sha256"] or queue.get("queue_sha256") != files["audit_queue"]["sha256"]:
        raise ValueError("Corpus or queue no longer matches the verified gate")
    if queue.get("rows") != 750 or min(queue.get("language", {}).get("TANGLISH", 0), queue.get("language", {}).get("TAMIL", 0)) < 300:
        raise ValueError("Audit queue lacks required size or language balance")
    return {
        "status": "FROZEN_PENDING_HUMAN_AUDIT",
        "files": files,
        "ontology_sha256": semantic_digest(ACTION_FAMILY),
        "speech_act_schema_sha256": semantic_digest(sorted(SPEECH)),
        "slot_schema_sha256": semantic_digest(sorted(SLOTS)),
        "action_affordances_sha256": semantic_digest({k: sorted(v) for k, v in AFFORDANCES.items()}),
        "audit_queue_rows": queue["rows"],
        "audit_queue_language": queue["language"],
    }


def verify() -> list[str]:
    if not MANIFEST.exists():
        return ["freeze_manifest_missing"]
    frozen = json.loads(MANIFEST.read_text(encoding="utf-8"))
    current = snapshot()
    return [key for key, value in current.items() if frozen.get(key) != value]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()
    if args.create:
        if MANIFEST.exists():
            raise SystemExit("Freeze manifest already exists; verify it or explicitly archive before a new freeze")
        frozen = snapshot()
        frozen["frozen_utc"] = datetime.now(timezone.utc).isoformat()
        MANIFEST.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = verify()
    print(json.dumps({"frozen": not errors, "errors": errors, "manifest": str(MANIFEST)}, indent=2))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
