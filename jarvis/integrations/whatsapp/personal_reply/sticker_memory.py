"""Local owner-sticker index. Selection produces candidates, never sends media."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import numpy as np

from jarvis.integrations.whatsapp.personal_reply.example_index import embed
from jarvis.integrations.whatsapp.personal_reply.models import Authorship
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


class StickerMemory:
    def __init__(self, store: PersonalReplyStore) -> None:
        self.store = store

    def index_owner_send(self, *, message_id: str, contact_id: str, media_path: str,
                         preceding_context: str, conversation_mode: str = "CASUAL",
                         provenance: Authorship = Authorship.UNKNOWN,
                         provenance_confidence: float = 0.0,
                         mime_type: str = "image/webp", sent_at: float | None = None) -> str:
        if provenance not in (Authorship.USER_TYPED, Authorship.USER_EDITED_AI_DRAFT) and not (
            provenance == Authorship.LEGACY_OWNER_LIKELY and provenance_confidence >= 0.45
        ):
            raise ValueError("Sticker needs verified or plausible legacy owner provenance")
        if not message_id or not contact_id or not self.store_contact_is_direct(contact_id):
            raise ValueError("A unique message and direct contact are required")
        path = Path(media_path).resolve(strict=True)
        if not path.is_file() or path.stat().st_size > 5_000_000 or path.stat().st_size == 0:
            raise ValueError("Sticker file must be nonempty and at most 5 MB")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        vector = embed([preceding_context or ""])[0].astype(np.float16).tobytes()
        now = time.time()
        used_at = sent_at if sent_at is not None else now
        with self.store._lock, self.store._conn() as conn:
            conn.execute("INSERT OR IGNORE INTO wa_pr_stickers "
                         "(sticker_hash,media_ref_enc,mime_type,first_seen) VALUES (?,?,?,?)",
                         (digest, self.store.box.encrypt(str(path)), mime_type, now))
            conn.execute("INSERT OR IGNORE INTO wa_pr_sticker_usage "
                         "(message_id,sticker_hash,contact_id,context_enc,context_vector,conversation_mode,provenance,used_at,provenance_confidence) "
                         "VALUES (?,?,?,?,?,?,?,?,?)", (message_id, digest, contact_id,
                         self.store.box.encrypt(preceding_context[:2000]), vector, conversation_mode,
                         provenance.value, used_at, provenance_confidence))
            conn.execute("UPDATE wa_pr_stickers SET last_used=max(coalesce(last_used,0),?) WHERE sticker_hash=?",
                         (used_at, digest))
        return digest

    @staticmethod
    def store_contact_is_direct(contact_id: str) -> bool:
        from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
        return WhatsAppInbox.is_direct_chat(contact_id)

    def candidates(self, contact_id: str, context: str, conversation_mode: str,
                   limit: int = 3, cooldown_s: float = 3600) -> list[dict]:
        """Return scoped, previously owner-sent stickers; never auto-select a weak match."""
        if not self.store_contact_is_direct(contact_id) or not context.strip():
            return []
        query = embed([context])[0]
        now = time.time()
        with self.store._conn() as conn:
            rows = conn.execute("SELECT u.sticker_hash,u.context_vector,u.conversation_mode,u.used_at,"
                                "s.media_ref_enc,s.mime_type,s.last_used,u.provenance,u.provenance_confidence FROM wa_pr_sticker_usage u "
                                "JOIN wa_pr_stickers s USING(sticker_hash) "
                                "WHERE u.contact_id=? AND u.provenance IN ('USER_TYPED','USER_EDITED_AI_DRAFT','LEGACY_OWNER_LIKELY') "
                                "ORDER BY u.used_at DESC LIMIT 500", (contact_id,)).fetchall()
        ranked: dict[str, dict] = {}
        for row in rows:
            if row["last_used"] and now - row["last_used"] < cooldown_s:
                continue
            vector = np.frombuffer(row["context_vector"], dtype=np.float16).astype(np.float32)
            if len(vector) != len(query):
                continue
            score = float(vector @ query) + (0.08 if row["conversation_mode"] == conversation_mode else 0)
            if row['provenance'] == Authorship.LEGACY_OWNER_LIKELY.value:
                score -= 0.2 + 0.1 * (1 - row['provenance_confidence'])
            if score < 0.35:
                continue
            old = ranked.get(row["sticker_hash"])
            if old is None or score > old["score"]:
                ranked[row["sticker_hash"]] = {"sticker_hash": row["sticker_hash"],
                                               "media_path": self.store.box.decrypt(row["media_ref_enc"]),
                                               "mime_type": row["mime_type"], "score": round(score, 3)}
        return sorted(ranked.values(), key=lambda item: item["score"], reverse=True)[:max(0, min(limit, 8))]

    def record_actual_use(self, sticker_hash: str) -> None:
        with self.store._lock, self.store._conn() as conn:
            conn.execute("UPDATE wa_pr_stickers SET last_used=? WHERE sticker_hash=?", (time.time(), sticker_hash))
