"""Observe a user-sent marker through the real inbox and CommandService. Never sends or inserts messages."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
BASELINE = ROOT / "reports/whatsapp_acceptance_baseline.json"


def diagnostics():
    with urllib.request.urlopen("http://127.0.0.1:8765/dashboard/whatsapp/diagnostics", timeout=10) as response:
        return json.load(response)


def command(text):
    request = urllib.request.Request("http://127.0.0.1:8765/command",
        data=json.dumps({"text": text}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["baseline", "check"])
    parser.add_argument("--marker", default="JARVIS CHECK 1002")
    args = parser.parse_args()
    if args.mode == "baseline":
        d = diagnostics()
        baseline = {"started": time.time(), "marker": args.marker,
                    "stored": d["stored_inbound_messages"], "generation": d["sync_generation"]}
        BASELINE.write_text(json.dumps(baseline), encoding="utf-8")
        print(json.dumps(baseline))
        return
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    row = None
    for _ in range(7):
        with sqlite3.connect(ROOT / "jarvis/data/whatsapp_inbox.db") as conn:
            row = conn.execute("SELECT message_id, chat_id, timestamp, is_read FROM whatsapp_messages "
                "WHERE is_from_me=0 AND text=? AND timestamp>=? ORDER BY timestamp DESC LIMIT 1",
                (baseline["marker"], baseline["started"] - 5)).fetchone()
        if row:
            break
        time.sleep(5)
    d = diagnostics()
    h = d.get("bridge_runtime_diagnostics", {}).get("event_health", {})
    result = {"marker_received": bool(row), "stored_before": baseline["stored"],
              "stored_after": d["stored_inbound_messages"], "generation": d["sync_generation"],
              "same_generation": baseline["generation"] == d["sync_generation"],
              "overall_state": d.get("overall_state"), "buffer_active": h.get("buffer_active"),
              "pending_notifications": h.get("received_pending_notifications"), "commands": []}
    if row:
        result["message_hash"] = hashlib.sha256(row[0].encode()).hexdigest()[:16]
        result["jid_type"] = "LID" if row[1].endswith("@lid") else "PN" if row[1].endswith("@s.whatsapp.net") else "other"
        result["stored_unread"] = not row[3]
        for text in ("who messaged me", "how many unread personal messages can you see", "summarize my whatsapp"):
            output = command(text)
            result["commands"].append({"command": text, "state": output["state"],
                "marker_in_response": baseline["marker"] in json.dumps(output)})
    destination = ROOT / "reports/whatsapp_acceptance_result.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
