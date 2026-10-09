"""Local human audit. No training, inference, production writes or holdout reads."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import secrets
import threading
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.stage25_admit import read_jsonl
from scripts.stage25_freeze import verify, MANIFEST
from scripts.stage25_gold_data import OUT, ROOT, validate_row, COARSE, SLOTS
from scripts.tanglish_stage24_ontology import ACTION_FAMILY

DECISIONS = {"APPROVE", "REJECT", "FIX_LABEL", "AMBIGUOUS"}
CONFIG = ROOT / "jarvis/config/nlp_candidate.json"
AI_STATUSES = {"LIKELY_APPROVE", "MANUAL_REVIEW", "LIKELY_REJECT"}


def validate_precheck(rows, queue):
    by_id = {item["row_id"]: item for item in queue}
    if len(rows) != len(queue) or len({r.get("row_id") for r in rows}) != len(queue):
        raise ValueError("Precheck count or unique IDs mismatch")
    result = {}
    for row in rows:
        item = by_id.get(row.get("row_id"))
        if not item or row.get("text") != item["text"]:
            raise ValueError("Precheck ID/text mismatch: " + str(row.get("row_id")))
        if row.get("language") != item["language"] or row.get("original_frame") != item["frame"]:
            raise ValueError("Precheck original annotation mismatch: " + item["row_id"])
        status = row.get("suggested_status")
        if status not in AI_STATUSES or not isinstance(row.get("confidence"), (str, int, float)) or not isinstance(row.get("reason"), str):
            raise ValueError("Invalid auxiliary metadata: " + item["row_id"])
        result[item["row_id"]] = {"ai_precheck_status": status,
                                  "ai_precheck_confidence": row["confidence"],
                                  "ai_precheck_reason": row["reason"]}
    return result


class AuditStore:
    def __init__(self, directory=OUT, check=verify):
        self.directory = Path(directory)
        self.check = check
        self.path = self.directory / "unified_human_audit.jsonl"
        self.guard()
        self.queue = read_jsonl(self.directory / "independent_audit_queue.jsonl")
        self.by_id = {item["row_id"]: item for item in self.queue}
        if len(self.by_id) != len(self.queue):
            raise ValueError("Duplicate queue IDs")
        self.latest()  # Refuse corrupt or foreign persisted reviews.

    def precheck(self):
        path = self.directory / "ai_precheck_auxiliary.json"
        if not path.exists():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        queue_hash = hashlib.sha256((self.directory / "independent_audit_queue.jsonl").read_bytes()).hexdigest()
        if value.get("queue_sha256") != queue_hash or set(value["metadata"]) != set(self.by_id):
            raise ValueError("Auxiliary precheck provenance mismatch")
        for row in value["metadata"].values():
            if set(row) != {"ai_precheck_status", "ai_precheck_confidence", "ai_precheck_reason"} or row["ai_precheck_status"] not in AI_STATUSES:
                raise ValueError("Invalid auxiliary precheck fields")
        return value["metadata"]

    def import_precheck(self, path):
        self.guard()
        raw = Path(path).read_bytes()
        rows = [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
        if len(rows) != 750:
            raise ValueError("External precheck must contain exactly 750 rows")
        metadata = validate_precheck(rows, self.queue)
        value = {"source_sha256": hashlib.sha256(raw).hexdigest(),
                 "queue_sha256": hashlib.sha256((self.directory / "independent_audit_queue.jsonl").read_bytes()).hexdigest(),
                 "metadata": metadata}
        target = self.directory / "ai_precheck_auxiliary.json"
        content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if target.exists():
            if target.read_text(encoding="utf-8") != content:
                raise ValueError("Auxiliary import already exists with different contents")
        else:
            with target.open("x", encoding="utf-8") as stream:
                stream.write(content)
        return dict(Counter(r["ai_precheck_status"] for r in metadata.values()))

    def guard(self):
        errors = self.check()
        if errors:
            raise ValueError("Frozen evidence mismatch: " + ", ".join(errors))

    def latest(self):
        records = read_jsonl(self.path) if self.path.exists() else []
        latest = {}
        for record in records:
            item = self.by_id.get(record.get("sample_id"))
            if not item or record.get("row_sha256") != item["row_sha256"]:
                raise ValueError("Review provenance mismatch")
            if record.get("decision") not in DECISIONS or record.get("original_labels") != item["frame"]:
                raise ValueError("Invalid persisted decision or original labels")
            if not record.get("reviewer", "").strip() or not record.get("reviewed_utc"):
                raise ValueError("Missing human provenance")
            if record["decision"] == "FIX_LABEL":
                self.validate(item, record.get("corrected_labels"))
            latest[record["sample_id"]] = record
        return latest

    @staticmethod
    def validate(item, frame):
        if not isinstance(frame, dict) or set(frame) != set(item["frame"]):
            raise ValueError("Correction must preserve the structured frame schema")
        try:
            errors = validate_row({"text": item["text"], "language": item["language"],
                                   "working_context": item.get("working_context"), "frame": frame})
        except (KeyError, TypeError, AttributeError, IndexError) as exc:
            raise ValueError("Malformed structured annotation: " + str(exc)) from exc
        if errors:
            raise ValueError("Invalid annotation: " + ", ".join(errors))

    def save(self, payload):
        self.guard()
        if set(payload) - {"sample_id", "decision", "reviewer", "corrected_labels", "reason", "error_type"}:
            raise ValueError("Only annotation review fields may be submitted")
        item = self.by_id[payload["sample_id"]]
        decision = payload["decision"]
        reviewer = payload["reviewer"].strip()
        if decision not in DECISIONS or not reviewer:
            raise ValueError("Human reviewer and valid decision required")
        corrected = payload.get("corrected_labels")
        if decision == "FIX_LABEL":
            self.validate(item, corrected)
        elif corrected is not None:
            raise ValueError("Only FIX_LABEL may change annotations")
        record = {"sample_id": item["row_id"], "row_id": item["row_id"], "row_sha256": item["row_sha256"],
                  "decision": decision, "reviewer": reviewer,
                  "reviewed_utc": datetime.now(timezone.utc).isoformat(),
                  "original_labels": item["frame"], "corrected_labels": corrected,
                  "reason": payload.get("reason", ""), "error_type": payload.get("error_type", "")}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return self.status()

    def status(self):
        self.guard()
        latest = self.latest()
        counts = Counter(r["decision"] for r in latest.values())
        ai = self.precheck()
        ai_counts = Counter(r["ai_precheck_status"] for r in ai.values())
        flagged = {key for key, r in ai.items() if r["ai_precheck_status"] != "LIKELY_APPROVE"}
        likely = set(ai) - flagged
        config = json.loads(CONFIG.read_text())
        provisional = config.get("NLP_CANDIDATE", {}).get("status") == "AI_ASSISTED_PROVISIONAL"
        development = None
        if provisional:
            directory = ROOT / config["NLP_CANDIDATE"]["dataset_directory"]
            artifact_directory = config["NLP_CANDIDATE"].get("artifact_directory", "candidate")
            progress = directory / artifact_directory / "progress.json"
            summary = directory / artifact_directory / "dashboard_summary.json"
            development = {"status": "AI_ASSISTED_PROVISIONAL", "human_audit": "DEFERRED_NOT_COMPLETED",
                           "data_quality": "PROVISIONAL", "production_acceptance": "NOT_HUMAN_VALIDATED",
                           "flagged_12": "HUMAN_REVIEW_DEFERRED", "shadow": "ON_ADVISORY" if config.get("MULTILINGUAL_NLP_SHADOW") else "OFF",
                           "training": json.loads(progress.read_text()) if progress.exists() else None,
                           "benchmarks": json.loads(summary.read_text()) if summary.exists() else None}
        return {"total": len(self.queue), "reviewed": len(latest),
                "remaining": len(self.queue) - len(latest),
                "counts": {d: counts[d] for d in sorted(DECISIONS)},
                "ai_counts": {s: ai_counts[s] for s in sorted(AI_STATUSES)},
                "flagged_human_review": {"reviewed": len(flagged & latest.keys()), "total": len(flagged)},
                "likely_approve_human_review": {"reviewed": len(likely & latest.keys()), "total": len(likely)},
                "next_step": "WAIT_FOR_OWNER_INSTRUCTION" if len(latest) == len(self.queue) else "HUMAN_REVIEW",
                "audit_complete": len(latest) == len(self.queue),
                "admission_ready": len(latest) == len(self.queue) and not counts["AMBIGUOUS"],
                "training": "PROVISIONAL_DEVELOPMENT_ONLY" if provisional else "BLOCKED_PENDING_HUMAN_AUDIT_AND_DATA_PREPARATION",
                "development": development,
                "deployment": config["deployment_state"], "config": config,
                "dataset_version": "FROZEN_STAGE_2_5",
                "split_sizes": None, "benchmarks": None}

    def admit(self):
        """Seal reviewed positives only; never admit unaudited synthetic rows."""
        status = self.status()
        if not status["admission_ready"]:
            raise ValueError("All samples must be reviewed and ambiguity resolved")
        latest = self.latest()
        admitted = []
        for item in self.queue:
            record = latest[item["row_id"]]
            if record["decision"] not in {"APPROVE", "FIX_LABEL"}:
                continue
            frame = record["corrected_labels"] if record["decision"] == "FIX_LABEL" else item["frame"]
            self.validate(item, frame)
            admitted.append({**copy.deepcopy(item), "frame": frame, "human_review": record})
        payload = {"freeze_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                   "audit_sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(),
                   "counts": status["counts"], "admitted": admitted}
        raw = (json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
        digest = hashlib.sha256(raw).hexdigest()
        target = self.directory / ("audited_manifest_" + digest + ".json")
        if target.exists():
            if target.read_bytes() != raw:
                raise ValueError("Immutable manifest collision")
        else:
            with target.open("xb") as stream:
                stream.write(raw)
        return {"manifest": str(target), "sha256": digest, "admitted": len(admitted)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--admit", action="store_true")
    parser.add_argument("--import-precheck", type=Path)
    args = parser.parse_args()
    store = AuditStore()
    if args.import_precheck:
        print(json.dumps(store.import_precheck(args.import_precheck), indent=2))
        return
    if args.admit:
        print(json.dumps(store.admit(), indent=2))
        return
    token = secrets.token_urlsafe(32)
    review_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def respond(self, value, status=200, content_type="application/json"):
            raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            compressed = len(raw) > 16384 and "gzip" in self.headers.get("Accept-Encoding", "")
            if compressed:
                import gzip
                raw = gzip.compress(raw)
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if compressed:
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Vary", "Accept-Encoding")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(raw)
            self.wfile.flush()
            self.close_connection = True

        def allowed(self):
            return self.headers.get("Host") in {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}

        def do_GET(self):
            if not self.allowed():
                return self.respond({"error": "Invalid host"}, 403)
            try:
                if self.path.split("?", 1)[0] == "/":
                    raw = (ROOT / "scripts/unified_nlp_audit.html").read_text(encoding="utf-8")
                    raw += (ROOT / "scripts/multilingual_shadow_panel.html").read_text(encoding="utf-8")
                    self.respond(raw.replace("__TOKEN__", token).encode(), content_type="text/html")
                elif self.path == "/api/state":
                    self.respond({"status": store.status(), "queue": store.queue, "reviews": store.latest(), "precheck": store.precheck(),
                                  "schema": {"actions": ACTION_FAMILY, "speech": COARSE, "slots": sorted(SLOTS)}})
                elif self.path.split("?", 1)[0] == "/api/shadow":
                    from jarvis.core.language_shadow import ShadowStore
                    from urllib.parse import parse_qs, urlsplit
                    offset = parse_qs(urlsplit(self.path).query).get('offset', ['0'])[0]
                    shadow = ShadowStore().state(offset=int(offset))
                    shadow["enabled"] = json.loads(CONFIG.read_text(encoding="utf-8")).get("MULTILINGUAL_NLP_SHADOW") is True
                    shadow["production_authoritative"] = True
                    shadow["production_nlp"] = "CURRENT_PRODUCTION — existing router"
                    shadow["candidate_nlp"] = "V2 multilingual E5-small + separate shadow decoder"
                    shadow["language_status"] = {lang: "SHADOW / NOT ACCEPTED" for lang in
                        ("ENGLISH", "TANGLISH", "TAMIL", "MIXED", "MIXED_TAMIL_ENGLISH", "VOICE_ASR")}
                    shadow["real_metrics"] = {key: None for key in ("action_accuracy", "domain_accuracy", "canonical_slot_f1",
                        "recipient", "sender", "reference_typing", "correction_reconstruction", "negation_precision",
                        "negation_recall", "negation_f1", "speech_act", "capability_recall_at_1", "capability_recall_at_3",
                        "capability_recall_at_5", "capability_recall_at_10")}
                    development = ROOT / "data/nlp_shadow/development/decoder_DEV.json"
                    if development.exists():
                        metrics = json.loads(development.read_text(encoding="utf-8"))
                        shadow["DEV_ONLY_PROVISIONAL"] = {"metrics": metrics["after"], "negation": metrics["negation_after"]}
                    self.respond(shadow)
                else:
                    self.respond({"error": "Not found"}, 404)
            except (ValueError, KeyError, TypeError) as exc:
                self.respond({"error": str(exc)}, 409)

        def do_POST(self):
            if not self.allowed() or self.headers.get("X-Audit-Token") != token or self.path not in {"/api/review", "/api/shadow/review"}:
                return self.respond({"error": "Forbidden"}, 403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 100000:
                    raise ValueError("Invalid request size")
                payload = json.loads(self.rfile.read(length))
                if self.path == "/api/shadow/review":
                    from jarvis.core.language_shadow import ShadowStore
                    ShadowStore().review(payload["case_id"], payload["decision"], payload["reviewer"])
                    return self.respond({"saved": True})
                with review_lock:
                    result = store.save(payload)
                self.respond(result)
            except (ValueError, KeyError, TypeError) as exc:
                self.respond({"error": str(exc)}, 400)

    print(f"NLP Intelligence audit: http://127.0.0.1:{args.port} (production unchanged)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
