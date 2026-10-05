"""Conservative, rebuildable attribution of old WhatsApp ``fromMe`` rows.

Only metadata is written as evidence. Account direction is not proof of authorship.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import os
from dataclasses import dataclass
from pathlib import Path

from jarvis.integrations.whatsapp.personal_reply.models import Authorship

_TEST_TEXT = re.compile(r"^JARVIS (?:TRACE|RUN [AB]|LIVE|FRESH LATENCY|RESTART CHECK|outgoing acceptance|send test)\b", re.I)
_BOT_TEXT = re.compile(r"^(?:JARVIS:|\[JARVIS\]|This is an automated message|Auto.reply:)", re.I)
_DIRECT = ("@lid", "@s.whatsapp.net")


def _weight(name: str, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(os.getenv('JARVIS_STYLE_WEIGHT_' + name, default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class ProvenanceDecision:
    provenance: Authorship
    confidence: float
    reasons: tuple[str, ...]


def evidence_weight(provenance: Authorship, confidence: float = 0.0) -> float:
    if provenance in (Authorship.USER_TYPED, Authorship.VERIFIED_MANUAL_OWNER_SEND):
        return _weight('MANUAL', 1.0)
    if provenance == Authorship.USER_EDITED_AI_DRAFT:
        return _weight('EDITED', 0.9)
    if provenance == Authorship.USER_APPROVED_AI_DRAFT:
        return _weight('APPROVED', 0.6)
    if provenance == Authorship.VERIFIED_LEGACY_OWNER:
        return _weight('VERIFIED_LEGACY', 0.85)
    if provenance == Authorship.LEGACY_OWNER_LIKELY:
        return round(_weight('LEGACY', 0.45) * max(0.0, min(1.0, confidence)), 4)
    return 0.0


def _ids_in(value: object) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"message_id", "sent_message_id", "provider_message_id"} and isinstance(item, str):
                ids.add(item)
            else:
                ids.update(_ids_in(item))
    elif isinstance(value, list):
        for item in value:
            ids.update(_ids_in(item))
    return ids


class LegacyProvenanceResolver:
    def __init__(self, inbox_path: Path, store_path: Path) -> None:
        self.inbox_path = Path(inbox_path)
        self.store_path = Path(store_path)
        self.generated_ids: set[str] = set()
        self.generated_hashes: dict[tuple[str, str], list[float]] = {}
        self.first_send_at: float | None = None
        self.unresolved_send_times: list[float] = []
        with sqlite3.connect(self.store_path) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='action_ledger'").fetchone():
                for tool, created, status, ack, verification in db.execute(
                    "SELECT tool,created_at,status,provider_ack_json,verification_json FROM action_ledger "
                    "WHERE lower(tool) LIKE '%whatsapp%' AND (lower(tool) LIKE '%send%' OR lower(tool) LIKE '%reply%')"
                ):
                    try:
                        from datetime import datetime, timezone
                        parsed = datetime.fromisoformat(created.replace('Z', '+00:00')) if created else None
                        ts = (parsed.replace(tzinfo=timezone.utc) if parsed and parsed.tzinfo is None else parsed).timestamp() if parsed else None
                        if ts is not None:
                            self.first_send_at = min(self.first_send_at, ts) if self.first_send_at else ts
                            if status in ('STARTED','UNCERTAIN','EXTERNALLY_ACKNOWLEDGED') and not ack:
                                self.unresolved_send_times.append(ts)
                    except (ValueError, AttributeError):
                        pass
                    for blob in (ack, verification):
                        try:
                            self.generated_ids.update(_ids_in(json.loads(blob or '{}')))
                        except (ValueError, TypeError):
                            pass
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='wa_pr_replies'").fetchone():
                self.generated_ids.update(r[0] for r in db.execute(
                    "SELECT sent_message_id FROM wa_pr_replies WHERE sent_message_id IS NOT NULL AND sent_message_id != ''"))
        with sqlite3.connect(self.inbox_path) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='wa_generated_messages'").fetchone():
                for mid, thread, digest, created in db.execute(
                    "SELECT message_id,thread_id,content_hash,created_at FROM wa_generated_messages"):
                    self.generated_ids.add(mid)
                    self.generated_hashes.setdefault((thread, digest), []).append(float(created or 0))
                    if created:
                        self.first_send_at = min(self.first_send_at, float(created)) if self.first_send_at else float(created)

    @staticmethod
    def metadata(payload: str | None) -> dict:
        try:
            obj = json.loads(payload or '{}')
            return obj if isinstance(obj, dict) else {}
        except (ValueError, TypeError):
            return {}

    def classify(self, *, message_id: str, chat_id: str, timestamp: float, message_type: str,
                 text: str, from_me: bool, payload: str | None = None) -> ProvenanceDecision:
        if not from_me:
            return ProvenanceDecision(Authorship.UNKNOWN, 0, ('contact_message',))
        reasons = ['fromMe_account_direction']
        if message_id in self.generated_ids:
            return ProvenanceDecision(Authorship.AUTO_GENERATED, 1, tuple(reasons + ['jarvis_message_id_match']))
        if chat_id.startswith('1234567890@'):
            return ProvenanceDecision(Authorship.UNKNOWN, 0, tuple(reasons + ['synthetic_test_contact']))
        if message_type not in {'text', 'sticker'} or not chat_id.endswith(_DIRECT):
            return ProvenanceDecision(Authorship.UNKNOWN, 0, tuple(reasons + ['non_style_type_or_non_direct_chat']))
        event = self.metadata(payload)
        meta = event.get('metadata') if isinstance(event.get('metadata'), dict) else {}
        forwarding = any(meta.get(k) for k in ('is_forwarded', 'forwarded', 'forwardingScore', 'forwarding_score'))
        forwarding = forwarding or any(event.get(k) for k in ('is_forwarded', 'forwarded', 'forwardingScore'))
        if forwarding:
            return ProvenanceDecision(Authorship.UNKNOWN, 0, tuple(reasons + ['forwarding_metadata']))
        digest = hashlib.sha256(text.strip().encode()).hexdigest() if text else ''
        hash_match = any(abs(timestamp - created) <= 120 for created in self.generated_hashes.get((chat_id, digest), []))
        if text and (hash_match or _TEST_TEXT.match(text) or _BOT_TEXT.match(text)):
            return ProvenanceDecision(Authorship.AUTO_GENERATED, 0.9, tuple(reasons + ['generated_hash_or_test_template']))
        if message_type == 'sticker':
            return ProvenanceDecision(Authorship.LEGACY_OWNER_LIKELY, 0.45,
                                      tuple(reasons + ['direct_sticker', 'forwarding_metadata_unavailable']))
        if not text or text.casefold().startswith(('waiting for this message', 'this message was deleted')):
            return ProvenanceDecision(Authorship.UNKNOWN, 0, tuple(reasons + ['empty_or_placeholder']))
        if self.first_send_at is not None and timestamp < self.first_send_at:
            return ProvenanceDecision(Authorship.LEGACY_OWNER_LIKELY, 0.78,
                                      tuple(reasons + ['predates_first_recorded_jarvis_send', 'no_automation_id_match',
                                                       'forwarding_metadata_unavailable']))
        # Current inbox metadata lacks forwarding flags. Keep this bounded well
        # below verified authorship; exact same-day ledger timing alone proves nothing.
        return ProvenanceDecision(Authorship.LEGACY_OWNER_LIKELY, 0.55,
                                  tuple(reasons + ['no_automation_id_match', 'jarvis_send_capability_existed_or_unknown',
                                                   'forwarding_metadata_unavailable']))

    def classify_live(self, *, message_id: str, chat_id: str, timestamp: float, message_type: str,
                      text: str, payload: str | None = None, source_device_proof: str = '') -> ProvenanceDecision:
        """Only explicit trusted origin proof can promote a phone echo to manual evidence.

        A missing ledger match cannot prove human authorship while an outgoing
        request may be in flight or unacknowledged.
        """
        base = self.classify(message_id=message_id, chat_id=chat_id, timestamp=timestamp,
                             message_type=message_type, text=text, from_me=True, payload=payload)
        if base.provenance in (Authorship.AUTO_GENERATED, Authorship.UNKNOWN):
            return base
        if any(abs(timestamp - ts) <= 600 for ts in self.unresolved_send_times):
            return ProvenanceDecision(Authorship.UNKNOWN, 0,
                                      ('unresolved_jarvis_send_window', 'manual_origin_not_proven'))
        if source_device_proof != 'OWNER_ATTESTED_MESSAGE_ID':
            return ProvenanceDecision(Authorship.UNKNOWN, 0,
                                      ('fromMe_account_direction', 'manual_origin_not_proven'))
        return ProvenanceDecision(Authorship.VERIFIED_MANUAL_OWNER_SEND, 1,
                                  ('owner_attested_exact_message_id', 'no_jarvis_id_or_hash_match'))
