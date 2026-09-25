"""In-memory Fake WhatsApp Transport for testing and offline simulation."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage, WhatsAppBridgeStatus


class FakeWhatsAppTransport:
    """
    Simulates the Baileys transport layer in memory.
    Enables thorough unit, integration, security, and regression testing without
    a real WhatsApp account or phone connection.
    """

    def __init__(self, on_incoming_callback: Optional[Callable[[NormalizedWhatsAppMessage], Any]] = None) -> None:
        self.on_incoming = on_incoming_callback
        self.sent_messages: List[Dict[str, Any]] = []
        self.status = WhatsAppBridgeStatus(state="CONNECTED", account="1234567890@s.whatsapp.net")
        self.is_connected = True
        self.message_counter = 0

    def set_incoming_callback(self, callback: Callable[[NormalizedWhatsAppMessage], Any]) -> None:
        self.on_incoming = callback

    async def send_text(self, to: str, text: str, quoted: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Simulates sending a text message via WhatsApp transport."""
        if not self.is_connected:
            raise ConnectionError("WhatsApp transport is disconnected")

        self.message_counter += 1
        msg_id = f"fake_msg_{int(time.time()*1000)}_{self.message_counter}"
        record = {
            "action": "send_text",
            "message_id": msg_id,
            "to": to,
            "text": text,
            "quoted": quoted,
            "timestamp": time.time(),
            "status": "SENT",
        }
        self.sent_messages.append(record)
        return {"message_id": msg_id, "status": "SENT", "timestamp": time.time()}

    async def send_media(
        self,
        to: str,
        file_path: str,
        mimetype: str,
        caption: str = "",
        is_voice_note: bool = False,
    ) -> Dict[str, Any]:
        """Simulates sending a media message via WhatsApp transport."""
        if not self.is_connected:
            raise ConnectionError("WhatsApp transport is disconnected")

        self.message_counter += 1
        msg_id = f"fake_media_{int(time.time()*1000)}_{self.message_counter}"
        record = {
            "action": "send_media",
            "message_id": msg_id,
            "to": to,
            "file_path": file_path,
            "mimetype": mimetype,
            "caption": caption,
            "is_voice_note": is_voice_note,
            "timestamp": time.time(),
            "status": "SENT",
        }
        self.sent_messages.append(record)
        return {"message_id": msg_id, "status": "SENT", "timestamp": time.time()}

    async def simulate_incoming(self, message: NormalizedWhatsAppMessage) -> Any:
        """Simulates reception of an incoming message from the transport."""
        if not self.is_connected:
            return None
        if self.on_incoming:
            if asyncio.iscoroutinefunction(self.on_incoming):
                return await self.on_incoming(message)
            return self.on_incoming(message)
        return None

    def disconnect(self) -> None:
        self.is_connected = False
        self.status.state = "DISCONNECTED"

    def reconnect(self) -> None:
        self.is_connected = True
        self.status.state = "CONNECTED"

    def clear(self) -> None:
        self.sent_messages.clear()
        self.message_counter = 0
