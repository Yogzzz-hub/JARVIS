"""Comprehensive unit tests for JARVIS Desktop UI components."""
from __future__ import annotations

import unittest
from jarvis.ui.events import (
    AssistantState,
    ConnectionState,
    UIEvent,
    UIEventType,
    redact_sensitive_text,
)
from jarvis.ui.settings import UISettings
from jarvis.ui.state import JarvisUIState
from jarvis.ui.models import ActivityListModel


class TestJarvisUIEvents(unittest.TestCase):
    def test_redaction(self):
        self.assertEqual(redact_sensitive_text("api_key: abcdefghijklmnop"), "api_key: [REDACTED]")
        self.assertEqual(redact_sensitive_text("token = secret_token_1234567"), "token: [REDACTED]")
        self.assertEqual(redact_sensitive_text("Normal text without secret"), "Normal text without secret")

    def test_ui_event_creation(self):
        ev = UIEvent(event_type=UIEventType.JARVIS_READY, request_id="req1", payload={"foo": "bar"})
        self.assertEqual(ev.event_type, UIEventType.JARVIS_READY)
        self.assertEqual(ev.request_id, "req1")
        self.assertEqual(ev.payload["foo"], "bar")


class TestJarvisUIState(unittest.TestCase):
    def setUp(self):
        self.state = JarvisUIState()

    def test_initial_state(self):
        self.assertEqual(self.state.connectionStatus, ConnectionState.OFFLINE.value)
        self.assertEqual(self.state.assistantState, AssistantState.IDLE.value)
        self.assertFalse(self.state.isListening)
        self.assertFalse(self.state.isSpeaking)

    def test_state_transitions(self):
        self.state.set_assistant_state(AssistantState.LISTENING.value)
        self.assertTrue(self.state.isListening)
        self.state.set_assistant_state(AssistantState.SPEAKING.value)
        self.assertTrue(self.state.isSpeaking)
        self.assertFalse(self.state.isListening)

    def test_confirmation_ticket_binding(self):
        ticket = {"ticket_id": "tkt_123", "target": "Delete DB", "secret_key": "abc12345678"}
        self.state.set_confirmation(ticket)
        self.assertEqual(self.state.assistantState, AssistantState.WAITING_CONFIRMATION.value)
        self.assertEqual(self.state.confirmationTicket["ticket_id"], "tkt_123")
        self.state.clear_confirmation()
        self.assertEqual(self.state.confirmationTicket, {})

    def test_metrics_updates_and_sparklines(self):
        self.state.update_metrics(cpu=25.5, ram=48.2, gpu=12.0, vram=512.0, ping=5)
        self.assertEqual(self.state.cpuPercent, 25.5)
        self.assertEqual(self.state.ramPercent, 48.2)
        self.assertEqual(self.state.gpuPercent, 12.0)
        self.assertEqual(self.state.pingMs, 5)

        cpu_hist = self.state.getCpuHistory()
        self.assertEqual(len(cpu_hist), 60)
        self.assertEqual(cpu_hist[-1], 25.5)

    def test_recent_tasks_bounded(self):
        for i in range(60):
            self.state.add_recent_task({"request_id": f"req_{i}", "text": f"Task {i}"})
        self.assertEqual(len(self.state.recentTasks), 50)
        self.assertEqual(self.state.recentTasks[0]["request_id"], "req_59")


class TestJarvisUISettings(unittest.TestCase):
    def test_default_settings(self):
        settings = UISettings()
        self.assertEqual(settings.get("overlay_location"), "bottom-center")
        self.assertTrue(settings.get("close_to_tray"))
        self.assertFalse(settings.get("low_resource_mode"))


class TestActivityListModel(unittest.TestCase):
    def test_model_insert_and_count(self):
        model = ActivityListModel()
        self.assertEqual(model.rowCount(), 0)
        model.add_task({
            "request_id": "t1",
            "text": "Open Chrome",
            "state": "SUCCESS",
            "source": "desktop",
            "route": "SmartRouter",
        })
        self.assertEqual(model.rowCount(), 1)
        model.clear()
        self.assertEqual(model.rowCount(), 0)


if __name__ == "__main__":
    unittest.main()
