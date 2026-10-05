"""One explicitly authorised WhatsApp send through the existing bridge and ActionLedger.

The bridge must be running read only with an exact one-shot recipient, text and
request ID already configured. This script sends one WebSocket request and never
retries an uncertain result. No general sending or auto-reply is enabled.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import time
from uuid import UUID

import websockets

from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
from jarvis.security.ledger.ledger import ActionLedger
from jarvis.security.ledger.models import LedgerState
from jarvis.tools.base import IdempotencyClass, RiskLevel


def source_thread(inbox: WhatsAppInbox, incoming_id: str) -> str:
    with sqlite3.connect(inbox.db_path) as conn:
        row = conn.execute("SELECT chat_id,is_from_me FROM whatsapp_messages WHERE message_id=?", (incoming_id,)).fetchone()
    if not row or row[1] or not inbox.is_direct_chat(row[0]):
        raise ValueError("The selected incoming message is not a stored direct-chat message")
    return row[0]


def fingerprint(incoming_id: str, message: str) -> str:
    return "wa_one_shot:" + hashlib.sha256((incoming_id + "\0" + message).encode()).hexdigest()


async def send_once(request_id: str, to: str, message: str) -> dict:
    submitted = False
    try:
        async with websockets.connect("ws://127.0.0.1:8768/commands", open_timeout=4) as ws:
            await ws.send(json.dumps({"id": request_id, "action": "send_text", "payload": {"to": to, "text": message}}))
            submitted = True
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                response = json.loads(await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.monotonic())))
                if response.get("id") == request_id:
                    return response
    except Exception as exc:
        return {"success": False, "status": "UNCERTAIN" if submitted else "FAILED", "error": type(exc).__name__}
    return {"success": False, "status": "UNCERTAIN", "error": "RESPONSE_TIMEOUT"}


def run(incoming_id: str, message: str, request_id: str) -> dict:
    if os.environ.get("JARVIS_WHATSAPP_ONE_SHOT_AUTHORIZED") != "1":
        raise ValueError("Explicit one-shot authorization flag is required")
    UUID(request_id)  # requires a fresh, nontrivial request identity
    inbox = WhatsAppInbox.get_default()
    to = source_thread(inbox, incoming_id)
    if (os.environ.get("JARVIS_WHATSAPP_ONE_SHOT_TO") != to or
            os.environ.get("JARVIS_WHATSAPP_ONE_SHOT_TEXT") != message or
            os.environ.get("JARVIS_WHATSAPP_ONE_SHOT_REQUEST_ID") != request_id):
        raise ValueError("The bridge one-shot configuration does not match this exact send")

    ledger = ActionLedger()
    fp = fingerprint(incoming_id, message)
    with ledger._get_conn() as conn:
        prior = conn.execute("SELECT status FROM action_ledger WHERE fingerprint=? LIMIT 1", (fp,)).fetchone()
    if prior or ledger.get_entry_by_id(request_id):
        raise ValueError("This one-shot action is already recorded; no resend is allowed")
    args_hash = hashlib.sha256(json.dumps({"to": to, "text": message}, sort_keys=True).encode()).hexdigest()
    risk = RiskLevel.EXTERNAL_EFFECT
    ledger.prepare_action(action_id=request_id, fingerprint=fp, request_id=request_id,
                          graph_id="whatsapp_live_acceptance", node_id="one_shot_send",
                          tool="send_whatsapp_message", risk=risk,
                          idempotency=IdempotencyClass.NON_IDEMPOTENT, args_hash=args_hash,
                          method="existing_baileys_bridge", target_references_json=json.dumps({"incoming_id": incoming_id}))
    if not ledger.start_action(request_id, fp, risk):
        raise RuntimeError("ActionLedger could not claim the one-shot send")
    response = asyncio.run(send_once(request_id, to, message))
    result = response.get("result") or {}
    message_id = result.get("message_id") if isinstance(result, dict) else None
    if response.get("success") and result.get("status") == "SENT" and message_id:
        ledger.record_external_ack(request_id, fp, risk, provider_ack_json=json.dumps({"message_id": message_id}))
        deadline = time.monotonic() + 10
        persisted = False
        while time.monotonic() < deadline:
            with sqlite3.connect(inbox.db_path) as conn:
                row = conn.execute("SELECT chat_id,is_from_me,text FROM whatsapp_messages WHERE message_id=?", (message_id,)).fetchone()
            if row and row[0] == to and row[1] and row[2] == message:
                persisted = True
                break
            time.sleep(0.25)
        if persisted:
            # A local outgoing row proves ingestion, not delivery to the other
            # phone. Keep the ledger at its acknowledged state until the owner
            # confirms receipt on that device.
            with ledger._get_conn() as conn:
                conn.execute("UPDATE action_ledger SET verification_json=? WHERE action_id=?",
                             (json.dumps({"message_id": message_id, "local_outgoing_persisted": True,
                                          "phone_receipt": "PENDING"}), request_id))
            return {"status": "PERSISTED_LOCAL", "message_id": message_id,
                    "ledger": LedgerState.EXTERNALLY_ACKNOWLEDGED.value, "phone_receipt": "PENDING"}
    # Once submitted, any absent receipt or persistence is uncertain. Never retry automatically.
    # The command was submitted to the local bridge. Even an error response can
    # arrive after Baileys attempted the send, so never classify it as retryable.
    uncertain = True
    state = LedgerState.UNCERTAIN if uncertain else LedgerState.FAILED_SAFE_TO_RETRY
    ledger.record_outcome(request_id, fp, risk, state,
                          verification_json=json.dumps({"message_id": message_id, "local_outgoing_persisted": False}),
                          error_class=response.get("error", "SEND_NOT_VERIFIED"))
    return {"status": state.value, "message_id": message_id, "ledger": state.value, "phone_receipt": "PENDING"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--incoming-id", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--request-id", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.incoming_id, args.message, args.request_id)))
