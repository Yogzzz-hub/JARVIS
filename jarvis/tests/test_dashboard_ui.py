"""Dashboard: every page loads without QML errors, buttons leave a visible result, and the memory / diagnostics
pages show real data from the gateway."""
from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path

import pytest

PySide6 = pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _resp(body):
    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass
    return R(json.dumps(body).encode())


def _pump(app, client, limit=5.0):
    t = time.time()
    while (client.busy or time.time() - t < 0.05) and time.time() - t < limit:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def test_every_page_loads_without_qml_errors():
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    from jarvis.ui.bridge import JarvisUIBridge
    from jarvis.ui.controller import JarvisUIController
    from jarvis.ui.dashboard_client import DashboardClient
    from jarvis.ui.metrics import MetricsSampler
    from jarvis.ui.models import ActivityListModel
    from jarvis.ui.settings import UISettings
    from jarvis.ui.state import JarvisUIState
    from jarvis.ui.whatsapp_contacts import WhatsAppContactsClient

    app = _app()
    settings = UISettings()
    settings.override("ui_3d", False)
    state = JarvisUIState()
    ctl = JarvisUIController(state=state, bridge=JarvisUIBridge(ws_url="ws://127.0.0.1:1/ws", http_url="http://127.0.0.1:1"),
                             settings=settings, activity_model=ActivityListModel(), metrics=MetricsSampler(interval_ms=100000))
    engine = QQmlApplicationEngine()
    qml = Path(__file__).resolve().parents[1] / "ui" / "qml"
    engine.addImportPath(str(qml))
    errors: list[str] = []
    engine.warnings.connect(lambda ws: errors.extend(w.toString() for w in ws))
    ctx = engine.rootContext()
    offline = lambda req, timeout=0: (_ for _ in ()).throw(OSError("offline"))  # noqa: E731
    for name, obj in (("uiState", state), ("uiController", ctl), ("uiActivityModel", ActivityListModel()),
                      ("uiSettings", settings), ("uiWhatsApp", WhatsAppContactsClient(opener=offline)),
                      ("uiDashboard", DashboardClient(opener=offline))):
        ctx.setContextProperty(name, obj)
    engine.load(QUrl.fromLocalFile(str(qml / "Main.qml")))
    roots = engine.rootObjects()
    assert roots, errors
    import shiboken6
    from PySide6.QtQuick import QQuickWindow
    window = shiboken6.wrapInstance(shiboken6.getCppPointer(roots[0])[0], QQuickWindow)
    stack = window.findChild(object, "pageStack")
    for i in range(10):
        stack.setProperty("currentIndex", i)
        t = time.time()
        while time.time() - t < 0.15:
            app.processEvents()
    real = [e for e in errors if "propagateSize" not in e]
    assert real == []


def test_whatsapp_button_results_are_not_overwritten_by_the_refresh():
    from jarvis.ui.whatsapp_contacts import WhatsAppContactsClient

    app = _app()

    def opener(req, timeout=0):
        path = req.full_url.split("/whatsapp/personal", 1)[1]
        if path == "/contacts":
            return _resp({"contacts": [], "status_text": "WhatsApp auto-reply is off."})
        if path.endswith("/mode"):
            return _resp({"status": "OK", "mode": "SUGGEST_ONLY"})
        if path.endswith("/rebuild"):
            return _resp({"messages_analyzed": 0, "profile_version": 0})
        return _resp({})
    c = WhatsAppContactsClient(http_url="http://x", opener=opener)
    c.setMode("91900@s.whatsapp.net", "SUGGEST_ONLY", 0)
    _pump(app, c)
    assert c.notice.startswith("Suggest only") and c.status == "WhatsApp auto-reply is off."
    c.rebuild("91900@s.whatsapp.net")
    _pump(app, c)
    assert c.notice.startswith("Nothing to learn from yet")


def test_backend_down_is_reported_not_silent():
    from jarvis.ui.dashboard_client import DashboardClient

    app = _app()
    c = DashboardClient(opener=lambda req, timeout=0: (_ for _ in ()).throw(OSError("refused")))
    c.refreshMemory()
    _pump(app, c)
    assert c.noticeError and "not running" in c.notice and c.noticePage == "memory"


def test_memory_api_lists_and_forgets_real_facts(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from jarvis.core.gateway import dashboard_api
    from jarvis.tools.system.everyday_tools import PersonalStore

    store = PersonalStore(tmp_path / "j.db")
    monkeypatch.setattr(dashboard_api, "_store", lambda: store)
    api = FastAPI()
    dashboard_api.register(api)
    tc = TestClient(api)
    assert tc.post("/dashboard/memory/facts", json={"fact": "my car is on level 2"}).status_code == 200
    store.add_todo("buy milk")
    snap = tc.get("/dashboard/memory").json()
    assert [f["fact"] for f in snap["facts"]] == ["my car is on level 2"] and snap["todos"][0]["text"] == "buy milk"
    fid = snap["facts"][0]["id"]
    assert tc.delete(f"/dashboard/memory/facts/{fid}").json()["message"] == "Forgotten."
    assert tc.delete(f"/dashboard/memory/facts/{fid}").status_code == 404
    assert tc.get("/dashboard/memory").json()["facts"] == []
