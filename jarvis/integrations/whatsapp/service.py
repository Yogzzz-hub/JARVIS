"""Live WhatsApp Integration Service and WebSocket Client.
Connects JARVIS Python backend to the local Baileys Node.js transport bridge over WebSocket.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import tomllib
from typing import Any, Callable, Dict, Optional, Set
from uuid import uuid4

import websockets
from websockets.exceptions import ConnectionClosed

from jarvis.config import ROOT
from jarvis.core.commands.service import CommandService
from jarvis.core.events.bus import EventBus
from jarvis.core.knowledge.service import KnowledgeService
from jarvis.integrations.whatsapp.gateway import WhatsAppChannelGateway
from jarvis.integrations.whatsapp.media_pipeline import WhatsAppMediaPipeline
from jarvis.integrations.whatsapp.models import (
    NormalizedWhatsAppMessage,
    WhatsAppBridgeStatus,
)
from jarvis.security.confirmation.manager import ConfirmationManager

logger = logging.getLogger("jarvis.integrations.whatsapp.service")


class BaileysWebSocketTransport:
    """Production WebSocket transport communicating with local Baileys bridge."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8768,
        on_incoming: Optional[Callable[[NormalizedWhatsAppMessage], Any]] = None,
        on_status: Optional[Callable[[Dict[str, Any]], Any]] = None,
        on_qr: Optional[Callable[[str], Any]] = None,
        on_pairing_code: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.ws_url = f"ws://{host}:{port}"
        self.on_incoming = on_incoming
        self.on_status = on_status
        self.on_qr = on_qr
        self.on_pairing_code = on_pairing_code

        self._ws: Any = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self.status = WhatsAppBridgeStatus()
        self.is_connected = False

    async def start(self) -> None:
        """Start the background WebSocket connection loop."""
        self._loop = asyncio.get_running_loop()
        self._running = True
        self._loop_task = asyncio.create_task(self._connect_loop())

    async def stop(self) -> None:
        """Stop the background connection loop and close connection."""
        self._running = False
        if hasattr(self, "_loop_task") and self._loop_task:
            self._loop_task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        self.is_connected = False
        self.status.state = "DISCONNECTED"

    async def _connect_loop(self) -> None:
        backoff = 2.0
        while self._running:
            try:
                logger.info("Connecting to WhatsApp bridge at %s...", self.ws_url)
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    self.is_connected = True
                    backoff = 2.0
                    logger.info("Connected to WhatsApp transport bridge at %s", self.ws_url)

                    # Request status or connect
                    await self._send({"id": "init_connect", "action": "connect"})

                    async for raw_msg in ws:
                        try:
                            data = json.loads(raw_msg)
                            await self._handle_event(data)
                        except Exception as e:
                            logger.error("Error processing message from WhatsApp bridge: %s", e)

            except (ConnectionClosed, OSError) as exc:
                self.is_connected = False
                self._ws = None
                self.status.state = "DISCONNECTED"
                if self._running:
                    logger.debug("WhatsApp bridge unavailable (%s). Retrying in %.1fs...", exc, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 1.5, 15.0)
            except Exception as e:
                self.is_connected = False
                self._ws = None
                self.status.state = "DISCONNECTED"
                if self._running:
                    logger.error("Unexpected error in WhatsApp bridge connection: %s", e)
                    await asyncio.sleep(5.0)

    async def _handle_event(self, data: Dict[str, Any]) -> None:
        msg_type = data.get("type")
        action = data.get("action")
        req_id = data.get("id")

        # Response to a pending command
        if req_id and req_id in self._pending_requests:
            fut = self._pending_requests.pop(req_id)
            if not fut.done():
                fut.set_result(data)
            return

        if msg_type == "incoming_message":
            payload = data.get("payload", {})
            try:
                msg = NormalizedWhatsAppMessage(**payload)
                if self.on_incoming:
                    res = self.on_incoming(msg)
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
            except Exception as exc:
                logger.error("Failed to parse incoming WhatsApp message: %s", exc)

        elif msg_type == "status_update":
            payload = data.get("payload", {})
            st = payload.get("state", "DISCONNECTED")
            self.status.state = st
            if "qr" in payload and payload["qr"]:
                self.status.qr = payload["qr"]
            if self.on_status:
                self.on_status(payload)

        elif msg_type == "qr_code":
            qr = data.get("payload", {}).get("qr", "")
            self.status.qr = qr
            self.status.state = "PAIRING_REQUIRED"
            if self.on_qr:
                self.on_qr(qr)

        elif msg_type == "pairing_code":
            code = data.get("payload", {}).get("code", "")
            if self.on_pairing_code:
                self.on_pairing_code(code)

    async def _send(self, data: Dict[str, Any]) -> None:
        if self._ws and self.is_connected:
            await self._ws.send(json.dumps(data))

    async def _call(self, action: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 15.0) -> Dict[str, Any]:
        if not self.is_connected or not self._ws:
            return {"success": False, "error": "WhatsApp bridge not connected"}

        req_id = uuid4().hex
        fut = asyncio.get_running_loop().create_future()
        self._pending_requests[req_id] = fut

        await self._send({"id": req_id, "action": action, "payload": payload or {}})

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            return {"success": False, "error": "Request timed out"}

    async def send_text(self, to: str, text: str, quoted: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send outbound text message via WhatsApp bridge."""
        res = await self._call("send_text", {"to": to, "text": text, "quoted": quoted})
        return res

    async def send_media(
        self,
        to: str,
        file_path: str,
        mimetype: str,
        caption: str = "",
        is_voice_note: bool = False,
    ) -> Dict[str, Any]:
        """Send outbound media via WhatsApp bridge."""
        res = await self._call(
            "send_media",
            {
                "to": to,
                "file_path": file_path,
                "mimetype": mimetype,
                "caption": caption,
                "is_voice_note": is_voice_note,
            },
        )
        return res

    async def get_status(self) -> Dict[str, Any]:
        """Query real-time status from bridge."""
        res = await self._call("get_status")
        return res.get("result", {})


class WhatsAppIntegrationService:
    """
    High-level orchestrator for the WhatsApp Omnichannel subsystem.
    Loads configuration, sets up gateway and transport, and links with Jarvis core.
    """

    def __init__(
        self,
        command_service: CommandService,
        confirmation_manager: Optional[ConfirmationManager] = None,
        knowledge_service: Optional[KnowledgeService] = None,
        event_bus: Optional[EventBus] = None,
        config_path: Optional[Path] = None,
        whatsapp_ai: Any = None,
        announcer: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.command_service = command_service
        self.confirmation_manager = confirmation_manager
        self.knowledge_service = knowledge_service
        self.event_bus = event_bus

        # Load config from config/whatsapp.toml
        cfg_file = config_path or (ROOT.parent / "config/whatsapp.toml")
        self.config = {}
        if cfg_file.exists():
            try:
                with open(cfg_file, "rb") as f:
                    self.config = tomllib.load(f)
            except Exception as e:
                logger.warning("Could not load config/whatsapp.toml: %s", e)

        wa_cfg = self.config.get("whatsapp", {})
        self.enabled = wa_cfg.get("enabled", True)
        self.bridge_host = wa_cfg.get("bridge_host", "127.0.0.1")
        self.bridge_port = wa_cfg.get("bridge_port", 8768)
        self.mode = wa_cfg.get("mode", "DRAFT_ONLY")
        self.voice_reply_enabled = wa_cfg.get("voice_reply_enabled", False)
        self.owner_name = wa_cfg.get("owner_name", "Boss")
        self.ai_replies = bool(wa_cfg.get("ai_replies", True))
        self.announce_new_messages = bool(wa_cfg.get("announce_new_messages", True))

        owner_numbers = wa_cfg.get("owner", {}).get("phone_numbers", ["6381456199", "+916381456199"])
        self.owner_identities: Set[str] = set(owner_numbers)

        allowlist = self.config.get("whatsapp", {}).get("allowlist", {}).get("auto_reply_contacts", [])
        self.auto_reply_allowlist: Set[str] = set(allowlist)

        # Setup transport
        self.transport = BaileysWebSocketTransport(
            host=self.bridge_host,
            port=self.bridge_port,
            on_incoming=self._on_incoming_message,
            on_status=self._on_bridge_status,
            on_qr=self._on_qr_code,
            on_pairing_code=self._on_pairing_code,
        )

        # Multimodal media pipeline
        self.media_pipeline = WhatsAppMediaPipeline(
            stt_engine=getattr(command_service, "stt", None),
            knowledge_engine=getattr(self.knowledge_service, "knowledge_engine", None) if self.knowledge_service else None,
        )

        # Omnichannel Gateway
        self.gateway = WhatsAppChannelGateway(
            command_service=self.command_service,
            transport=self.transport,
            confirmation_manager=self.confirmation_manager,
            media_pipeline=self.media_pipeline,
            knowledge_service=self.knowledge_service,
            owner_identities=self.owner_identities,
            mode=self.mode,
            auto_reply_allowlist=self.auto_reply_allowlist,
            voice_reply_enabled=self.voice_reply_enabled,
            whatsapp_ai=whatsapp_ai if self.ai_replies else None,
            announcer=announcer if self.announce_new_messages else None,
            event_bus=event_bus,
        )

    async def start(self) -> None:
        """Start the WhatsApp integration."""
        if not self.enabled:
            logger.info("WhatsApp omnichannel integration is disabled by config.")
            return
        logger.info("Starting WhatsApp omnichannel service (Owner: %s)...", self.owner_identities)
        await self.transport.start()

    async def stop(self) -> None:
        """Stop the WhatsApp integration."""
        logger.info("Stopping WhatsApp omnichannel service...")
        await self.transport.stop()

    async def _on_incoming_message(self, message: NormalizedWhatsAppMessage) -> None:
        """Handle incoming message routed from transport."""
        logger.info("Received WhatsApp message from %s (%s)", message.sender_display_name, message.sender_id)
        if self.event_bus:
            self.event_bus.emit(
                "whatsapp.incoming",
                "",
                sender=message.sender_display_name,
                sender_id=message.sender_id,
                text=message.text,
                type=message.type,
            )
        await self.gateway.handle_incoming(message)

    def _on_bridge_status(self, status_payload: Dict[str, Any]) -> None:
        state = status_payload.get("state", "UNKNOWN")
        logger.info("WhatsApp Bridge status updated: %s", state)
        if self.event_bus:
            self.event_bus.emit("whatsapp.status", "", state=state, payload=status_payload)

    def _on_qr_code(self, qr: str) -> None:
        logger.info("WhatsApp Bridge generated pairing QR code.")
        if self.event_bus:
            self.event_bus.emit("whatsapp.qr", "", qr=qr)

    def _on_pairing_code(self, code: str) -> None:
        logger.info("WhatsApp Bridge generated pairing code: %s", code)
        if self.event_bus:
            self.event_bus.emit("whatsapp.pairing_code", "", code=code)
