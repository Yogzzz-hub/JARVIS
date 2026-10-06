"""Live WhatsApp Integration Service and WebSocket Client.
Connects JARVIS Python backend to the local Baileys Node.js transport bridge over WebSocket.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
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
from jarvis.integrations.whatsapp.incoming_trace import trace_generation, trace_incoming
from jarvis.security.confirmation.manager import ConfirmationManager

logger = logging.getLogger("jarvis.integrations.whatsapp.service")



def _vision_provider():
    """The owner's photos are read with JARVIS's vision model ([models] vision); off when [features] vision is off."""
    try:
        from jarvis.config import load
        if not load().features.vision:
            return None
        from jarvis.core.vision.providers.qwen3vl import Qwen3VLProvider
        return Qwen3VLProvider()
    except Exception:
        return None

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
        on_chat_state: Optional[Callable[[Dict[str, Any]], Any]] = None,
        read_only: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.ws_url = f"ws://{host}:{port}"
        self.on_incoming = on_incoming
        self.on_status = on_status
        self.on_qr = on_qr
        self.on_pairing_code = on_pairing_code
        self.on_chat_state = on_chat_state
        self.read_only = read_only
        self.intelligence = None

        self._ws: Any = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self.status = WhatsAppBridgeStatus()
        self.is_connected = False
        self._dispatch_workers = []

    async def start(self) -> None:
        """Start the background WebSocket connection loop."""
        self._loop = asyncio.get_running_loop()
        self._running = True
        if self.intelligence is not None:
            self._dispatch_workers = [asyncio.create_task(self._dispatch_loop(), name=f"whatsapp-dispatch-{i}") for i in range(2)]
        self._loop_task = asyncio.create_task(self._connect_loop())

    async def stop(self) -> None:
        """Stop the background connection loop and close connection."""
        self._running = False
        for worker in self._dispatch_workers:
            worker.cancel()
        await asyncio.gather(*self._dispatch_workers, return_exceptions=True)
        self._dispatch_workers = []
        if hasattr(self, "_loop_task") and self._loop_task:
            self._loop_task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        self.is_connected = False
        self.status.state = "DISCONNECTED"
        if self.on_status:
            self.on_status({"state": "DISCONNECTED"})

    async def _dispatch_loop(self):
        while self._running:
            job = await asyncio.to_thread(self.intelligence.store.claim_dispatch)
            if job is None:
                await asyncio.sleep(0.25)
                continue
            try:
                message = NormalizedWhatsAppMessage(**json.loads(job["payload"]))
                # Old queued work remains searchable but cannot execute commands or
                # send delayed replies after a restart.
                if time.time() - job["created_at"] > 120:
                    message.history = True
                if self.on_incoming:
                    result = self.on_incoming(message)
                    if asyncio.iscoroutine(result):
                        await result
                await asyncio.to_thread(self.intelligence.store.finish_dispatch, job["message_id"])
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("WhatsApp dispatch held after failure")
                await asyncio.to_thread(self.intelligence.store.finish_dispatch, job["message_id"], type(exc).__name__)

    async def _connect_loop(self) -> None:
        backoff = 2.0
        while self._running:
            try:
                logger.info("Connecting to WhatsApp bridge at %s...", self.ws_url)
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    self.is_connected = True
                    if self.on_status:
                        self.on_status({"state": "CONNECTING"})
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
                if self.on_status:
                    self.on_status({"state": "DISCONNECTED"})
                if self._running:
                    logger.debug("WhatsApp bridge unavailable (%s). Retrying in %.1fs...", exc, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 1.5, 15.0)
            except Exception as e:
                self.is_connected = False
                self._ws = None
                self.status.state = "DISCONNECTED"
                if self.on_status:
                    self.on_status({"state": "DISCONNECTED"})
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
            token = trace_generation.set(str(data.get("generation") or ""))
            trace_incoming(stage="python_websocket_receive", event_type=msg_type,
                           message_id=payload.get("message_id"), chat_jid=payload.get("chat_id"),
                           from_me=payload.get("is_from_me"), message_type=payload.get("type"),
                           timestamp=payload.get("timestamp"), python_receive_result="RECEIVED")
            try:
                msg = NormalizedWhatsAppMessage(**payload)
                if self.intelligence is not None:
                    await asyncio.to_thread(self.intelligence.inbox.record_python_event)
                trace_incoming(stage="python_schema", event_type=msg_type, message_id=msg.message_id,
                               chat_jid=msg.chat_id, from_me=msg.is_from_me, message_type=msg.type,
                               timestamp=msg.timestamp, python_receive_result="SCHEMA_ACCEPTED")
                if self.intelligence is not None:
                    await asyncio.to_thread(self.intelligence.inbox.add_message, msg)
                    await asyncio.to_thread(self.intelligence.store.enqueue_dispatch, msg)
                    trace_incoming(stage="python_dispatch", event_type=msg_type, message_id=msg.message_id,
                                   chat_jid=msg.chat_id, python_receive_result="ENQUEUED")
                elif self.on_incoming:
                    res = self.on_incoming(msg)
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
            except Exception as exc:
                reason = type(exc).__name__
                if hasattr(exc, "errors"):
                    try:
                        reason += ":" + ",".join(
                            f"{'.'.join(map(str, error.get('loc', ())))}:{error.get('type', '')}"
                            for error in exc.errors()[:4])
                    except Exception:
                        pass
                trace_incoming(stage="python_receive_error", event_type=msg_type,
                               message_id=payload.get("message_id"), chat_jid=payload.get("chat_id"),
                               python_receive_result="REJECTED", reason=reason)
                logger.error("WhatsApp incoming message rejected: %s", reason)
            finally:
                trace_generation.reset(token)

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

        elif msg_type == "chat_state":
            # WhatsApp's unread badge per chat, as the phone shows it
            if self.on_chat_state:
                res = self.on_chat_state(data.get("payload") or {})
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)

    async def _send(self, data: Dict[str, Any]) -> None:
        if self._ws and self.is_connected:
            await self._ws.send(json.dumps(data))

    async def _call(self, action: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 15.0) -> Dict[str, Any]:
        if self.read_only and action in {"send_text", "send_media"}:
            return {"success": False, "error": "WhatsApp read-only mode blocks sending"}
        if not self.is_connected or not self._ws:
            return {"success": False, "error": "WhatsApp bridge not connected"}

        req_id = uuid4().hex
        if action in {"send_text", "send_media"} and self.intelligence is not None:
            self.intelligence.store.generated((payload or {}).get("to", ""), (payload or {}).get("text", (payload or {}).get("caption", "")), req_id)
        fut = asyncio.get_running_loop().create_future()
        self._pending_requests[req_id] = fut

        try:
            await self._send({"id": req_id, "action": action, "payload": payload or {}})
            response = await asyncio.wait_for(fut, timeout=timeout)
            if action in {"send_text", "send_media"} and self.intelligence is not None and response.get("success"):
                result = response.get("result") or {}
                if result.get("message_id"):
                    self.intelligence.store.generated(payload.get("to", ""), payload.get("text", payload.get("caption", "")), req_id, result["message_id"])
            return response
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            return {"success": False, "status": "UNCERTAIN" if action in {"send_text", "send_media"} else "FAILED",
                    "error": "Request timed out"}
        finally:
            self._pending_requests.pop(req_id, None)

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

    async def get_message(self, message_id: str, chat_id: str = "", download: bool = False) -> Optional[NormalizedWhatsAppMessage]:
        """Re-fetch a message by id (used to recover messages that arrived undecrypted)."""
        res = await self._call("get_message", {"message_id": message_id, "chat_id": chat_id, "download": download}, timeout=30.0 if download else 5.0)
        payload = res.get("result") if res.get("success") else None
        return NormalizedWhatsAppMessage(**payload) if payload else None

    async def get_chats(self) -> Dict[str, Any]:
        """WhatsApp's unread badge per chat from the bridge ({"synced", "full", "chats": [...]})."""
        res = await self._call("get_chats", timeout=5.0)
        return (res.get("result") or {}) if res.get("success") else {}

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
        self.read_only = os.environ.get("JARVIS_WHATSAPP_READ_ONLY") == "1"
        self.enabled = wa_cfg.get("enabled", True)
        self.bridge_host = wa_cfg.get("bridge_host", "127.0.0.1")
        self.bridge_port = wa_cfg.get("bridge_port", 8768)
        self.mode = "OFF" if self.read_only else wa_cfg.get("mode", "DRAFT_ONLY")
        self.voice_reply_enabled = wa_cfg.get("voice_reply_enabled", False)
        self.owner_name = wa_cfg.get("owner_name", "Boss")
        self.ai_replies = not self.read_only and bool(wa_cfg.get("ai_replies", True))
        self.announce_new_messages = not self.read_only and bool(wa_cfg.get("announce_new_messages", True))

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
            on_chat_state=self._on_chat_state,
            read_only=self.read_only,
        )

        # Multimodal media pipeline
        self.media_pipeline = WhatsAppMediaPipeline(
            stt_engine=getattr(command_service, "stt", None),
            vision_provider=_vision_provider(),
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

        # Contact-specific personal replies (style learning + time-boxed auto-reply grants; groups never).
        self.personal_reply = None
        self.draft_only_agent = None
        pr_cfg = wa_cfg.get("personal_reply", {})
        if not self.read_only and bool(pr_cfg.get("enabled", True)):
            try:
                from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent, set_personal_reply_agent
                from jarvis.integrations.whatsapp.personal_reply.auto_reply_policy import AutoReplyPolicy
                from jarvis.integrations.whatsapp.personal_reply.reply_generator import ReplyGenerator
                from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore
                from jarvis.security.ledger.ledger import ActionLedger
                from jarvis.security.policy.evaluator import PolicyEvaluator
                store = PersonalReplyStore()
                self.personal_reply = PersonalReplyAgent(
                    store=store, transport=self.transport, inbox=self.gateway.inbox,
                    generator=ReplyGenerator(client=getattr(whatsapp_ai, "_client", None)),
                    policy=AutoReplyPolicy(store, auto_reply_untrained=bool(pr_cfg.get("auto_reply_untrained_contacts", False)),
                                           max_hours=float(pr_cfg.get("max_auto_reply_hours", 12)),
                                           generated_auto_reply_enabled=bool(pr_cfg.get('generated_auto_reply_enabled', False))),
                    ledger=ActionLedger(), policy_evaluator=PolicyEvaluator(), event_bus=event_bus,
                    coalesce_s=float(pr_cfg.get("coalesce_seconds", 1.2)),
                    owner_names=[self.owner_name, *pr_cfg.get("export_names", [])],
                    notifier=announcer if self.announce_new_messages else None,
                )
                self.gateway.personal_reply = self.personal_reply
                set_personal_reply_agent(self.personal_reply)
            except Exception as exc:
                logger.warning("WhatsApp personal reply agent unavailable: %s", exc)

        # Chat memory: every conversation becomes searchable for the owner's questions.
        self.memory = None
        engine = getattr(self.knowledge_service, "knowledge_engine", None) if self.knowledge_service else None
        if engine is not None and bool(wa_cfg.get("remember_chats", True)):
            from jarvis.integrations.whatsapp.memory import WhatsAppMemory
            self.memory = WhatsAppMemory(engine, self.gateway.inbox, owner_name=self.owner_name)

    async def start(self) -> None:
        """Start the WhatsApp integration."""
        if not self.enabled:
            logger.info("WhatsApp omnichannel integration is disabled by config.")
            return
        logger.info("Starting WhatsApp omnichannel service (Owner: %s)...", self.owner_identities)
        from jarvis.integrations.whatsapp.intelligence.engine import get_intelligence
        self.intelligence = get_intelligence(self.gateway.inbox)
        from jarvis.core.llm.client import get_llm
        self.intelligence.client = get_llm()
        if self.config.get("whatsapp", {}).get("semantic_retrieval", True):
            async def embed_message(text):
                model = await self.intelligence.client.resolve("embed")
                vectors = await self.intelligence.client.embed([text], model=model)
                self.intelligence.embedding_model = model
                return vectors[0] if vectors else []
            self.intelligence.embedder = embed_message
        self.intelligence.style_agent = self.personal_reply
        if self.personal_reply is None and self.read_only:
            from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore, default_db_path
            if default_db_path().is_file():
                self.intelligence.style_store = PersonalReplyStore()
                from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
                self.draft_only_agent = PersonalReplyAgent(store=self.intelligence.style_store,
                                                            inbox=self.gateway.inbox, transport=None,
                                                            use_jde=False)
        if self.personal_reply is not None:
            self.personal_reply.policy.pause_store = self.intelligence.store
        self.transport.intelligence = self.intelligence
        await self.intelligence.start()
        await self.transport.start()
        if self.personal_reply is not None:
            recovered = self.personal_reply.recover()  # expire old grants; never resend interrupted sends
            if any(recovered.values()):
                logger.info("WhatsApp personal reply recovery: %s", recovered)
            self.personal_reply.start_background()
        if self.memory is not None:
            async def _index_history():
                try:
                    count = await asyncio.to_thread(self.memory.index_recent)
                    if count and self.knowledge_service is not None:
                        self.knowledge_service.schedule_embedding()
                    logger.info("WhatsApp memory: %d chat sections searchable", count)
                except Exception as exc:
                    logger.debug("WhatsApp history indexing skipped: %s", exc)
            self._memory_task = asyncio.create_task(_index_history())

    async def stop(self) -> None:
        """Stop the WhatsApp integration."""
        logger.info("Stopping WhatsApp omnichannel service...")
        if self.personal_reply is not None:
            await self.personal_reply.close()
        await self.transport.stop()
        if getattr(self, "intelligence", None):
            await self.intelligence.close()

    async def _on_chat_state(self, payload: Dict[str, Any]) -> None:
        """Store WhatsApp's unread badges (what the phone shows) so summaries and counts match it."""
        chats = payload.get("chats") or []
        try:
            await asyncio.to_thread(self.gateway.inbox.update_chats, chats, bool(payload.get("full")),
                                    bool(payload.get("synced")), str(payload.get("generation") or ""),
                                    str(payload.get("synced_generation") or ""), payload)
        except Exception as exc:
            logger.warning("Could not store WhatsApp chat state: %s", exc)

    async def _on_incoming_message(self, message: NormalizedWhatsAppMessage) -> None:
        """Handle incoming message routed from transport."""
        trace_incoming(stage="python_service", event_type="incoming_message", message_id=message.message_id,
                       chat_jid=message.chat_id, from_me=message.is_from_me, message_type=message.type,
                       timestamp=message.timestamp, python_receive_result="DISPATCHED")
        if self.read_only:
            await self.gateway.handle_incoming(message.model_copy(update={"history": True}))
            if (not message.history and not message.is_from_me and message.type == 'text'
                    and getattr(self, 'draft_only_agent', None) is not None
                    and self.draft_only_agent.maturity(message.chat_id) in (
                        'DRAFT_READY', 'VERIFIED_STYLE_BUILDING', 'AUTO_REPLY_CANDIDATE',
                        'TIMED_AUTO_REPLY_READY')):
                # Read-only listener may create a local suggestion. The agent
                # has no transport, so this branch cannot send a WhatsApp reply.
                async def prepare_draft(chat_id: str) -> None:
                    try:
                        await self.draft_only_agent.draft_latest(chat_id)
                    except Exception:
                        logger.exception('Could not prepare read-only personal draft')
                asyncio.create_task(prepare_draft(message.chat_id))
            return
        if message.history:  # missed while JARVIS was offline: stored only (no announcement, reply or command)
            await self.gateway.handle_incoming(message)
            self._remember_chat(message.chat_id)
            return
        logger.info("Received WhatsApp message from %s (%s)", message.sender_display_name, message.sender_id)
        # The gateway's in-memory dedupe is reset on restart. Capture durable
        # existence first so a replay of an already stored ID cannot fire an
        # automation again after a new Python generation starts.
        was_stored = self.gateway.inbox.contains_message(message.message_id, message.chat_id)
        result = await self.gateway.handle_incoming(message)
        from jarvis.integrations.whatsapp.personal_reply.dedupe import is_group_chat
        if self.event_bus and not message.is_from_me and not getattr(message, "is_group", False) \
                and not is_group_chat(message.chat_id) \
                and not self.gateway.is_owner(message.sender_id) \
                and not was_stored and self.gateway.inbox.contains_message(message.message_id, message.chat_id) \
                and (not isinstance(result, dict) or result.get("status") not in
                     {"DUPLICATE_IGNORED", "PENDING_DECRYPTION"}):
            # This event is evidence that a current direct message reached the
            # Python gateway. Its body is never a command or event-bus payload.
            self.event_bus.emit("whatsapp.message_received", message.message_id,
                                message_id=message.message_id, chat_id=message.chat_id,
                                sender_id=message.sender_id, message_type=message.type,
                                history=False, from_me=False, is_group=False)
        self._remember_chat(message.chat_id)

    def _remember_chat(self, chat_id: str) -> None:
        """Keep the chat searchable for the owner's questions (WhatsApp memory / RAG)."""
        memory = getattr(self, "memory", None)
        if memory is None or not chat_id:
            return
        on_done = getattr(self.knowledge_service, "schedule_embedding", None) if self.knowledge_service else None
        try:
            memory.schedule(chat_id, on_done=on_done)
        except Exception as exc:
            logger.debug("WhatsApp memory update skipped: %s", exc)

    def _on_bridge_status(self, status_payload: Dict[str, Any]) -> None:
        state = status_payload.get("state", "UNKNOWN")
        logger.info("WhatsApp Bridge status updated: %s", state)
        try:
            self.gateway.inbox.set_connector_state(state)
            if status_payload.get("identity"):
                diagnostics = dict(status_payload.get("diagnostics") or {})
                diagnostics["event_health"] = status_payload.get("event_health") or {}
                self.gateway.inbox.set_bridge_runtime(status_payload["identity"],
                                                       diagnostics)
        except Exception as exc:
            logger.warning("Could not store WhatsApp connector state: %s", exc)
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
