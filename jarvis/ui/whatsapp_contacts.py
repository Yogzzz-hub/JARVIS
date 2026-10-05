"""Dashboard -> WhatsApp -> Contacts: QML-facing client for the personal reply agent REST API."""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

logger = logging.getLogger("jarvis.ui.whatsapp_contacts")


class WhatsAppContactsClient(QObject):
    contactsChanged = Signal()
    selectedChanged = Signal()
    activityChanged = Signal()
    previewChanged = Signal()
    testResultChanged = Signal()
    historyChanged = Signal()
    statusChanged = Signal()
    busyChanged = Signal()
    noticeChanged = Signal()
    intelligenceChanged = Signal()
    holdoutChanged = Signal()
    _done = Signal(str, object)  # (kind, result) delivered on the UI thread

    def __init__(self, http_url: str = "http://127.0.0.1:8765", opener: Optional[Callable[..., Any]] = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.base = http_url.rstrip("/") + "/whatsapp/personal"
        self._opener = opener or urllib.request.urlopen
        self._contacts: list = []
        self._grants: list = []
        self._activity: list = []
        self._selected: dict = {}
        self._preview: dict = {}
        self._test: dict = {}
        self._history: list = []
        self._status = ""
        self._encryption = ""
        self._busy = 0
        self._notice = ""
        self._notice_error = False
        self._intelligence: dict = {}
        self._contact_brain: dict = {}
        self._holdout: list = []
        self._done.connect(self._on_done)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(400)
        self._refresh_timer.timeout.connect(self.refresh)

    # ------------------------------------------------------------------ properties
    @Property("QVariantList", notify=contactsChanged)
    def contacts(self) -> list:
        return self._contacts

    @Property("QVariantList", notify=contactsChanged)
    def grants(self) -> list:
        return self._grants

    @Property(str, notify=contactsChanged)
    def encryption(self) -> str:
        return self._encryption

    @Property("QVariantMap", notify=selectedChanged)
    def selected(self) -> dict:
        return self._selected

    @Property("QVariantList", notify=activityChanged)
    def activity(self) -> list:
        return self._activity

    @Property("QVariantMap", notify=previewChanged)
    def preview(self) -> dict:
        return self._preview

    @Property("QVariantMap", notify=testResultChanged)
    def testResult(self) -> dict:
        return self._test

    @Property("QVariantList", notify=historyChanged)
    def history(self) -> list:
        return self._history

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy > 0

    @Property(str, notify=noticeChanged)
    def notice(self) -> str:
        """Outcome of the last button (kept until the next one; the auto-reply status line is separate)."""
        return self._notice

    @Property(bool, notify=noticeChanged)
    def noticeError(self) -> bool:
        return self._notice_error

    @Property('QVariantMap', notify=intelligenceChanged)
    def intelligence(self) -> dict:
        return self._intelligence

    @Property('QVariantMap', notify=intelligenceChanged)
    def contactBrain(self) -> dict:
        return self._contact_brain

    @Property('QVariantList', notify=holdoutChanged)
    def holdoutCases(self) -> list:
        return self._holdout

    def _set_notice(self, text: str, error: bool = False) -> None:
        self._notice, self._notice_error = text, error
        self.noticeChanged.emit()

    @Slot()
    def clearNotice(self) -> None:
        self._set_notice("")

    # ------------------------------------------------------------------ HTTP plumbing
    def _request(self, kind: str, method: str, path: str, body: Optional[dict] = None, timeout: float = 60.0) -> None:
        self._busy += 1
        self.busyChanged.emit()

        def work() -> None:
            data = json.dumps(body).encode("utf-8") if body is not None else None
            req = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
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
                result = {"error": f"JARVIS backend unavailable ({exc})"}
            self._done.emit(kind, result)

        threading.Thread(target=work, daemon=True, name=f"wa-contacts-{kind}").start()

    @staticmethod
    def _q(contact_id: str) -> str:
        return urllib.parse.quote(contact_id, safe="")

    def _set_status(self, text: str) -> None:
        self._status = text
        self.statusChanged.emit()

    def _on_done(self, kind: str, result: Any) -> None:
        self._busy = max(0, self._busy - 1)
        self.busyChanged.emit()
        if isinstance(result, dict) and result.get("error"):
            self._set_notice(str(result["error"]), error=True)
            return
        if kind == "contacts":
            self._contacts = result.get("contacts", [])
            self._grants = result.get("grants", [])
            self._encryption = result.get("encryption", "")
            self._activity = result.get("activity", [])
            self.contactsChanged.emit()
            self.activityChanged.emit()
            if result.get("status_text"):
                self._set_status(result["status_text"])
        elif kind == "detail":
            self._selected = result
            self.selectedChanged.emit()
        elif kind == "preview":
            self._preview = result
            self.previewChanged.emit()
        elif kind == "test":
            self._test = result
            self.testResultChanged.emit()
        elif kind == "history":
            self._history = result.get("history", [])
            self.historyChanged.emit()
        elif kind == 'intelligence':
            self._intelligence = result
            self.intelligenceChanged.emit()
        elif kind == 'contact_brain':
            self._contact_brain = result.get('contact') or {}
            self.intelligenceChanged.emit()
        elif kind == 'holdout':
            self._holdout = result.get('cases', [])
            self.holdoutChanged.emit()
        elif kind.startswith('holdout_rating:'):
            self._set_notice('Review saved.' if result.get('status') == 'SAVED' else 'Review case unavailable.',
                             error=result.get('status') != 'SAVED')
            self.loadHoldout(kind.split(':', 1)[1])
        elif kind.startswith('evaluate:'):
            self._set_notice('Evaluation complete; owner review cases are ready.')
            self.loadHoldout(kind.split(':', 1)[1])
        elif kind in ('brain_start', 'brain_cancel'):
            self._intelligence['latest_job'] = result
            self.intelligenceChanged.emit()
            self._set_notice('Intelligence build ' + result.get('status', '').lower() + '.')
        else:
            self._set_notice(self._describe(kind, result if isinstance(result, dict) else {}))
            self.refresh()
            cid = (self._selected.get("contact") or {}).get("contact_id") if self._selected else None
            if cid:
                self.select(cid)

    _MODE_WORDS = {"OFF": "Replies are off", "SUGGEST_ONLY": "Suggest only: drafts appear here, nothing is sent",
                   "ASK_BEFORE_SEND": "Ask before send: each draft waits for your OK"}

    def _describe(self, kind: str, r: dict) -> str:
        """A sentence for what the button did (the API returns data, not always a message)."""
        if r.get("message"):
            return str(r["message"])
        if kind in ("import", "rebuild"):
            n = int(r.get("messages_analyzed") or 0)
            if n == 0:
                return ("Nothing to learn from yet: JARVIS has no messages from you to this person. Import a chat export, "
                        "or chat on WhatsApp for a while and press Refresh profile.")
            return f"Learned from {n} of your messages ({r.get('examples', 0)} reply examples); profile v{r.get('profile_version', 0)}."
        if kind == "mode":
            return self._MODE_WORDS.get(str(r.get("mode")), "Mode updated.") + "."
        if kind == "clear":
            return "Style profile deleted. Imported chats stay unless you delete them too."
        if kind == "add":
            return f"Added {r.get('display_name') or 'the contact'}."
        return "Done."

    # ------------------------------------------------------------------ slots used by QML
    @Slot()
    def refresh(self) -> None:
        self._request("contacts", "GET", "/contacts")
        self.refreshIntelligence()

    @Slot()
    def refreshIntelligence(self) -> None:
        self._request('intelligence', 'GET', '/intelligence/overview')

    @Slot()
    def loadAllHistory(self) -> None:
        self._request('brain_start', 'POST', '/intelligence/jobs', {'scope': 'ALL'})

    @Slot(str)
    def refreshPersonIntelligence(self, contact_id: str) -> None:
        self._request('brain_start', 'POST', '/intelligence/jobs',
                      {'scope': 'CONTACT', 'contact_id': contact_id})

    @Slot(str)
    def cancelIntelligenceJob(self, job_id: str) -> None:
        self._request('brain_cancel', 'POST', f'/intelligence/jobs/{self._q(job_id)}/cancel', {})

    @Slot(str)
    def loadContactIntelligence(self, contact_id: str) -> None:
        self._request('contact_brain', 'GET', f'/intelligence/contacts/{self._q(contact_id)}')

    @Slot(str)
    def loadHoldout(self, contact_id: str) -> None:
        self._request('holdout', 'GET', f'/contacts/{self._q(contact_id)}/style/holdout-review')

    @Slot(str)
    def evaluatePerson(self, contact_id: str) -> None:
        self._request('evaluate:' + contact_id, 'POST',
                      f'/contacts/{self._q(contact_id)}/style/evaluate', {}, timeout=180)

    @Slot(str, str, str, str)
    def rateHoldout(self, contact_id: str, case_id: str, rating: str, dimensions_json: str) -> None:
        try:
            dimensions = json.loads(dimensions_json or '{}')
        except ValueError:
            self._set_notice('Review dimensions are invalid.', error=True)
            return
        self._request('holdout_rating:' + contact_id, 'POST',
                      f'/contacts/{self._q(contact_id)}/style/holdout-review/{self._q(case_id)}',
                      {'rating': rating, **dimensions})

    @Slot(int, str)
    def draftFeedback(self, reply_id: int, kind: str) -> None:
        self._request('draft_feedback', 'POST', f'/replies/{int(reply_id)}/feedback', {'kind': kind})

    @Slot(str)
    def select(self, contact_id: str) -> None:
        self._request("detail", "GET", f"/contacts/{self._q(contact_id)}")
        self.loadContactIntelligence(contact_id)
        self.loadHoldout(contact_id)
        self._preview, self._test = {}, {}
        self.previewChanged.emit()
        self.testResultChanged.emit()

    @Slot(str, str)
    def addContact(self, contact: str, display_name: str) -> None:
        self._request("add", "POST", "/contacts", {"contact": contact, "display_name": display_name})

    @Slot(str, str, str, str)
    def importChatFile(self, contact_id: str, file_url: str, display_name: str, owner_name: str) -> None:
        path = urllib.parse.unquote(file_url.replace("file:///", "").replace("file://", "")) if file_url.startswith("file:") else file_url
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            self._set_status(f"Could not read the export: {exc}")
            return
        self._request("import", "POST", f"/contacts/{self._q(contact_id)}/import",
                      {"export_text": text, "display_name": display_name, "owner_name": owner_name}, timeout=300)

    @Slot(str, str)
    def importFromHistory(self, contact_id: str, display_name: str) -> None:
        self._request("import", "POST", f"/contacts/{self._q(contact_id)}/import",
                      {"from_inbox": True, "display_name": display_name}, timeout=300)

    @Slot(str)
    def rebuild(self, contact_id: str) -> None:
        self._request("rebuild", "POST", f"/contacts/{self._q(contact_id)}/rebuild", {})

    @Slot(str)
    def previewStyle(self, contact_id: str) -> None:
        self._request("preview", "GET", f"/contacts/{self._q(contact_id)}/preview")

    @Slot(str, str)
    def testReply(self, contact_id: str, text: str) -> None:
        if text.strip():
            self._request("test", "POST", f"/contacts/{self._q(contact_id)}/test", {"text": text})

    @Slot(str, str, float)
    def setMode(self, contact_id: str, mode: str, minutes: float) -> None:
        self.setModeWithNote(contact_id, mode, minutes, "")

    @Slot(str, str, float, str)
    def setModeWithNote(self, contact_id: str, mode: str, minutes: float, note: str) -> None:
        body = {"mode": mode, "minutes": minutes if minutes > 0 else None, "note": note.strip()}
        self._request("mode", "POST", f"/contacts/{self._q(contact_id)}/mode", body)

    @Slot(float)
    def enableEveryone(self, minutes: float) -> None:
        self.enableEveryoneWithNote(minutes, "")

    @Slot(float, str)
    def enableEveryoneWithNote(self, minutes: float, note: str) -> None:
        self._request("everyone", "POST", "/everyone", {"minutes": minutes, "note": note.strip()})

    @Slot(str)
    def stop(self, contact_id: str) -> None:
        self._request("stop", "POST", f"/contacts/{self._q(contact_id)}/stop", {})

    @Slot()
    def stopAll(self) -> None:
        self._request("stop_all", "POST", "/stop_all", {})

    @Slot(str)
    def clearProfile(self, contact_id: str) -> None:
        self._request("clear", "DELETE", f"/contacts/{self._q(contact_id)}/profile")

    @Slot(str)
    def loadHistory(self, contact_id: str) -> None:
        self._request("history", "GET", f"/contacts/{self._q(contact_id)}/history")

    @Slot(str, str)
    def feedback(self, contact_id: str, kind: str) -> None:
        self._request("feedback", "POST", f"/contacts/{self._q(contact_id)}/feedback", {"kind": kind})

    @Slot(int, str, bool)
    def approve(self, reply_id: int, text: str, mark_good: bool) -> None:
        self._request("approve", "POST", f"/replies/{reply_id}/approve", {"text": text or None, "mark_good": mark_good})

    @Slot(int)
    def reject(self, reply_id: int) -> None:
        self._request("reject", "POST", f"/replies/{reply_id}/reject", {})

    # ------------------------------------------------------------------ live events from the backend
    def on_backend_event(self, name: str, payload: dict) -> None:
        if not name.startswith("whatsapp.personal."):
            return
        if name == "whatsapp.personal.activity":
            self._activity = [payload] + self._activity[:99]
            self.activityChanged.emit()
        if name == 'whatsapp.personal.ingestion':
            self._intelligence['latest_job'] = payload
            self.intelligenceChanged.emit()
            if payload.get('status') in ('COMPLETE', 'FAILED', 'CANCELLED'):
                self.refreshIntelligence()
        self._refresh_timer.start()
