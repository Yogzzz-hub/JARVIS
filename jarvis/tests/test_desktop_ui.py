"""Desktop UI: 3D meshes, conversation state, live answer text and QML that compiles."""
from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QUrl, Signal  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

QML_DIR = Path(__file__).resolve().parents[1] / "ui" / "qml"


@pytest.fixture(scope="module")
def qapp():
    return QGuiApplication.instance() or QGuiApplication([])


def test_hud_ring_mesh_has_one_quad_strip_per_dash():
    from jarvis.ui.geometry import hud_ring_mesh, torus_mesh

    vertices, indices, count = hud_ring_mesh(90, 96, dashes=4, gap=0.3, steps=5)
    assert count == 4 * 5 * 6
    assert len(vertices) == 4 * (5 + 1) * 2 * 6 * 4
    assert max(struct.unpack(f"<{count}I", indices)) < len(vertices) // 24
    floats = struct.unpack(f"<{len(vertices) // 4}f", vertices)
    radii = {round((floats[i] ** 2 + floats[i + 1] ** 2) ** 0.5, 3) for i in range(0, len(floats), 6)}
    assert radii == {90.0, 96.0}

    vertices, indices, count = torus_mesh(100, 2, rings=16, sides=8)
    assert count == 16 * 8 * 6 and len(vertices) == 17 * 9 * 24


def test_conversation_merges_the_streaming_answer(qapp):
    from jarvis.ui.state import JarvisUIState

    state = JarvisUIState()
    state.add_turn("user", "explain recursion")
    state.add_turn("assistant", "Recursion is", streaming=True)
    state.add_turn("assistant", "Recursion is a function calling itself.", streaming=True)
    state.add_turn("assistant", "Recursion is a function calling itself.", streaming=False, state="SUCCESS")
    turns = state.conversation
    assert [t["role"] for t in turns] == ["user", "assistant"]
    assert turns[-1]["text"] == "Recursion is a function calling itself." and not turns[-1]["streaming"]
    state.add_turn("user", "api_key: sk-abcdefghijklmnopqrstuvwx")
    assert "abcdefghijklmnop" not in state.conversation[-1]["text"]


def test_audio_level_follows_newest_bar(qapp):
    from jarvis.ui.state import JarvisUIState

    state = JarvisUIState()
    state.set_audio_levels([0.0] * 23 + [0.8])
    assert state.audioLevel == pytest.approx(0.8)


class FakeBridge(QObject):
    connectionChanged = Signal(str)
    eventReceived = Signal(object)
    responseReceived = Signal(dict)
    pingUpdated = Signal(int)

    def __init__(self):
        super().__init__()
        self.sent: list[str] = []

    def send_command(self, text):
        self.sent.append(text)

    def send_control(self, action):
        self.sent.append(action)


class FakeMetrics(QObject):
    metricsSampled = Signal(float, float, float, float)

    def set_interval(self, ms):
        pass


def test_controller_shows_partial_answers_and_ai_status(qapp, tmp_path):
    from jarvis.ui.controller import JarvisUIController
    from jarvis.ui.events import UIEvent, UIEventType
    from jarvis.ui.models import ActivityListModel
    from jarvis.ui.settings import UISettings
    from jarvis.ui.state import JarvisUIState

    state = JarvisUIState()
    settings = UISettings(tmp_path / "ui.json")
    settings.override("ui_3d", False)
    bridge = FakeBridge()
    controller = JarvisUIController(state=state, bridge=bridge, settings=settings,
                                    activity_model=ActivityListModel(), metrics=FakeMetrics())
    assert state.ui3d is False

    controller.sendCommand("explain recursion")
    controller._on_event_received(UIEvent(UIEventType.RESPONSE_PARTIAL, "r1", {"text": "Recursion is"}))
    assert state.response == "Recursion is" and state.conversation[-1]["streaming"]
    controller._on_response_received({"state": "SUCCESS", "message": "Recursion is a function calling itself.", "request_id": "r1"})
    assert state.conversation[-1]["text"] == "Recursion is a function calling itself."
    assert len(state.conversation) == 2

    controller._on_event_received(UIEvent(UIEventType.MODEL_STATE, "", {"reachable": False}))
    assert state.llmStatus == "OFFLINE"

    controller.toggleTalk()
    assert bridge.sent[-1] == "ptt_start" and state.isListening
    controller.toggleTalk()
    assert bridge.sent[-1] == "ptt_stop"

    controller.updateSetting("ui_3d", True)
    assert state.ui3d is True


def _qml_files():
    return sorted(p for p in QML_DIR.rglob("*.qml"))


@pytest.mark.parametrize("path", _qml_files(), ids=lambda p: str(p.relative_to(QML_DIR)))
def test_every_qml_file_compiles(qapp, path):
    import jarvis.ui.geometry  # noqa: F401  registers Jarvis3D
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    if path.name == "Theme.qml":
        pytest.skip("singleton without qmldir")
    engine = QQmlEngine()
    engine.addImportPath(str(QML_DIR))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
    if component.status() == QQmlComponent.Status.Error and any(
            "module \"QtQuick3D" in e.toString() and "not installed" in e.toString() for e in component.errors()):
        pytest.skip("Qt Quick 3D is not installed")
    assert component.status() == QQmlComponent.Status.Ready, [e.toString() for e in component.errors()]
