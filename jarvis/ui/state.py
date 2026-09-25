"""Central reactive state for JARVIS Qt/QML UI."""
from __future__ import annotations

import collections
import logging
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from jarvis.ui.events import AssistantState, ConnectionState, redact_sensitive_text

logger = logging.getLogger("jarvis.ui.state")

MAX_HISTORY_ITEMS = 50
MAX_METRIC_SAMPLES = 60


class JarvisUIState(QObject):
    """Exposes observable, thread-safe UI properties to QML."""

    # Signals for property changes
    connectionChanged = Signal(str)
    assistantStateChanged = Signal(str)
    transcriptPartialChanged = Signal(str)
    transcriptFinalChanged = Signal(str)
    responseChanged = Signal(str)
    activeTaskChanged = Signal(dict)
    confirmationChanged = Signal(dict)
    audioLevelsChanged = Signal(list)
    cpuPercentChanged = Signal(float)
    ramPercentChanged = Signal(float)
    gpuPercentChanged = Signal(float)
    vramMbChanged = Signal(float)
    pingMsChanged = Signal(int)
    lowResourceModeChanged = Signal(bool)
    recentTasksChanged = Signal(list)
    modelsChanged = Signal(list)
    devicesChanged = Signal(list)
    integrationsChanged = Signal(list)
    whatsappStatusChanged = Signal(str)
    whatsappAccountChanged = Signal(str)
    whatsappLastMessageChanged = Signal(str)
    whatsappModeChanged = Signal(str)
    whatsappVoiceReplyChanged = Signal(bool)
    statusMessageChanged = Signal(str)
    isListeningChanged = Signal(bool)
    isSpeakingChanged = Signal(bool)
    isTaskRunningChanged = Signal(bool)
    taskHistoryChanged = Signal()
    audioLevelChanged = Signal(float)
    conversationChanged = Signal()
    llmStatusChanged = Signal(str)
    voiceStatusChanged = Signal(str)
    ui3dChanged = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._connection: str = ConnectionState.OFFLINE.value
        self._assistant_state: str = AssistantState.IDLE.value
        self._transcript_partial: str = ""
        self._transcript_final: str = ""
        self._response: str = ""
        self._active_task: dict[str, Any] = {}
        self._confirmation: dict[str, Any] = {}
        self._audio_levels: list[float] = [0.0] * 24
        self._cpu_percent: float = 0.0
        self._ram_percent: float = 0.0
        self._gpu_percent: float = 0.0
        self._vram_mb: float = 0.0
        self._ping_ms: int = 0
        self._low_resource_mode: bool = False
        self._status_message: str = "Ready"
        self._audio_level: float = 0.0
        self._conversation: list[dict[str, Any]] = []
        self._llm_status: str = "UNKNOWN"
        self._voice_status: str = "UNKNOWN"
        self._ui3d: bool = True

        # Bounded history buffers
        self._recent_tasks: list[dict[str, Any]] = []
        self._models: list[dict[str, Any]] = [
            {"name": "STT (Whisper)", "status": "READY", "details": "Faster-Whisper local"},
            {"name": "Router (Qwen-0.5B)", "status": "READY", "details": "Fast deterministic/SLM"},
            {"name": "Planner (Qwen-1.5B)", "status": "SLEEPING", "details": "On-demand worker"},
            {"name": "Vision (Qwen2-VL)", "status": "SLEEPING", "details": "UI screen grounding"},
            {"name": "TTS (Piper)", "status": "READY", "details": "Natural neural speech"},
        ]
        self._devices: list[dict[str, Any]] = [
            {"name": "Desktop PC (Host)", "status": "ONLINE", "type": "desktop"},
            {"name": "Microphone", "status": "READY", "type": "audio_in"},
            {"name": "Speaker", "status": "READY", "type": "audio_out"},
            {"name": "Android Phone", "status": "DISCONNECTED", "type": "mobile"},
            {"name": "Bluetooth Audio", "status": "DISCONNECTED", "type": "bluetooth"},
        ]
        self._integrations: list[dict[str, Any]] = [
            {"name": "WhatsApp Omnichannel", "status": "DISCONNECTED", "desc": "Baileys transport bridge (Draft-only)"},
            {"name": "Ollama LLM", "status": "CONNECTED", "desc": "Local inference engine"},
            {"name": "Windows UI Automation", "status": "CONNECTED", "desc": "Native accessibility tree"},
            {"name": "Android (scrcpy)", "status": "DEGRADED", "desc": "ADB device control & phone mirror"},
            {"name": "LocalSend", "status": "DEGRADED", "desc": "Fast LAN PC ↔ Android transfer"},
            {"name": "Browser (Playwright)", "status": "CONNECTED", "desc": "Semantic web automation & DOM"},
            {"name": "FreshRSS", "status": "DISABLED", "desc": "Local feed aggregator & intelligence"},
            {"name": "Push Notifications", "status": "CONNECTED", "desc": "ntfy / Gotify mobile alerts"},
            {"name": "Memos", "status": "DISABLED", "desc": "Human-readable notes & inbox"},
            {"name": "Node-RED", "status": "DISABLED", "desc": "Safe event & flow bridge"},
            {"name": "Google Services", "status": "DISCONNECTED", "desc": "Gmail, Calendar, Drive"},
        ]

        self._whatsapp_status: str = "DISCONNECTED"
        self._whatsapp_account: str = "Not Paired"
        self._whatsapp_last_message: str = "None"
        self._whatsapp_mode: str = "DRAFT_ONLY"
        self._whatsapp_voice_reply: bool = False

        # Metric history for lightweight sparklines
        self.cpu_history: collections.deque[float] = collections.deque([0.0] * 60, maxlen=60)
        self.ram_history: collections.deque[float] = collections.deque([0.0] * 60, maxlen=60)
        self.gpu_history: collections.deque[float] = collections.deque([0.0] * 60, maxlen=60)

    # --- Connection State ---
    @Property(str, notify=connectionChanged)
    def connectionStatus(self) -> str:
        return self._connection

    def set_connection(self, status: str) -> None:
        if self._connection != status:
            self._connection = status
            self.connectionChanged.emit(status)
            if status == ConnectionState.OFFLINE.value:
                self.set_assistant_state(AssistantState.OFFLINE.value)

    # --- Assistant State ---
    @Property(str, notify=assistantStateChanged)
    def assistantState(self) -> str:
        return self._assistant_state

    def set_assistant_state(self, state: str) -> None:
        if self._assistant_state != state:
            self._assistant_state = state
            self.assistantStateChanged.emit(state)
            self.isListeningChanged.emit(state == AssistantState.LISTENING.value)
            self.isSpeakingChanged.emit(state == AssistantState.SPEAKING.value)
            self.isTaskRunningChanged.emit(state in (
                AssistantState.ROUTING.value,
                AssistantState.PLANNING.value,
                AssistantState.EXECUTING.value,
                AssistantState.VERIFYING.value
            ))

    @Property(bool, notify=isListeningChanged)
    def isListening(self) -> bool:
        return self._assistant_state == AssistantState.LISTENING.value

    @Property(bool, notify=isSpeakingChanged)
    def isSpeaking(self) -> bool:
        return self._assistant_state == AssistantState.SPEAKING.value

    @Property(bool, notify=isTaskRunningChanged)
    def isTaskRunning(self) -> bool:
        return self._assistant_state in (
            AssistantState.ROUTING.value,
            AssistantState.PLANNING.value,
            AssistantState.EXECUTING.value,
            AssistantState.VERIFYING.value
        )

    # --- Transcripts & Response ---
    @Property(str, notify=transcriptPartialChanged)
    def transcriptPartial(self) -> str:
        return self._transcript_partial

    def set_transcript_partial(self, text: str) -> None:
        cleaned = redact_sensitive_text(text)
        if self._transcript_partial != cleaned:
            self._transcript_partial = cleaned
            self.transcriptPartialChanged.emit(cleaned)

    @Property(str, notify=transcriptFinalChanged)
    def transcriptFinal(self) -> str:
        return self._transcript_final

    def set_transcript_final(self, text: str) -> None:
        cleaned = redact_sensitive_text(text)
        if self._transcript_final != cleaned:
            self._transcript_final = cleaned
            self.transcriptFinalChanged.emit(cleaned)

    @Property(str, notify=responseChanged)
    def response(self) -> str:
        return self._response

    def set_response(self, text: str) -> None:
        cleaned = redact_sensitive_text(text)
        if self._response != cleaned:
            self._response = cleaned
            self.responseChanged.emit(cleaned)

    # --- Active Task ---
    @Property("QVariantMap", notify=activeTaskChanged)
    def activeTask(self) -> dict[str, Any]:
        return self._active_task

    def set_active_task(self, task: dict[str, Any]) -> None:
        safe_task = {k: redact_sensitive_text(v) if isinstance(v, str) else v for k, v in task.items()}
        self._active_task = safe_task
        self.activeTaskChanged.emit(safe_task)

    # --- Confirmation Ticket ---
    @Property("QVariantMap", notify=confirmationChanged)
    def confirmationTicket(self) -> dict[str, Any]:
        return self._confirmation

    def set_confirmation(self, ticket: dict[str, Any]) -> None:
        safe_ticket = {k: redact_sensitive_text(v) if isinstance(v, str) else v for k, v in ticket.items()}
        self._confirmation = safe_ticket
        self.confirmationChanged.emit(safe_ticket)
        if safe_ticket:
            self.set_assistant_state(AssistantState.WAITING_CONFIRMATION.value)

    def clear_confirmation(self) -> None:
        self._confirmation = {}
        self.confirmationChanged.emit({})

    # --- Audio Waveform ---
    @Property("QVariantList", notify=audioLevelsChanged)
    def audioLevels(self) -> list[float]:
        return self._audio_levels

    def set_audio_levels(self, levels: list[float]) -> None:
        # Bounded between 0.0 and 1.0, maximum 24 bars
        bars = [max(0.0, min(1.0, float(v))) for v in levels[:24]]
        if len(bars) < 24:
            bars += [0.0] * (24 - len(bars))
        self._audio_levels = bars
        self.audioLevelsChanged.emit(bars)
        newest = bars[-1] if bars else 0.0
        if abs(newest - self._audio_level) > 0.01:
            self._audio_level = newest
            self.audioLevelChanged.emit(newest)

    @Property(float, notify=audioLevelChanged)
    def audioLevel(self) -> float:
        """Newest microphone level (0..1) - drives the reactor's voice reactivity."""
        return self._audio_level

    # --- Conversation (chat transcript shown on the home screen) ---
    @Property("QVariantList", notify=conversationChanged)
    def conversation(self) -> list[dict[str, Any]]:
        return self._conversation

    def add_turn(self, role: str, text: str, streaming: bool = False, state: str = "") -> None:
        text = redact_sensitive_text((text or "").strip())
        if not text:
            return
        last = self._conversation[-1] if self._conversation else None
        if last and last["role"] == role and last.get("streaming"):
            last.update(text=text, streaming=streaming, state=state or last.get("state", ""))
        elif last and last["role"] == role and last["text"] == text:
            return
        else:
            import time as _time
            self._conversation.append({"role": role, "text": text, "time": _time.strftime("%H:%M"),
                                       "streaming": streaming, "state": state})
            del self._conversation[:-MAX_HISTORY_ITEMS]
        self._conversation = list(self._conversation)
        self.conversationChanged.emit()

    @Slot()
    def clearConversation(self) -> None:
        self._conversation = []
        self.conversationChanged.emit()

    @Property(str, notify=llmStatusChanged)
    def llmStatus(self) -> str:
        return self._llm_status

    def set_llm_status(self, status: str) -> None:
        if status != self._llm_status:
            self._llm_status = status
            self.llmStatusChanged.emit(status)

    @Property(bool, notify=ui3dChanged)
    def ui3d(self) -> bool:
        """Render the real-time 3D reactor (the UI falls back to 2D automatically when unsupported)."""
        return self._ui3d

    def set_ui3d(self, enabled: bool) -> None:
        if bool(enabled) != self._ui3d:
            self._ui3d = bool(enabled)
            self.ui3dChanged.emit(self._ui3d)

    @Property(str, notify=voiceStatusChanged)
    def voiceStatus(self) -> str:
        return self._voice_status

    def set_voice_status(self, status: str) -> None:
        if status != self._voice_status:
            self._voice_status = status
            self.voiceStatusChanged.emit(status)

    # --- Metrics ---
    @Property(float, notify=cpuPercentChanged)
    def cpuPercent(self) -> float:
        return self._cpu_percent

    @Property(float, notify=ramPercentChanged)
    def ramPercent(self) -> float:
        return self._ram_percent

    @Property(float, notify=gpuPercentChanged)
    def gpuPercent(self) -> float:
        return self._gpu_percent

    @Property(float, notify=vramMbChanged)
    def vramMb(self) -> float:
        return self._vram_mb

    @Property(int, notify=pingMsChanged)
    def pingMs(self) -> int:
        return self._ping_ms

    def update_metrics(self, cpu: float, ram: float, gpu: float = 0.0, vram: float = 0.0, ping: int = 0) -> None:
        self._cpu_percent = round(cpu, 1)
        self._ram_percent = round(ram, 1)
        self._gpu_percent = round(gpu, 1)
        self._vram_mb = round(vram, 1)
        self._ping_ms = ping

        self.cpu_history.append(self._cpu_percent)
        self.ram_history.append(self._ram_percent)
        self.gpu_history.append(self._gpu_percent)

        self.cpuPercentChanged.emit(self._cpu_percent)
        self.ramPercentChanged.emit(self._ram_percent)
        self.gpuPercentChanged.emit(self._gpu_percent)
        self.vramMbChanged.emit(self._vram_mb)
        self.pingMsChanged.emit(self._ping_ms)

    # --- Low Resource Mode ---
    @Property(bool, notify=lowResourceModeChanged)
    def lowResourceMode(self) -> bool:
        return self._low_resource_mode

    def set_low_resource_mode(self, enabled: bool) -> None:
        if self._low_resource_mode != enabled:
            self._low_resource_mode = enabled
            self.lowResourceModeChanged.emit(enabled)

    # --- Status Message ---
    @Property(str, notify=statusMessageChanged)
    def statusMessage(self) -> str:
        return self._status_message

    def set_status_message(self, msg: str) -> None:
        self._status_message = msg
        self.statusMessageChanged.emit(msg)

    # --- Models, Devices, Integrations ---
    @Property("QVariantList", notify=modelsChanged)
    def models(self) -> list[dict[str, Any]]:
        return self._models

    def update_models(self, models: list[dict[str, Any]]) -> None:
        self._models = models
        self.modelsChanged.emit(models)

    @Property("QVariantList", notify=devicesChanged)
    def devices(self) -> list[dict[str, Any]]:
        return self._devices

    def update_devices(self, devices: list[dict[str, Any]]) -> None:
        self._devices = devices
        self.devicesChanged.emit(devices)

    @Property("QVariantList", notify=integrationsChanged)
    def integrations(self) -> list[dict[str, Any]]:
        return self._integrations

    def update_integrations(self, integrations: list[dict[str, Any]]) -> None:
        self._integrations = integrations
        self.integrationsChanged.emit(integrations)

    @Slot()
    def refresh_connectors(self) -> None:
        try:
            from jarvis.connectors.manager import get_connector_manager
            mgr = get_connector_manager()
            statuses = mgr.get_all_statuses()
            name_map = {
                "android": "Android (scrcpy)",
                "localsend": "LocalSend",
                "browser": "Browser (Playwright)",
                "freshrss": "FreshRSS",
                "notifications": "Push Notifications",
                "memos": "Memos",
                "nodered": "Node-RED",
            }
            for key, display_name in name_map.items():
                st = statuses.get(key, {})
                status_val = st.get("status", "DISABLED")
                for item in self._integrations:
                    if item.get("name") == display_name:
                        item["status"] = status_val
                        break
            self.integrationsChanged.emit(self._integrations)
        except Exception as e:
            logger.debug("Connector refresh skipped: %s", e)


    @Property(str, notify=whatsappStatusChanged)
    def whatsappStatus(self) -> str:
        return self._whatsapp_status

    @Slot(str)
    def setWhatsappStatus(self, status: str) -> None:
        if self._whatsapp_status != status:
            self._whatsapp_status = status
            self.whatsappStatusChanged.emit(status)
            for item in self._integrations:
                if item.get("name") == "WhatsApp Omnichannel":
                    item["status"] = status
                    break
            self.integrationsChanged.emit(self._integrations)

    @Property(str, notify=whatsappAccountChanged)
    def whatsappAccount(self) -> str:
        return self._whatsapp_account

    @Slot(str)
    def setWhatsappAccount(self, account: str) -> None:
        if self._whatsapp_account != account:
            self._whatsapp_account = account
            self.whatsappAccountChanged.emit(account)

    @Property(str, notify=whatsappLastMessageChanged)
    def whatsappLastMessage(self) -> str:
        return self._whatsapp_last_message

    @Slot(str)
    def setWhatsappLastMessage(self, message: str) -> None:
        if self._whatsapp_last_message != message:
            self._whatsapp_last_message = message
            self.whatsappLastMessageChanged.emit(message)

    @Property(str, notify=whatsappModeChanged)
    def whatsappMode(self) -> str:
        return self._whatsapp_mode

    @Slot(str)
    def setWhatsappMode(self, mode: str) -> None:
        if self._whatsapp_mode != mode:
            self._whatsapp_mode = mode
            self.whatsappModeChanged.emit(mode)

    @Property(bool, notify=whatsappVoiceReplyChanged)
    def whatsappVoiceReply(self) -> bool:
        return self._whatsapp_voice_reply

    @Slot()
    def toggleWhatsappVoiceReply(self) -> None:
        self._whatsapp_voice_reply = not self._whatsapp_voice_reply
        self.whatsappVoiceReplyChanged.emit(self._whatsapp_voice_reply)

    # --- Recent Tasks History ---
    @Property("QVariantList", notify=recentTasksChanged)
    def recentTasks(self) -> list[dict[str, Any]]:
        return self._recent_tasks

    def add_recent_task(self, task: dict[str, Any]) -> None:
        safe_task = {k: redact_sensitive_text(v) if isinstance(v, str) else v for k, v in task.items()}
        # Keep at front, bound to MAX_HISTORY_ITEMS
        self._recent_tasks.insert(0, safe_task)
        if len(self._recent_tasks) > MAX_HISTORY_ITEMS:
            self._recent_tasks = self._recent_tasks[:MAX_HISTORY_ITEMS]
        self.recentTasksChanged.emit(self._recent_tasks)
        self.taskHistoryChanged.emit()

    @Slot(result="QVariantList")
    def getCpuHistory(self) -> list[float]:
        return list(self.cpu_history)

    @Slot(result="QVariantList")
    def getRamHistory(self) -> list[float]:
        return list(self.ram_history)

    @Slot(result="QVariantList")
    def getGpuHistory(self) -> list[float]:
        return list(self.gpu_history)
