"""Main application controller linking QML, State, Bridge, and Tray."""
from __future__ import annotations

import logging
import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from jarvis.ui.bridge import JarvisUIBridge
from jarvis.ui.events import AssistantState, ConnectionState, UIEvent, UIEventType
from jarvis.ui.metrics import MetricsSampler
from jarvis.ui.models import ActivityListModel
from jarvis.ui.settings import UISettings
from jarvis.ui.state import JarvisUIState

logger = logging.getLogger("jarvis.ui.controller")


class JarvisUIController(QObject):
    """Exposes all high-level actions and controls to QML."""

    showVoiceOverlayRequested = Signal()
    hideVoiceOverlayRequested = Signal()
    showDashboardRequested = Signal()
    hideDashboardRequested = Signal()
    showToastRequested = Signal(str, str)  # title, message
    whatsappPersonalEvent = Signal(str, dict)  # event name, payload (Dashboard -> WhatsApp -> Contacts)

    def __init__(
        self,
        state: JarvisUIState,
        bridge: JarvisUIBridge,
        settings: UISettings,
        activity_model: ActivityListModel,
        metrics: MetricsSampler,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.bridge = bridge
        self.settings = settings
        self.activity_model = activity_model
        self.metrics = metrics

        # Wire Bridge Signals
        self.bridge.connectionChanged.connect(self._on_connection_changed)
        self.bridge.eventReceived.connect(self._on_event_received)
        self.bridge.responseReceived.connect(self._on_response_received)
        self.bridge.pingUpdated.connect(self._on_ping_updated)

        # Wire Metrics
        self.metrics.metricsSampled.connect(self._on_metrics_sampled)
        self.state.set_ui3d(self.settings.get("ui_3d", True) is not False)

        # Watchdog: a missed backend event must never leave the UI stuck on "Listening" / "Speaking".
        self._last_activity = time.monotonic()
        self.state.assistantStateChanged.connect(self._touch)
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(1000)
        self._watchdog.timeout.connect(self._check_stuck)
        self._watchdog.start()
        self.state.set_low_resource_mode(bool(self.settings.get("low_resource_mode", False)))

    # Seconds a state may last without any backend event before the UI recovers on its own.
    STUCK_LIMITS_S = {
        AssistantState.LISTENING.value: 20.0,
        AssistantState.TRANSCRIBING.value: 15.0,
        AssistantState.SPEAKING.value: 90.0,
        AssistantState.EXECUTING.value: 180.0,
        AssistantState.ROUTING.value: 60.0,
        AssistantState.PLANNING.value: 120.0,
        AssistantState.VERIFYING.value: 60.0,
        AssistantState.SUCCESS.value: 6.0,
    }

    def _touch(self, *_args) -> None:
        self._last_activity = time.monotonic()

    def _check_stuck(self, now: float | None = None) -> bool:
        st = self.state.assistantState
        limit = self.STUCK_LIMITS_S.get(st)
        now = time.monotonic() if now is None else now
        if limit is None or now - self._last_activity < limit:
            return False
        logger.info("UI state %s had no backend activity for %.0fs; returning to idle", st, now - self._last_activity)
        if st == AssistantState.LISTENING.value:
            self.bridge.send_control("ptt_stop")
        self.state.set_assistant_state(AssistantState.IDLE.value)
        self.state.set_status_message("Ready")
        self.hideVoiceOverlayRequested.emit()
        self._touch()
        return True

    # --- UI Actions callable from QML ---

    @Slot(str)
    def sendCommand(self, text: str) -> None:
        """Submit a user text command through existing backend."""
        clean_text = text.strip()
        if not clean_text:
            return

        self.state.set_transcript_final(clean_text)
        self.state.set_response("")
        self.state.add_turn("user", clean_text)
        self.state.set_assistant_state(AssistantState.EXECUTING.value)
        self.state.set_status_message(f"Executing: {clean_text}")

        # Dispatch via bridge to backend
        self.bridge.send_command(clean_text)

    @Slot()
    def startPTT(self) -> None:
        """Start voice push-to-talk."""
        self.state.set_transcript_partial("")
        self.state.set_status_message("Listening...")
        self.state.set_assistant_state(AssistantState.LISTENING.value)
        self.showVoiceOverlayRequested.emit()
        self.bridge.send_control("ptt_start")

    @Slot()
    def toggleTalk(self) -> None:
        """One button / hotkey for voice: start listening, or finish the current utterance."""
        if self.state.isListening:
            self.stopPTT()
        else:
            self.startPTT()

    @Slot()
    def stopPTT(self) -> None:
        """Stop push-to-talk."""
        if self.state.isListening:
            self.state.set_assistant_state(AssistantState.TRANSCRIBING.value)
            self.state.set_status_message("Transcribing...")
        self.bridge.send_control("ptt_stop")

    @Slot()
    def cancelTask(self) -> None:
        """Cancel current running task safely via backend CONTROL lane."""
        self.state.set_status_message("Cancelling task...")
        self.bridge.send_command("cancel")

    @Slot()
    def stopSpeaking(self) -> None:
        """Stop Jarvis speech output."""
        self.bridge.send_control("stop_speaking")

    @Slot(str)
    def confirmTicket(self, ticket_id: str) -> None:
        """Approve a Phase-5 security confirmation ticket."""
        self.state.clear_confirmation()
        self.state.set_status_message(f"Approved action for ticket {ticket_id}")
        self.bridge.send_command(f"confirm ticket {ticket_id}")

    @Slot(str)
    def rejectTicket(self, ticket_id: str) -> None:
        """Deny a Phase-5 security confirmation ticket."""
        self.state.clear_confirmation()
        self.state.set_status_message(f"Rejected action for ticket {ticket_id}")
        self.bridge.send_command(f"reject ticket {ticket_id}")

    @Slot(str, "QVariant")
    def updateSetting(self, key: str, value: Any) -> None:
        """Safely update and persist a UI setting."""
        self.settings.set(key, value)
        if key == "ui_3d":
            self.state.set_ui3d(bool(value))
        if key == "low_resource_mode":
            self.state.set_low_resource_mode(bool(value))
            if bool(value):
                self.metrics.set_interval(2000)
            else:
                self.metrics.set_interval(1000)

    @Slot(str, result="QVariant")
    def getSetting(self, key: str) -> Any:
        return self.settings.get(key)

    @Slot(result="QVariantMap")
    def getAllSettings(self) -> dict[str, Any]:
        return self.settings.all()

    @Slot()
    def requestVoiceOverlay(self) -> None:
        self.showVoiceOverlayRequested.emit()

    @Slot()
    def dismissVoiceOverlay(self) -> None:
        self.hideVoiceOverlayRequested.emit()

    @Slot()
    def requestDashboard(self) -> None:
        self.showDashboardRequested.emit()

    @Slot()
    def toggleDashboard(self) -> None:
        self.showDashboardRequested.emit()

    # --- Internal Bridge Event Handlers ---

    def _on_connection_changed(self, conn_state: str) -> None:
        self.state.set_connection(conn_state)
        if conn_state == ConnectionState.ONLINE.value:
            self.state.set_assistant_state(AssistantState.IDLE.value)
            self.state.set_status_message("Connected to JARVIS EDGE")
        elif conn_state == ConnectionState.OFFLINE.value:
            self.state.set_assistant_state(AssistantState.OFFLINE.value)
            self.state.set_status_message("Disconnected from backend")
        elif conn_state == ConnectionState.RECONNECTING.value:
            self.state.set_status_message("Reconnecting...")

    def _on_event_received(self, event: UIEvent) -> None:
        ev_type = event.event_type
        if ev_type != UIEventType.AUDIO_LEVEL:
            self._touch()
        if ev_type == UIEventType.JARVIS_READY:
            self.state.set_assistant_state(AssistantState.IDLE.value)
        elif ev_type == UIEventType.WAKE_DETECTED:
            self.showDashboardRequested.emit()
            self.showVoiceOverlayRequested.emit()
            self.state.set_assistant_state(AssistantState.LISTENING.value)
            self.state.set_status_message("Listening...")
        elif ev_type == UIEventType.LISTENING_STARTED:
            self.state.set_voice_status("READY")
            self.state.set_transcript_partial("")
            self.state.set_status_message("Listening...")
            self.state.set_assistant_state(AssistantState.LISTENING.value)
            self.showDashboardRequested.emit()
            self.showVoiceOverlayRequested.emit()
        elif ev_type == UIEventType.LISTENING_STOPPED:
            if self.state.isListening:
                self.state.set_assistant_state(AssistantState.TRANSCRIBING.value)
        elif ev_type == UIEventType.TRANSCRIPT_PARTIAL:
            text = event.payload.get("text", "")
            self.state.set_transcript_partial(text)
        elif ev_type == UIEventType.TRANSCRIPT_FINAL:
            text = event.payload.get("text", "")
            self.state.set_transcript_final(text)
            self.state.set_response("")
            self.state.add_turn("user", text)
        elif ev_type == UIEventType.RESPONSE_PARTIAL:
            text = event.payload.get("text", "")
            if text.strip():
                self.state.set_response(text)
                self.state.add_turn("assistant", text, streaming=True)
                if self.state.assistantState not in (AssistantState.SPEAKING.value, AssistantState.LISTENING.value):
                    self.state.set_status_message("Answering...")
        elif ev_type == UIEventType.MODEL_STATE:
            if "reachable" in event.payload:
                self.state.set_llm_status("ONLINE" if event.payload.get("reachable") else "OFFLINE")
        elif ev_type == UIEventType.AUDIO_LEVEL:
            self.state.set_audio_levels(event.payload.get("levels", []))
        elif ev_type == UIEventType.WHATSAPP_PERSONAL:
            payload = dict(event.payload)
            name = str(payload.pop("event", ""))
            self.whatsappPersonalEvent.emit(name, payload)
            if name.endswith("approval_needed") or name.endswith("review_needed"):
                who = payload.get("display_name", "a contact")
                self.showToastRequested.emit("WhatsApp", f"Reply to {who} is waiting for you in Contacts.")
        elif ev_type == UIEventType.TASK_STARTED:
            self.state.set_assistant_state(AssistantState.EXECUTING.value)
        elif ev_type == UIEventType.TTS_STARTED:
            self.state.set_assistant_state(AssistantState.SPEAKING.value)
        elif ev_type in (UIEventType.TTS_STOPPED, UIEventType.VOICE_IDLE):
            if ev_type == UIEventType.VOICE_IDLE:
                self.state.set_voice_status("READY")
            if not self.state.isListening and self.state.assistantState != AssistantState.ERROR.value:
                self.state.set_assistant_state(AssistantState.IDLE.value)
                self.state.set_status_message("Ready")
        elif ev_type == UIEventType.VOICE_ERROR:
            self.state.set_voice_status("ERROR")
            self.state.set_assistant_state(AssistantState.ERROR.value)
            err = event.payload.get("error", "Audio unavailable")
            self.state.set_status_message(err)
            self.showToastRequested.emit("Voice Input Error", f"Voice unavailable: {err}")
        elif ev_type == UIEventType.CONFIRMATION_REQUIRED:
            self.state.set_assistant_state(AssistantState.WAITING_CONFIRMATION.value)
            self.state.set_status_message("Awaiting Confirmation")
            
            ticket_id = event.payload.get("ticket_id")
            summary = event.payload.get("summary")
            
            if not ticket_id and "tool_result" in event.payload:
                tr_data = event.payload.get("tool_result", {}).get("data", {})
                if isinstance(tr_data, dict):
                    ticket_id = tr_data.get("ticket_id")
                    summary = tr_data.get("human_summary") or event.payload.get("message")
                    
            self.state.set_confirmation({
                "ticket_id": ticket_id or "",
                "title": "ACTION REQUIRED",
                "target": "Execution Approval",
                "details": summary or "Confirm action to proceed."
            })
        elif ev_type == UIEventType.TASK_FAILED:
            self.state.set_assistant_state(AssistantState.ERROR.value)
            err = event.payload.get("message") or event.payload.get("error") or "Task failed"
            self.state.set_response(err)
            self.showToastRequested.emit("Task Error", err)
        elif ev_type == UIEventType.INTEGRATION_STATE:
            st = event.payload.get("state") or event.payload.get("status")
            if st:
                self.state.setWhatsappStatus(st.upper())
                if st.upper() == "CONNECTED":
                    self.state.setWhatsappAccount("Linked (+916381456199)")
                elif st.upper() in ("DISCONNECTED", "LOGGED_OUT"):
                    self.state.setWhatsappAccount("Not Paired")
            code = event.payload.get("code")
            if code:
                self.state.setWhatsappAccount(f"Pairing: {code}")
                self.showToastRequested.emit("WhatsApp Pairing Code", f"Pairing code: {code}")

    @Slot()
    def connectWhatsapp(self) -> None:
        """Trigger WhatsApp connection / reconnection."""
        self.state.set_status_message("Connecting WhatsApp...")
        self.bridge.send_command("connect whatsapp")

    @Slot()
    def disconnectWhatsapp(self) -> None:
        """Disconnect WhatsApp session."""
        self.state.set_status_message("Disconnecting WhatsApp...")
        self.bridge.send_command("disconnect whatsapp")

    @Slot()
    def repairWhatsapp(self) -> None:
        """Request new pairing code for WhatsApp."""
        self.state.set_status_message("Requesting WhatsApp pairing code...")
        self.bridge.send_command("re-pair whatsapp")

    def _on_response_received(self, data: dict[str, Any]) -> None:
        self._touch()
        state_str = data.get("state", "SUCCESS")
        msg = data.get("message", "")
        req_id = data.get("request_id", "")
        req_text = self.state.transcriptFinal or "Command"

        self.state.set_response(msg)
        self.state.add_turn("assistant", msg, streaming=False, state=state_str)

        if state_str == "SUCCESS" and self.state.assistantState != AssistantState.SPEAKING.value:
            self.state.set_assistant_state(AssistantState.SUCCESS.value)
            self.state.set_status_message("Done")
        elif state_str == "WAITING_CONFIRMATION":
            self.state.set_assistant_state(AssistantState.WAITING_CONFIRMATION.value)
            self.state.set_status_message("Awaiting Confirmation")
        elif state_str == "CANCELLED":
            self.state.set_assistant_state(AssistantState.IDLE.value)
            self.state.set_status_message("Cancelled")
        elif state_str != "SUCCESS":
            self.state.set_assistant_state(AssistantState.ERROR.value)
            self.state.set_status_message("Failed")

        # Record in activity model and recent tasks
        task_entry = {
            "request_id": req_id,
            "text": req_text,
            "state": state_str,
            "source": "desktop",
            "route": "SmartRouter",
            "duration": f"{data.get('metrics', {}).get('total_ms', 0):.0f} ms",
            "message": msg,
            "timestamp": time.strftime("%H:%M:%S"),
            "verified": state_str == "SUCCESS",
        }
        self.activity_model.add_task(task_entry)
        self.state.add_recent_task(task_entry)

        # Ensure any open_app action is focused / brought to front on interactive desktop
        tool_res = data.get("tool_result") or {}
        t_name = tool_res.get("tool_name") or data.get("tool") or ""
        if t_name == "open_app" or ("is open" in msg.lower() and state_str == "SUCCESS"):
            app_data = tool_res.get("data") or {}
            target = app_data.get("target") or ""
            name = app_data.get("name") or ""
            process_names = app_data.get("process_names") or ()
            self._ensure_app_active(name, target, process_names)
        elif t_name == "list_directory" and state_str == "SUCCESS":
            folder_path = (tool_res.get("data") or {}).get("path")
            if folder_path:
                try:
                    import subprocess
                    subprocess.Popen(["explorer.exe", str(folder_path)])
                except Exception:
                    pass

    def _ensure_app_active(self, name: str, target: str, process_names: Any) -> None:
        def _bg():
            try:
                from jarvis.tools.system.native import bring_to_front
                procs = tuple(process_names) if process_names else ()
                # 1. Check if window already exists and bring to front
                if bring_to_front(procs, name):
                    logger.info("Brought app window to front from UI: %s", name)
                    return

                # 2. If not visible yet, launch it directly from this UI process (which is running on Default desktop)
                logger.info("Ensuring app launch from UI: %s -> %s", name, target)
                if "explorer.exe" in str(target).lower() or name.lower() in ("explorer", "file explorer"):
                    import subprocess
                    folder = str(target) if str(target).startswith("shell:") else "shell:MyComputerFolder"
                    subprocess.Popen(["explorer.exe", folder])
                elif target:
                    if str(target).startswith(("http://", "https://", "ms-", "shell:")):
                        import os
                        os.startfile(target)
                    elif any(b in str(target).lower() for b in ("chrome.exe", "msedge.exe", "brave.exe", "firefox.exe")):
                        import subprocess
                        subprocess.Popen([target, "--new-window"])
                    else:
                        import os, subprocess
                        try:
                            os.startfile(target)
                        except Exception:
                            subprocess.Popen([target])
                time.sleep(0.4)
                bring_to_front(procs, name)
            except Exception as exc:
                logger.warning("Failed to ensure app active from UI: %s", exc)
        import threading
        threading.Thread(target=_bg, daemon=True).start()

    def _on_ping_updated(self, ping: int) -> None:
        self.state.update_metrics(self.state.cpuPercent, self.state.ramPercent, self.state.gpuPercent, self.state.vramMb, ping)

    def _on_metrics_sampled(self, cpu: float, ram: float, gpu: float, vram: float) -> None:
        self.state.update_metrics(cpu, ram, gpu, vram, self.state.pingMs)
