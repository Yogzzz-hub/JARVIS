"""What JARVIS actually did, so follow-up questions get true answers ("who did you send that to?").

Every finished command is recorded (tool, key arguments, outcome, the reply JARVIS gave). Follow-ups are
answered from this record deterministically, and the chat model receives the last few entries as context,
so "what did you just do", "did it work", "what was the message" are never guessed.
"""
from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

_SKIP_TOOLS = {"recent_actions", "stop_speaking", "stop_task", "cancel_task", "show_dashboard", "clarify", "unresolved"}
CHAT = "_chat"  # a spoken/written answer, not an action (kept only for "what did you say")
_SEND_TOOLS = ("send_whatsapp_message", "reply_whatsapp_message", "reply_whatsapp_all", "send_whatsapp_bulk", "send_email",
               "android_quick_action", "localsend_text")


@dataclass
class ActionEntry:
    at: float
    tool: str
    args: dict[str, Any]
    state: str
    reply: str
    request: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.state in ("SUCCESS", "SENT", "VERIFIED")

    def when(self, now: Optional[float] = None) -> str:
        secs = max(0, int((now or time.time()) - self.at))
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{secs // 60} minute{'s' if secs >= 120 else ''} ago"
        return time.strftime("at %I:%M %p", time.localtime(self.at)).replace(" 0", " ")

    def describe(self) -> str:
        a = self.args
        if self.tool in ("send_whatsapp_message", "reply_whatsapp_message"):
            who = a.get("recipient") or a.get("contact") or "someone"
            text = a.get("message") or a.get("instruction") or ""
            what = f'the WhatsApp message "{text}" to {who}' if text else f"a WhatsApp message to {who}"
            return f"{'sent' if self.ok else 'tried to send'} {what}"
        if self.tool == "open_app":
            return f"{'opened' if self.ok else 'tried to open'} {a.get('name') or ' and '.join(a.get('apps') or [])}"
        if self.tool == "compound":
            from jarvis.core.commands.introspection import tool_words
            return f"ran {len(a.get('steps') or [])} steps: {', '.join(tool_words(s) for s in a.get('steps') or [])}"
        from jarvis.core.commands.introspection import tool_words
        name = tool_words(self.tool)
        detail = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in list(a.items())[:3] if v not in (None, "", [], {}))
        return f"{'did' if self.ok else 'tried'}: {name}" + (f" ({detail})" if detail else "")


class ActionLog:
    def __init__(self, size: int = 30) -> None:
        self._items: deque[ActionEntry] = deque(maxlen=size)
        self._lock = threading.Lock()

    def record(self, tool: str, args: Optional[dict] = None, state: str = "", reply: str = "", request: str = "",
               **extra: Any) -> None:
        if not tool or tool in _SKIP_TOOLS:
            return
        clean = {k: v for k, v in (args or {}).items() if not str(k).startswith("_") and len(str(v)) < 400}
        with self._lock:
            self._items.append(ActionEntry(time.time(), tool, clean, state, (reply or "")[:400], (request or "")[:200], extra))

    def recent(self, n: int = 5, within_s: float = 3 * 3600) -> list[ActionEntry]:
        now = time.time()
        with self._lock:
            items = [e for e in self._items if now - e.at <= within_s]
        return items[-n:]

    def last(self, tools: tuple[str, ...] = (), include_chat: bool = False) -> Optional[ActionEntry]:
        for e in reversed(self.recent(30)):
            if e.tool == CHAT and not include_chat:
                continue
            if not tools or e.tool in tools:
                return e
        return None

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def context_lines(self, n: int = 5) -> list[str]:
        now = time.time()
        return [f"{e.when(now)}: {e.describe()} ({'succeeded' if e.ok else e.state.lower() or 'unknown'})"
                for e in self.recent(n, within_s=1800) if e.tool != CHAT]


_LOG = ActionLog()


def get_action_log() -> ActionLog:
    return _LOG


# ------------------------------------------------------------------ follow-up questions
_U = r"(?:you|u|jarvis)"
FOLLOWUP = re.compile(
    rf"^(?:to\s+whom|who)\s+(?:did|have|has|was|were)\s+(?:{_U}\s+)?(?:just\s+)?(?:sen[dt]|message[d]?|text(?:ed)?|reply|replied)"
    rf"(?:\s+(?:it|that|this|the\s+message|the\s+msg|a\s+message))?(?:\s+(?:to|sent\s+to))?"
    rf"|^(?:to\s+whom|who)\s+{_U}\s+(?:have\s+|has\s+)?(?:just\s+)?(?:sen[dt]|messaged|texted)(?:\s+(?:it|that))?(?:\s+to)?"
    rf"|^who\s+(?:was|is)\s+(?:it|that|the\s+message)\s+(?:sent\s+)?(?:to|for)"
    rf"|^what\s+(?:did|have)\s+{_U}\s+(?:actually\s+|really\s+|even\s+)?(?:just\s+)?(?:send|sent|write|wrote|type|typed|say|said|reply|replied|do|done|open|opened|close|closed|set|change|changed|play|played|turn|turned|search|searched|make|made|put)"
    rf"|^what\s+(?:was|is)\s+(?:the|that|your|my)\s+(?:message|msg|reply|last\s+(?:message|reply|action|command))"
    rf"|^what\s+(?:just\s+)?happened|^what\s+was\s+that"
    rf"|^(?:did|has|was)\s+(?:it|that|the\s+message|the\s+msg|my\s+message|that\s+(?:message|msg|text|mail|email|reply))\s+"
    rf"(?:(?:actually|really|definitely|even|successfully|properly)\s+)?(?:get\s+|been\s+)?(?:sen[dt]|delivered|work|go\s+through|done)"
    rf"|^did\s+{_U}\s+(?:send|sent|do|open|finish|reply)\s+(?:it|that|the\s+message)"
    rf"|^(?:repeat\s+that|say\s+that\s+again|come\s+again|what\s+did\s+{_U}\s+say)"
    rf"|^where\s+did\s+{_U}\s+(?:save|put|send)\s+(?:it|that)"
    rf"|^(?:was|were|is|has)\s+(?:that|the|my|it)\s*(?:message|msg|mail|email|screenshot|file|note|reminder)?\s+(?:been\s+)?(?:actually\s+|really\s+|even\s+|successfully\s+)?(?:delivered|sent|saved|done|created|set)"
    rf"|^did\s+{_U}\s+(?:actually\s+|really\s+|already\s+)?(?:send|deliver)\s+(?:my|the|that|this)\s+(?:message|msg|text|whatsapp)(?:\s+to\s+[a-z .'-]{{1,30}})?"
    rf"|^what\s+did\s+{_U}\s+(?:just\s+)?say"
    rf"|^did\s+{_U}\s+(?:actually|really)?\s*(?:send|do|save|open|finish)\s+(?:it|that|the\s+\w+)(?:\s+or\s+not)?"
    rf"|^who\s+(?:got|received|gets)\s+(?:that|the|it|my)?\s*(?:message|msg|text)?"
    rf"|^who\s+was\s+(?:that|the)\s+(?:message|msg|text)\s+for"
    rf"|^what\s+was\s+the\s+last\s+thing\s+{_U}\s+did|^(?:the\s+)?last\s+thing\s+{_U}\s+did"
    rf"|^what\s+(?:message|msg|text|mail|email)\s+did\s+{_U}\s+(?:just\s+)?(?:send|sent|write|type)"
    rf"|^did\s+(?:that|it)\s+work"
    rf"|^who\s+(?:was|did)\s+(?:the|my|your)\s+(?:last|latest|previous)\s+(?:message|msg|text|whatsapp)\s+(?:sent\s+|go\s+)?(?:to|for)"
    rf"|^did\s+{_U}\s+(?:already\s+|actually\s+)?(?:message|text|ping|reply\s+to)\s+[a-z .'-]{{1,30}}?(?:\s+(?:already|yet))?$"
    rf"|^(?:say|repeat)\s+(?:that|it)\s+(?:again|one\s+more\s+time|once\s+more|1\s+more\s+time)|^(?:pardon|sorry)\s*\??$|^come\s+again"
    rf"|^did\s+my\s+(?:message|msg|text|whatsapp|mail|email)\s+(?:to\s+[a-z .'-]{{1,30}}?\s+)?(?:go(?:\s+through|\s+out)?|get\s+(?:sent|delivered|there|through)|send|reach|arrive|land)$"
    rf"|^who\s+did\s+{_U}\s+(?:just\s+)?(?:message|text|send\s+(?:it|that|a\s+message)\s+to|reply\s+to)"
    rf"|^what\s+(?:actually\s+|exactly\s+|just\s+)?failed|^what\s+did\s+{_U}\s+(?:retry|re-?try|skip|undo|redo|roll\s+back|"
    rf"verify|check|change|fix)\b|^why\s+did\s+(?:it|that|the\s+task|the\s+command)\s+fail"
    rf"|^which\s+(?:step|action|part)\s+failed|^what\s+went\s+wrong")


def is_followup(text: str) -> bool:
    t = re.sub(r"\s+", " ", (text or "").lower()).strip(" .!?")
    t = re.sub(r"^(?:hey\s+|ok\s+)?jarvis,?\s+", "", t)
    t = re.sub(r"^(?:(?:and|so|wait|but|then|ok|okay|hold\s+on|hang\s+on|um+|uh+|hey|please|jarvis|sorry|pardon|excuse\s+me|"
               r"(?:can|could|would|will)\s+(?:you|u)(?:\s+please)?)\s*,?\s+)+", "", t)
    return bool(FOLLOWUP.search(t))


def answer_followup(text: str, log: Optional[ActionLog] = None) -> str:
    log = log or _LOG
    t = re.sub(r"\s+", " ", (text or "").lower()).strip(" .!?")
    last = log.last() or log.last(include_chat=True)
    if last is None:
        return "I haven't done anything for you in the last few hours."
    if re.search(r"\b(?:what\s+(?:exactly\s+|actually\s+)?failed|why\s+did\s+(?:it|that|the\s+task)\s+fail|which\s+step\s+failed|what\s+went\s+wrong)\b", t):
        if last.ok:
            return f"The last action ({last.describe()}) succeeded without errors."
        return f"{last.describe()} failed: {last.reply or last.extra.get('reason') or last.state.lower()}."
    if re.search(r"\b(?:repeat|say (?:that|it) (?:again|one more time|once more)|come again|pardon|what did (?:you|u|jarvis) say)\b", t):
        said = log.last(include_chat=True)
        return said.reply or f"I {said.describe()}."
    if re.search(r"\b(?:to whom|who)\b.*\b(?:send|sent|message|messaged|text|texted|reply|replied|to|for)\b", t):
        sent = log.last(_SEND_TOOLS)
        if sent is None:
            return "I haven't sent any messages recently."
        who = sent.args.get("recipient") or sent.args.get("contact") or "someone"
        text_ = sent.args.get("message") or ""
        state = "" if sent.ok else f" It didn't go through ({sent.state.lower()})."
        note = (" That was addressed to 'Me' - your own chat, not another person. Sorry, I misread your question."
                if str(who).strip().lower() in ("me", "myself", "you") else "")
        return f"I sent it to {who} {sent.when()}" + (f': "{text_}".' if text_ else ".") + state + note
    if re.search(r"\b(?:message|msg|send|sent|write|wrote|type|typed)\b", t) and not re.search(r"\bdid (?:it|that)\b", t):
        sent = log.last(_SEND_TOOLS)
        if sent is not None:
            who = sent.args.get("recipient") or "someone"
            return f'I sent "{sent.args.get("message") or sent.reply}" to {who} {sent.when()}.'
    if re.search(r"\b(?:did|has|was)\b.*\b(?:sent|send|delivered|work|go through|done|finish)\b", t):
        return (f"Yes - I {last.describe()} {last.when()}." if last.ok
                else f"No - I {last.describe()}, but it {last.state.lower() or 'did not finish'}: {last.reply}")
    if t.startswith("where"):
        path = next((v for v in last.args.values() if isinstance(v, str) and ("\\" in v or "/" in v)), "")
        return f"{last.reply or last.describe()}" + (f" It's at {path}." if path and path not in last.reply else "")
    return f"I {last.describe()} {last.when()}." + (f" {last.reply}" if last.reply and last.reply not in last.describe() else "")
