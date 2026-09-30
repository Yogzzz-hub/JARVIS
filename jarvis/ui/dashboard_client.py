"""Dashboard pages -> gateway REST (memory, diagnostics). Requests run off the UI thread; results come back as
Qt properties, and every action leaves a visible notice so a click never looks like it did nothing."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

from PySide6.QtCore import Property, QObject, Signal, Slot


class DashboardClient(QObject):
    memoryChanged = Signal()
    diagnosticsChanged = Signal()
    noticeChanged = Signal()
    busyChanged = Signal()
    _done = Signal(str, object)

    def __init__(self, http_url: str = "http://127.0.0.1:8765", opener: Optional[Callable[..., Any]] = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.base = http_url.rstrip("/") + "/dashboard"
        self._opener = opener or urllib.request.urlopen
        self._memory: dict = {"facts": [], "todos": [], "shortcuts": []}
        self._diagnostics: list = []
        self._diag_ms = 0
        self._notice = ""
        self._notice_error = False
        self._notice_page = ""
        self._busy = 0
        self._done.connect(self._on_done)

    @Property("QVariantMap", notify=memoryChanged)
    def memory(self) -> dict:
        return self._memory

    @Property("QVariantList", notify=diagnosticsChanged)
    def diagnostics(self) -> list:
        return self._diagnostics

    @Property(int, notify=diagnosticsChanged)
    def diagnosticsMs(self) -> int:
        return self._diag_ms

    @Property(str, notify=noticeChanged)
    def notice(self) -> str:
        return self._notice

    @Property(bool, notify=noticeChanged)
    def noticeError(self) -> bool:
        return self._notice_error

    @Property(str, notify=noticeChanged)
    def noticePage(self) -> str:
        """Which page the notice belongs to ("memory" / "diagnostics"), so it only shows there."""
        return self._notice_page

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy > 0

    def _set_notice(self, text: str, error: bool = False, page: str = "") -> None:
        self._notice, self._notice_error = text, error
        if page:
            self._notice_page = page
        self.noticeChanged.emit()

    @Slot()
    def clearNotice(self) -> None:
        self._set_notice("")

    def _request(self, kind: str, method: str, path: str, body: Optional[dict] = None, timeout: float = 60.0) -> None:
        self._busy += 1
        self.busyChanged.emit()

        def work() -> None:
            data = json.dumps(body).encode("utf-8") if body is not None else None
            req = urllib.request.Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
            try:
                with self._opener(req, timeout=timeout) as resp:
                    result = json.loads(resp.read().decode("utf-8") or "{}")
            except urllib.error.HTTPError as exc:
                try:
                    detail = json.loads(exc.read().decode("utf-8")).get("detail", str(exc))
                except Exception:
                    detail = str(exc)
                result = {"error": detail}
            except Exception as exc:
                result = {"error": f"JARVIS is not running yet ({type(exc).__name__}). Start it with start.bat."}
            self._done.emit(kind, result)

        threading.Thread(target=work, daemon=True, name=f"dashboard-{kind}").start()

    def _on_done(self, kind: str, result: Any) -> None:
        self._busy = max(0, self._busy - 1)
        self.busyChanged.emit()
        if isinstance(result, dict) and result.get("error"):
            self._set_notice(str(result["error"]), error=True, page="diagnostics" if kind == "diagnostics" else "memory")
            return
        if kind == "memory":
            self._memory = {k: result.get(k, []) for k in ("facts", "todos", "shortcuts")}
            self.memoryChanged.emit()
        elif kind == "diagnostics":
            self._diagnostics = result.get("checks", [])
            self._diag_ms = int(result.get("ms", 0))
            self.diagnosticsChanged.emit()
            bad = sum(1 for c in self._diagnostics if c.get("status") == "FAIL")
            warn = sum(1 for c in self._diagnostics if c.get("status") == "WARN")
            self._set_notice(page="diagnostics", text=f"Checked {len(self._diagnostics)} items in {self._diag_ms} ms: "
                             f"{bad} failed, {warn} need attention.", error=bad > 0)
        else:
            self._set_notice(result.get("message", "Done."), page="memory")
            self.refreshMemory()

    @Slot()
    def refreshMemory(self) -> None:
        self._request("memory", "GET", "/memory")

    @Slot(str)
    def addFact(self, fact: str) -> None:
        if fact.strip():
            self._request("add_fact", "POST", "/memory/facts", {"fact": fact.strip()})

    @Slot(int)
    def forgetFact(self, fact_id: int) -> None:
        self._request("forget", "DELETE", f"/memory/facts/{int(fact_id)}")

    @Slot(str)
    def deleteShortcut(self, phrase: str) -> None:
        self._request("shortcut", "DELETE", "/memory/shortcuts/" + urllib.parse.quote(phrase, safe=""))

    @Slot()
    def runDiagnostics(self) -> None:
        self._set_notice("Running diagnostics...", page="diagnostics")
        self._request("diagnostics", "GET", "/diagnostics", timeout=120)
