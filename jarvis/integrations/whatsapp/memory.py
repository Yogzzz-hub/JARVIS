"""WhatsApp chat memory: each conversation is kept as a searchable document in the knowledge base.

This lets the owner ask JARVIS things like "what did Rahul say about the trip?" or "when is Priya's
exam?" and get answers grounded in their own chats. Chats are indexed under a dedicated scope
(``scope:whatsapp_history``) that only the owner's local assistant searches; replies written to
other people never see it.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("jarvis.integrations.whatsapp.memory")

WHATSAPP_SCOPE = "scope:whatsapp_history"
COLLECTION = "WhatsApp chats"


class WhatsAppMemory:
    def __init__(self, engine: Any, inbox: Any, owner_name: str = "Me", debounce_s: float = 20.0):
        self.engine = engine
        self.inbox = inbox
        self.owner_name = owner_name or "Me"
        self.debounce_s = debounce_s
        self._pending: dict[str, asyncio.Task] = {}
        self._collection_id: Optional[str] = None

    def _collection(self) -> str:
        if self._collection_id is None:
            self._collection_id = self.engine.get_or_create_collection(COLLECTION).collection_id
        return self._collection_id

    def transcript(self, chat_id: str, limit: int = 120) -> tuple[str, str]:
        msgs = self.inbox.get_chat_history(chat_id, limit=limit)
        if not msgs:
            return "", ""
        is_group = not self.inbox.is_direct_chat(chat_id)
        others = [m.sender_display_name for m in msgs if not m.is_from_me and m.sender_display_name]
        name = (others[-1] if others else chat_id.split("@")[0]) if not is_group else f"group {chat_id.split('@')[0]}"
        title = f"WhatsApp {'group chat' if is_group else 'chat with ' + name}"
        lines = [f"# {title}"]
        day = ""
        for m in msgs:
            if not m.text:
                continue
            ts = datetime.fromtimestamp(m.timestamp)
            if ts.strftime("%Y-%m-%d") != day:
                day = ts.strftime("%Y-%m-%d")
                lines.append(f"\n## {ts.strftime('%A %d %B %Y')}")
            who = self.owner_name if m.is_from_me else (m.sender_display_name or "Contact")
            lines.append(f"[{ts.strftime('%H:%M')}] {who}: {m.text[:600]}")
        return title, "\n".join(lines)

    def index_chat(self, chat_id: str) -> int:
        title, text = self.transcript(chat_id)
        if not text:
            return 0
        return self.engine.index_document_text(
            self._collection(),
            f"{title} [{chat_id}]",
            text,
            owner_scope=WHATSAPP_SCOPE,
            privacy_scope=WHATSAPP_SCOPE,
            source_type="WHATSAPP_CONVERSATIONS",
        )

    def index_recent(self, days: float = 30.0, max_chats: int = 200) -> int:
        """Index every chat active in the last ``days`` (run once at startup, in a worker thread)."""
        cutoff = time.time() - days * 86400
        chats = []
        try:
            for m in self.inbox.get_recent(limit=5000):
                if m.timestamp >= cutoff and m.chat_id not in chats:
                    chats.append(m.chat_id)
                if len(chats) >= max_chats:
                    break
        except Exception as exc:
            logger.debug("Chat listing failed: %s", exc)
        total = 0
        for chat_id in chats:
            try:
                total += self.index_chat(chat_id)
            except Exception as exc:
                logger.debug("Indexing chat %s failed: %s", chat_id, exc)
        return total

    def schedule(self, chat_id: str, on_done: Any = None) -> None:
        """Re-index a chat shortly after new messages (bursts are coalesced)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self.index_chat(chat_id)
            return
        task = self._pending.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

        async def _later():
            try:
                await asyncio.sleep(self.debounce_s)
                await asyncio.to_thread(self.index_chat, chat_id)
                if on_done:
                    on_done()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug("Chat re-index failed: %s", exc)
            finally:
                self._pending.pop(chat_id, None)

        self._pending[chat_id] = loop.create_task(_later())
