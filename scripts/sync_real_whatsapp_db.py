"""Inspect/import a bridge snapshot without manufacturing synchronization evidence.

Dry-run by default. Historical badge import never sets connector READY, clears
unlisted chats, or marks messages read based on age.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from jarvis.integrations.whatsapp.inbox import WhatsAppInbox


def import_snapshot(db_path: Path, snapshot_path: Path, *, apply: bool = False) -> dict:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("chats"), list):
        raise ValueError("Expected a chat snapshot object")
    chats = []
    for c in payload["chats"]:
        if not isinstance(c, dict) or not isinstance(c.get("jid"), str):
            raise ValueError("Malformed chat record")
        chats.append({"chat_id": c["jid"], "unread": max(0, int(c.get("unread") or 0)),
                      "name": str(c.get("name") or ""), "last_ts": float(c.get("lastTs") or 0),
                      "last_text": str(c.get("lastText") or ""),
                      "last_sender": str(c.get("lastSender") or ""),
                      "last_from_me": bool(c.get("lastFromMe"))})
    if apply:
        if not db_path.is_file():
            raise ValueError("An existing inbox database is required")
        inbox = WhatsAppInbox(db_path=db_path)
        # Historical snapshots cannot assert current-session completeness.
        inbox.update_chats(chats, full=True, synced=False)
    return {"records": len(chats), "applied": apply, "provenance": "LEGACY"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--db", type=Path, default=Path("jarvis/data/whatsapp_inbox.db"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(import_snapshot(args.db, args.snapshot, apply=args.apply)))


if __name__ == "__main__":
    main()
