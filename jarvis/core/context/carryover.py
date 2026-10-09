"""Conversation carry-over: turn a short follow-up into the full command it stands for.

People rarely repeat themselves. After "set volume to 30" they say "make it 60"; after "open notepad", "do the same
for calculator", "close it" or "no, paint"; after opening two apps, "close the first one"; after "send ravi I'm late",
"also to meena". This module keeps what the last few *executed* commands were and rewrites such a follow-up into a
complete sentence ("set volume to 60", "open calculator", "close notepad", "send meena I'm late").

The rewrite is plain text and goes back through the normal router, so every guard, policy and confirmation still
applies: a carried-over "send" asks for confirmation exactly like a typed one. It works on construction shapes
(new target, new number, pronoun, ordinal), never on particular sentences. It never resolves a pronoun for
destructive or sharing verbs (delete, uninstall, send, share ...); those keep asking. With no recent command, or
when the follow-up is not one of these shapes, it does nothing.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

TTL_S = 15 * 60          # a follow-up refers to something done in the last quarter hour
_NUM = r"\d+(?:[.:]\d+)?"

# Arguments that name what a command acted on, most specific first.
_TARGET_KEYS = ("name", "app", "target", "recipient", "contact", "to", "city", "location", "path", "file", "query", "title", "url")
# Verbs that act on an app or window and may take "it" / "the first one" for the app just used.
_APP_VERBS = (r"close\s+down|close|quit|exit|kill|shut|get\s+rid\s+of|end|terminate|restart|reopen|relaunch|minimi[sz]e|maximi[sz]e|hide|show|focus|switch\s+to|"
              r"go\s+to|open|launch|start|bring\s+back|bring\s+up|restore|snap|move|resize|full\s*screen|pin")
# Verbs whose object is never guessed from context.
_NEVER = re.compile(r"\b(?:delete|remove|erase|wipe|trash|uninstall|send|share|forward|post|upload|email|mail|message|text|"
                    r"whatsapp|pay|buy|order|format|rename|move\s+(?:it|that|this)\s+to|install|reply)\b")
# Words that start a full command of their own ("and open chrome" is a new command, not a new target).
_VERB_START = re.compile(
    r"^(?:open|close|launch|start|run|play|pause|stop|set|turn|switch|search|find|look|show|tell|send|message|text|call|"
    r"remind|create|make|delete|remove|install|uninstall|update|take|lock|restart|shut|mute|unmute|increase|decrease|"
    r"raise|lower|go|navigate|visit|type|write|read|copy|paste|move|rename|minimi[sz]e|maximi[sz]e|what|who|where|when|"
    r"why|how|is|are|do|does|can|could|will|would|please|check|get|put|add|save|download|upload|share)\b")
# A new target is a name or a place, never a function word, a negation or an answer.
_NOT_A_TARGET = re.compile(r"^(?:don'?t|do\s+not|not|never|stop|cancel|wait|leave|forget|nothing|nevermind|thanks?|thank|ok|okay|"
                           r"yes|yeah|yep|no|nope|please|that'?s|it'?s|its|i|you|we|he|she|they|my\s+bad|then|so|what|why|how|"
                           r"again|more|less|later|now|too|also|instead|anyway|whatever|fine|good|great|cool|done)\b")
_ADJUSTABLE = ("volume", "brightness", "zoom", "speed", "font size", "temperature")
_UP = r"(?:louder|higher|brighter|up|more|bigger|faster|increase\s+it|raise\s+it|turn\s+it\s+up|(?:a\s+)?(?:little|bit)\s+more)"
_DOWN = r"(?:quieter|softer|lower|dimmer|darker|down|less|smaller|slower|decrease\s+it|reduce\s+it|turn\s+it\s+down|(?:a\s+)?(?:little|bit)\s+less)"
_ORD = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3,
        "last": -1, "latest": -1, "previous": -2}
_LIST_TOOLS = ("search_web", "find_file", "search_files", "list_directory", "read_whatsapp_messages", "gmail_list_recent",
               "list_reminders", "search_news", "knowledge_search")
_APP_TOOLS = ("open_app", "close_app", "focus_app", "switch_window", "minimize_window", "maximize_window", "window_op",
              "system_op")


_LEAD = re.compile(r"^(?:(?:hey|hi|ok|okay)\s+)?jarvis\s*[,.!:]?\s+|^(?:um+|uh+|hmm+|m{2,}|erm+|er|ok|okay|so|well|alright|right|oh|ah+|"
                   r"(?:can|could|would|will)\s+you(?:\s+please)?|please|pls|kindly|just)\s*[,.!]?\s+")
_TAIL = re.compile(r"\s*[,.!]?\s+(?:please|pls|plz|now|right\s+now|thanks|thank\s+you|jarvis|for\s+me|quickly|real\s+quick)$")


def _clean(text: str) -> str:
    """The follow-up without wake word, fillers, courtesy and swapped-letter typos ("um, colse it please")."""
    t = " ".join((text or "").lower().split()).strip(" .!?")
    for _ in range(4):
        u = _TAIL.sub("", _LEAD.sub("", t)).strip(" .!?,")
        if u == t or not u:
            break
        t = u
    try:
        from jarvis.core.router.normalize import repair_swapped_letters
        t = repair_swapped_letters(t)
    except Exception:
        pass
    # Tanglish demonstratives are "it" ("atha close pannu" -> "close atha" -> "close it"); a remark about the owner after
    # the command is not part of it ("quit it, i'm done listening")
    t = re.sub(r"\b(?:adhu|athu|atha|adha|athai|adhai|idhu|ithu|itha|idha|ithai|idhai)\b", "it", t)
    from jarvis.core.semantics.references import REMARK_TAIL
    cut = REMARK_TAIL.sub("", t).strip(" ,.")
    if cut and cut != t and len(cut.split()) >= 2:
        t = cut
    return t


@dataclass
class Turn:
    text: str
    tool: str
    slots: dict[str, Any]
    at: float = field(default_factory=time.monotonic)
    wall: float = field(default_factory=time.time)
    pending: bool = False          # waiting for the owner's yes - not done yet

    def target(self) -> tuple[str, str] | None:
        for key in _TARGET_KEYS:
            v = self.slots.get(key)
            if isinstance(v, str) and v.strip():
                return key, v.strip()
        return None


class CarryOver:
    def __init__(self) -> None:
        self.turns: list[Turn] = []
        self.apps: list[str] = []          # apps opened in this conversation, oldest first, closed ones removed

    # ---------------------------------------------------------------- recording
    def record(self, text: str, tool: str, slots: dict[str, Any] | None, app: str = "", pending: bool = False) -> None:
        if not text or not tool or tool in ("clarify", "recent_actions", "command_history"):
            return
        self.turns.append(Turn(" ".join(text.split()), tool, dict(slots or {}), pending=pending))
        del self.turns[:-8]
        name = (app or (slots or {}).get("name") or "").strip()
        if tool == "open_app" and name:
            self.apps = [a for a in self.apps if a.lower() != name.lower()] + [name]
            del self.apps[:-6]
        elif tool == "close_app" and name:
            self.apps = [a for a in self.apps if a.lower() != name.lower()]

    def last(self) -> Turn | None:
        if self.turns and time.monotonic() - self.turns[-1].at <= TTL_S:
            return self.turns[-1]
        return None

    # ---------------------------------------------------------------- rewriting
    def rewrite(self, text: str) -> str | None:
        """The complete command a follow-up stands for, or None when it is not a follow-up this can resolve."""
        t = _clean(text)
        self._raw = " ".join((text or "").split())
        if not t or len(t.split()) > 10:
            return None
        last = self.last()
        for step in (self._event_change, self._introspect, self._forget, self._flip, self._repeat, self._additive, self._ordinal,
                     self._resend, self._person, self._typed_verb, self._question_pronoun, self._pronoun, self._refine,
                     self._settings_page, self._device_ui, self._number, self._relative, self._extend, self._category_swap,
                     self._new_target):
            out = step(t, last)
            if out:
                return out
        return None

    @staticmethod
    def _additive(t: str, last: Turn | None) -> str | None:
        """'open calculator too' -> 'open calculator' (a complete command with an additive word)."""
        m = re.match(r"^(?:and\s+|also\s+|then\s+)?(?P<cmd>.+?)\s*,?\s+(?:too|also|as\s+well|instead)$", t)
        if m and _VERB_START.match(m.group("cmd")) and not re.match(r"(?:do|try)\b", m.group("cmd")) \
                and not _NEVER.search(m.group("cmd")) and len(m.group("cmd").split()) >= 2:
            return m.group("cmd")
        # "now open slack", "and then close it": a connector before a full command
        m = re.match(r"^(?:(?:and|then|now|also|plus|ok|no|nope|nah|sorry|oops|wait|actually|hmm|i\s+said|i\s+meant|"
                     r"that'?s\s+wrong|wrong\s+(?:one|app)|my\s+bad)\s*[,.!]?\s+)+(?P<cmd>.+)$", t)
        if m and _VERB_START.match(m.group("cmd")) and not re.match(r"(?:do|try|what|who|where|when|why|how|is|are|can|could|will|would|"
                                                                    r"does|please)\b", m.group("cmd")) \
                and len(m.group("cmd").split()) >= 2 and not re.search(r"\b(?:it|that|this|them)\b", m.group("cmd")):
            cmd = m.group("cmd")
            if last is not None and last.tool == "search_web" and re.match(r"search\s+(?!for\b)", cmd):
                cmd = re.sub(r"^search\s+", "search for ", cmd)   # right after a web search, "search X" is the web too
            return cmd
        return None

    def _ordinal(self, t: str, last: Turn | None) -> str | None:
        """'close the first one' / 'close both' over the apps opened in this conversation."""
        if not self.apps or (last is not None and last.tool in _LIST_TOOLS):
            return None
        m = re.match(rf"^(?:now\s+|and\s+|then\s+)?(?P<v>{_APP_VERBS})\s+(?:the\s+)?(?:(?P<o>first|1st|second|2nd|third|3rd|fourth|4th|"
                     rf"last|latest|previous)(?:\s+(?:one|app|window|program))?|(?P<all>both(?:\s+of\s+them)?|them\s+both|all\s+of\s+them|"
                     rf"them\s+all|them|both\s+apps|all\s+(?:those|these|the)\s+apps))$", t)
        if not m:
            return None
        verb = m.group("v")
        verb = {"go to": "switch to", "bring up": "switch to", "focus": "switch to", "get rid of": "close", "end": "close",
                "terminate": "close", "close down": "close"}.get(verb, verb)
        if verb in ("open", "launch", "start"):
            return None   # "open the second one" is about a list of results, not the apps already open
        if m.group("all"):
            if len(self.apps) < 2:
                return None
            return " and ".join(f"{verb} {a}" for a in self.apps)
        idx = _ORD[m.group("o")]
        if idx >= len(self.apps) or -idx > len(self.apps):
            return None
        return f"{verb} {self.apps[idx]}"

    def _pronoun(self, t: str, last: Turn | None) -> str | None:
        """'close it' after opening notepad -> 'close notepad'; 'play lofi on it' after youtube -> '... on youtube'."""
        side = re.search(r"\bto\s+the\s+(?:left|right)(?:\s+(?:side|half))?$", t)   # a screen side, never a folder
        if last is None or (_NEVER.search(t) and not side):
            return None
        tgt = last.target()
        if tgt is None:
            return None
        key, value = tgt
        is_app = last.tool in _APP_TOOLS or key in ("name", "app")
        if last.tool == "close_app":
            is_app = False   # "open it again" after closing is fine, but "close it" twice is not a reference
            if re.match(r"^(?:open|launch|start|reopen|restart)\s+(?:it|that)(?:\s+again|\s+back)?$", t):
                return f"open {value}"
            return None
        if is_app:
            m = re.match(rf"^(?:now\s+|and\s+|then\s+|please\s+)?(?P<v>{_APP_VERBS})\s+(?:it|that|this)(?:\s+(?:app|window|program))?"
                         rf"(?P<rest>\s+(?:back|up|again|to\s+the\s+(?:left|right)|down))?$", t)
            if m:
                verb, rest = m.group("v"), (m.group("rest") or "").strip()
                if verb.startswith("bring") and rest == "back" or verb == "bring back":
                    return f"switch to {value}"
                verb = {"get rid of": "close", "end": "close", "terminate": "close", "close down": "close"}.get(verb, verb)
                if verb in ("open", "launch", "start") and last.tool == "open_app" and not rest:
                    return None      # already open
                if rest.startswith("to the") and verb in ("move", "snap"):
                    return f"snap {value} {rest}"
                return f"{verb} {value}" + (f" {rest}" if rest and rest not in ("again",) else "")
            it = r"(?:it|that|this)(?:\s+(?:app|window|program))?"
            if re.match(rf"^(?:bring\s+{it}\s+(?:back|up|forward|to\s+the\s+front)|(?:go|switch|jump|get)\s+back\s+to\s+{it}|"
                        rf"(?:go|switch|jump)\s+to\s+{it}|show\s+(?:me\s+)?{it}(?:\s+again)?|focus\s+(?:on\s+)?{it})$", t):
                return f"switch to {value}"
            if re.match(rf"^(?:make|put)\s+{it}\s+(?:bigger|larger|full\s*screen|maximum|max)$", t):
                return f"maximize {value}"
            if re.match(rf"^(?:make\s+{it}\s+(?:smaller|tiny)|put\s+{it}\s+(?:in|into)\s+the\s+(?:background|taskbar)|send\s+{it}\s+to\s+the\s+back|"
                        rf"get\s+{it}\s+out\s+of\s+(?:the\s+)?(?:way|sight))$", t):
                return f"minimize {value}"
            m = re.match(rf"^(?:move|snap|put|push|send|dock)\s+{it}\s+(?:to\s+(?:the\s+)?|on\s+the\s+)(?P<side>left|right)(?:\s+(?:side|half))?$", t)
            if m:
                return f"snap {value} to the {m.group('side')}"
        site = value if last.tool in ("open_website", "open_app", "android_open_app") else ""
        if site:
            m = re.match(r"^(?P<cmd>(?:play|search(?:\s+for)?|look\s+up|find|watch|stream|show(?:\s+me)?)\s+.+?)\s+(?:(?:on|in)\s+(?:it|that|there)|there)$", t)
            if m:
                name = last.slots.get("title") or value
                name = re.sub(r"^https?://(?:www\.)?|\.(?:com|in|org)\b.*$", "", str(name))
                return f"{m.group('cmd')} on {name}"
        if last.tool in ("find_file", "search_files") and re.search(r"\.\w{1,5}$", value):
            if re.match(r"^(?:open|show|launch|run|view)\s+(?:me\s+)?(?:it|that|this|(?:the|that|this)\s+(?:file|pdf|document|doc|image|photo|picture|spreadsheet|sheet|video|one))(?:\s+file)?(?:\s+up)?$", t):
                return f"open {value}"
        return None

    _PERSON_TOOLS = ("read_whatsapp_messages", "summarize_whatsapp_messages", "send_whatsapp_message", "reply_whatsapp_message",
                     "contact_info", "android_dial", "phone_call", "gmail_list_recent", "gmail_create_draft", "whatsapp_summary")
    _PERSON_KEYS = ("recipient", "contact", "sender", "person", "to", "from", "who", "name")

    def _person(self, t: str, last: Turn | None) -> str | None:
        """Typed reference: 'reply to her saying congratulations' right after 'show me messages from Deepa' -> Deepa.
        Only a person pronoun, only to the person of the immediately preceding person-typed turn (the active thread) -
        never an older one, never by recency across types. The send is still confirmed with the name spelled out."""
        if last is None or last.tool not in self._PERSON_TOOLS:
            return None
        who = next((str(last.slots[k]).strip() for k in self._PERSON_KEYS
                    if isinstance(last.slots.get(k), str) and str(last.slots[k]).strip()
                    and not re.fullmatch(r"(?:all|everyone|me|unread|any|someone|group)", str(last.slots[k]).strip(), re.I)), "")
        if not who:
            return None
        pron = r"(?:him|her|them|avan(?:ukku|uku|ku)?|aval(?:ukku|uku|ku)?|avanga(?:ukku|lukku|ku)?|avaru(?:kku)?)"
        m = re.match(rf"^(?P<v>(?:reply|respond|write\s+back|answer)\s+to|message|text|whatsapp|send|ping|tell|call|ring|dial|"
                     rf"email|mail|remind)\s+{pron}\b(?P<rest>.*)$", t)
        if not m:
            return None
        rest = m.group("rest")
        i = self._raw.lower().rfind(rest.strip().lower()) if rest.strip() else -1
        if i >= 0:
            rest = (" " if rest.startswith(" ") else "") + self._raw[i:i + len(rest.strip())]   # the message as said
        return f"{m.group('v')} {who.title() if who.islower() else who}{rest}"

    @staticmethod
    def _event_change(t: str, last: Turn | None) -> str | None:
        """'make it an hour long instead' while the event just proposed still waits for a yes -> the same event with the
        new length. Never after it was created (there is no calendar update tool, so that would duplicate it)."""
        if last is None or last.tool != "calendar_create_event" or not last.pending:
            return None
        m = re.match(r"^(?:no\s*,?\s+|actually\s*,?\s+)?(?:make|change|set)\s+(?:it|that|the\s+(?:event|meeting|call))\s+(?:to\s+)?"
                     r"(?P<d>(?:an?|one|two|three|half\s+an|\d+(?:\.\d+)?)\s*(?:hours?|hrs?|minutes?|mins?))(?:\s+long)?(?:\s+instead)?$", t)
        if not m:
            return None
        base = re.sub(r"\s+for\s+(?:an?|one|two|three|half\s+an|\d+(?:\.\d+)?)\s*(?:hours?|hrs?|minutes?|mins?)\b", "", last.text)
        base = re.sub(r"\s+to\s+my\s+calendar$", "", base)
        return f"{base} for {m.group('d')}"

    @staticmethod
    def _number(t: str, last: Turn | None) -> str | None:
        """'make it 60' / 'actually 40' / 'no I said 17' -> the last command with the new number."""
        if last is None:
            return None
        m = re.match(rf"^(?:no\s*,?\s+|nope\s*,?\s+|actually\s*,?\s+|sorry\s*,?\s+|wait\s*,?\s+|oops\s*,?\s+)*"
                     rf"(?:(?:make|change|set|put|turn|bump|drop|lower|raise|reduce|increase|decrease|push|move|take|bring|switch|"
                     rf"shift|adjust|go)\s+(?:it\s+|that\s+|the\s+time\s+|the\s+level\s+)?(?:up\s+|down\s+|back\s+)?(?:to\s+|at\s+|till\s+)?|"
                     rf"i\s+(?:said|meant|wanted|want)\s+|(?:make\s+)?that\s+|(?:to|at)\s+|change\s+the\s+time\s+to\s+)?(?P<n>{_NUM})\s*"
                     rf"(?P<u>%|percent|per\s+cent|pm|am|p\.m\.|a\.m\.|o'?clock|minutes?|mins?|hours?|seconds?)?"
                     rf"(?:\s+(?:instead|please|would\s+be\s+(?:better|fine|good)|is\s+(?:better|fine|good)|will\s+do))?$", t)
        if not m:
            return None
        n = m.group("n")
        if re.search(r"send|dial|call|delete|remove|uninstall|install|pay|share|forward|email|reply|post|power|message|"
                     r"transfer|push|upload", last.tool):
            return None   # a new number for a call or a send is a new request, said in full
        explicit = not re.fullmatch(r"\d+(?:[.:]\d+)?", t)   # only a bare "5" needs a volume / brightness to make sense
        if not explicit and not any(q in last.text for q in _ADJUSTABLE):
            return None   # a bare "5" only adjusts a volume / brightness just set
        numbers = list(re.finditer(rf"(?<![\w.]){_NUM}(?![\w.])", last.text))
        if not numbers:
            return None
        hit = None
        for v in last.slots.values():
            if isinstance(v, (int, float)) or (isinstance(v, str) and re.fullmatch(_NUM, v.strip())):
                hit = next((x for x in numbers if x.group() == str(v).strip() or
                            (re.fullmatch(r"\d+(?:\.\d+)?", x.group()) and float(x.group()) == float(v))), None)
                if hit:
                    break
        if hit is None:
            if len(numbers) != 1:
                return None   # "remind me at 5 for 10 minutes" + "make it 6": which number? ask instead
            hit = numbers[0]
        return last.text[:hit.start()] + n + last.text[hit.end():]

    @staticmethod
    def _relative(t: str, last: Turn | None) -> str | None:
        """'a little higher' / 'make it louder' after a volume or brightness change."""
        if last is None:
            return None
        noun = next((q for q in _ADJUSTABLE if q in last.text), None)
        if noun is None and re.search(r"play|media|music|video|song", last.tool + " " + last.text):
            noun = "volume"   # "louder" while music plays
        if noun is None:
            return None
        if re.fullmatch(r"(?:max|maximum|full)(?:\s+it)?(?:\s+out)?|(?:make|turn|put)\s+it\s+(?:to\s+)?(?:max|maximum|full)|all\s+the\s+way\s+up", t):
            return f"set {noun} to 100"
        too = re.match(r"^(?:it'?s\s+|that'?s\s+|still\s+|way\s+|bit\s+|a\s+bit\s+|much\s+|kinda\s+|a\s+little\s+)*too\s+(?P<w>loud|bright|high|strong|much|"
                       r"quiet|soft|low|dim|dark|faint)$", t)
        if too:
            return f"{'decrease' if too.group('w') in ('loud', 'bright', 'high', 'strong', 'much') else 'increase'} the {noun}"
        m = re.match(rf"^(?:(?:make|turn|put)\s+(?:it|that)\s+)?(?:a\s+(?:little|bit|tad)\s+(?:bit\s+)?|slightly\s+|bit\s+|much\s+|way\s+)?"
                     rf"(?:(?P<up>{_UP})|(?P<down>{_DOWN}))(?:\s+(?:a\s+(?:little|bit|tad)|a\s+notch|slightly|more|please|still|again))?$", t)
        if not m:
            return None
        return f"{'increase' if m.group('up') else 'decrease'} the {noun}"

    @staticmethod
    def _resend(t: str, last: Turn | None) -> str | None:
        """Right after a message: 'send the same to X', 'no, send it to X', 'and X too'. The recipient is said; only
        the message comes from context, and the send still asks for confirmation."""
        if last is None or "message" not in last.slots or not last.slots.get("recipient"):
            return None
        m = re.match(r"^(?:no\s*,?\s+|actually\s*,?\s+|sorry\s*,?\s+|also\s+|and\s+)*(?:send|forward|text|message)\s+(?:(?:the\s+same(?:\s+(?:message|thing|text))?|"
                     r"it|that|this(?:\s+message)?)\s+)?(?:to|for)\s+(?P<x>[a-z][\w .'-]{0,30}?)(?:\s+(?:too|also|as\s+well|instead))?$", t) \
            or re.match(r"^(?:the\s+)?same\s+(?:message|thing|text)\s+(?:to|for)\s+(?P<x>[a-z][\w .'-]{0,30}?)(?:\s+(?:too|also|as\s+well))?$", t)
        if not m or _NOT_A_TARGET.match(m.group("x")):
            return None
        value = str(last.slots["recipient"])
        pos = last.text.lower().find(value.lower())
        return last.text[:pos] + m.group("x").strip() + last.text[pos + len(value):] if pos >= 0 else None

    def _new_target(self, t: str, last: Turn | None) -> str | None:
        """'do the same for calculator', 'now calculator', 'and in pune?', 'also to meena', 'no, notepad'."""
        if last is None:
            return None
        m = (re.match(r"^(?:(?:and\s+|now\s+|then\s+)?(?:do|try)\s+)?(?:the\s+)?same\s+(?:thing\s+)?(?:for|with|to|on)\s+(?P<x>.+)$", t)
             or re.match(r"^(?:(?:no|nope|nah|sorry|oops|actually|wait|hmm|hold\s+on|my\s+bad|that'?s\s+(?:wrong|not\s+(?:it|right))|wrong\s+(?:one|app|person|contact|name)|"
                         r"not\s+(?:that(?:\s+one)?|this(?:\s+one)?|[\w.'-]+(?:\s+[\w.'-]+)?))\s*[,.!]?\s+)+"
                         r"(?:i\s+(?:meant|said|wanted|want|asked\s+for|need)\s+|not\s+that\s*,?\s+|make\s+it\s+|it'?s\s+|its\s+|it\s+(?:was|is)\s+(?:meant\s+)?for\s+|"
                         r"it\s+should\s+(?:be|go\s+to)\s+|(?:i\s+)?(?:want|need)\s+)?(?P<x>.+)$", t)
             or re.match(r"^(?:i\s+(?:meant|said|wanted|asked\s+for|was\s+asking\s+for)|it\s+(?:was|is)\s+(?:meant\s+)?for)\s+(?P<x>.+)$", t)
             or re.match(r"^(?P<x>[\w .'-]+?)\s*,?\s+not\s+[\w .'-]+$", t)
             or re.match(r"^(?:(?:and|so|ok|okay|then)\s+)?(?:what|how)\s+about\s+(?P<x>.+)$", t)
             or re.match(r"^(?:and\s+)?how'?s\s+it\s+(?P<x>(?:in|at|for)\s+.+)$", t)
             or re.match(r"^(?:(?:and|now|then|also|plus)\s+)+(?:do\s+|try\s+)?(?:also\s+)?(?P<x>.+?)(?:\s+(?:too|also|as\s+well|next))?$", t)

             or re.match(r"^(?:repeat|do)\s+(?:that|it|the\s+same)\s+(?:again\s+)?(?:for|with|on)\s+(?P<x>.+)$", t)
             or re.match(r"^try\s+(?P<x>.+)$", t)
             or re.match(r"^(?:do|try)\s+(?P<x>.+?)\s+(?:too|also|as\s+well|next|now)$", t)
             or re.match(r"^(?P<x>[\w .'-]+?)\s*,?\s+(?:too|also|as\s+well|instead|next)$", t)
             or re.match(r"^(?:cc|copy)\s+(?P<x>[\w .'-]+?)(?:\s+(?:on|in)\s+(?:it|that|this))?(?:\s+too)?$", t))
        if not m:
            return None
        x = m.group("x").strip(" ,?")
        query = bool(last.target()) and last.target()[0] == "query" and last.tool != "chat"
        if query and re.match(r"(?:how|what|why|when|where|which|who|is|are|best|top)\b", x) and len(x.split()) >= 3 \
                and not _NEVER.search(x):
            return re.sub(re.escape(last.target()[1]), x, last.text, count=1, flags=re.I) if last.target()[1].lower() in last.text.lower() else None
        if not x or _NOT_A_TARGET.match(x) or _VERB_START.match(x) or _NEVER.search(x) and not _NEVER.search(last.text) \
                or re.search(r"\b(?:it|that|this|them|one)\b", x) \
                or len(x.split()) > (7 if last.target() and last.target()[0] == "query" else 4):
            return None
        prep = re.match(r"^(?P<p>in|at|to|for|from|with|on)\s+(?P<v>.+)$", x)
        if prep:
            p, v = prep.group("p"), prep.group("v")
            # "weather in chennai" + "and in pune": replace what followed the same preposition
            pm = list(re.finditer(rf"\b{p}\s+(?P<w>[\w.'-]+(?:\s+(?!(?:at|on|in|to|for|from|with|and|by|about)\b)[\w.'-]+){{0,3}})", last.text))
            if pm:
                w = pm[-1]
                return last.text[:w.start("w")] + v + last.text[w.end("w"):]
            x = v
        if last.tool == "chat":
            # "weather in chennai" + "what about pune": the place after the question's last preposition
            pm = list(re.finditer(r"\b(?:in|at|for|of)\s+(?P<w>[\w.'-]+(?:\s+[\w.'-]+){0,2})$", last.text))
            if pm and len(x.split()) <= 3:
                return last.text[:pm[-1].start("w")] + x + last.text[pm[-1].end("w"):]
            return None
        tgt = last.target()
        if tgt is None:
            return None
        key, value = tgt
        if key == "query" and len(value) > 0.8 * len(last.text):
            return None
        pos = last.text.lower().find(value.lower())
        if pos < 0:
            return None
        return last.text[:pos] + x + last.text[pos + len(value):]

    # ---------------------------------------------------------------- typed follow-ups (references by type, not recency)
    @staticmethod
    def _introspect(t: str, last: Turn | None) -> str | None:
        """'who did that go to', 'what did it say', 'when was that' -> a question about what JARVIS just did."""
        if last is None:
            return None
        if re.match(r"^(?:and\s+)?(?:who|whom)\s+(?:did\s+(?:that|it|this|the\s+message)\s+go\s+to|was\s+(?:that|it)\s+(?:sent\s+)?(?:to|for)|"
                    r"did\s+you\s+send\s+(?:that|it)\s+to|got\s+(?:that|it))$", t):
            return "who did you send that to"
        if re.match(r"^(?:and\s+)?(?:what\s+did\s+(?:it|that|the\s+message|you)\s+(?:say|send|do)|when\s+(?:was|did)\s+(?:that|it)"
                    r"(?:\s+(?:happen|sent|done|go))?|did\s+(?:it|that)\s+(?:go\s+through|work|send))$", t):
            return "what was the last thing you did"
        return None

    @staticmethod
    def _forget(t: str, last: Turn | None) -> str | None:
        """'actually forget that' right after 'remember X' -> 'forget that X' (the fact just stored, by type)."""
        if last is None or last.tool != "remember_fact":
            return None
        if not re.match(r"^(?:(?:actually|no|wait|oh|hmm)\s*,?\s+)*(?:forget|delete|remove|erase|drop|unremember)\s+(?:that|it|this)"
                        r"(?:\s+(?:fact|one|note|again))?(?:\s+(?:please|now))?$", t):
            return None
        fact = str(last.slots.get("fact") or last.slots.get("text") or "").strip()
        return f"forget that {fact}" if fact else None

    @staticmethod
    def _flip(t: str, last: Turn | None) -> str | None:
        """'turn it back on' / 'switch that off again' after a toggle -> the same toggle in the new state."""
        if last is None or last.pending or _NEVER.search(last.text):
            return None
        m = re.match(r"^(?:(?:now|and|then|ok(?:ay)?|ok\s+now)\s+)*(?:turn|switch|put|flip|set)\s+(?:it|that|this|them)\s+(?:back\s+)?"
                     r"(?P<v>on|off)(?:\s+again)?$", t) \
            or re.match(r"^(?:(?:now|and|then)\s+)*(?:turn|switch)\s+(?:back\s+)?(?P<v>on|off)\s+(?:it|that|this)(?:\s+again)?$", t)
        en = re.match(r"^(?:(?:now|and|then)\s+)*(?P<e>re-?enable|enable|disable|activate|deactivate)\s+(?:it|that|this)(?:\s+again)?$", t)
        if not m and not en:
            return None
        want_on = (m.group("v") == "on") if m else en.group("e") in ("enable", "reenable", "re-enable", "activate")
        x = last.text
        p = re.search(r"\b(?P<verb>turn|switch|put|toggle)\s+(?P<v>on|off)\b", x) \
            or re.search(r"\b(?:turn|switch)\s+(?:the\s+|my\s+)?[\w-]+(?:\s+[\w-]+)?\s+(?P<v>on|off)\b", x)
        if p:
            return x[:p.start("v")] + ("on" if want_on else "off") + x[p.end("v"):]
        e = re.search(r"\b(?P<e>enable|disable|activate|deactivate)\b", x)
        if e:
            new = {True: {"enable": "enable", "disable": "enable", "activate": "activate", "deactivate": "activate"},
                   False: {"enable": "disable", "disable": "disable", "activate": "deactivate", "deactivate": "deactivate"}}
            return x[:e.start()] + new[want_on][e.group("e")] + x[e.end():]
        return None

    @staticmethod
    def _repeat(t: str, last: Turn | None) -> str | None:
        """'do it again', 'again, a bit more', 'do both again', 'slower than that even', 'innum konjam' -> the last command
        again. Never a send, delete, payment ... (said again in full), never while it still waits for a yes."""
        if last is None or last.pending or _NEVER.search(last.text) or re.search(
                r"send|delete|remove|uninstall|install|pay|share|forward|email|reply|post|upload|call|dial|power|format", last.tool):
            return None
        again = re.match(r"^(?:(?:and|now|ok(?:ay)?|please)\s+)*(?:do\s+(?:it|that|this|the\s+same|both|them|those|all\s+of\s+(?:it|them))"
                         r"(?:\s+(?:thing|steps?))?\s+(?:again|once\s+more)|again|once\s+more|one\s+more\s+time|repeat\s+(?:it|that)|"
                         r"same\s+again|thirumba(?:\s+pannu)?|marubadiyum(?:\s+pannu)?)(?:\s*,?\s*(?:a\s+(?:bit|little)\s+|even\s+|some\s+)?"
                         r"(?:more|further|again|please|now))*$", t)
        more = re.match(r"^(?:(?:a\s+(?:bit|little|tad)|even|still|some|much|way)\s+)*more(?:\s+please)?$|^innum(?:\s+(?:konjam|koncham))?"
                        r"(?:\s+(?:podu|pannu))?$", t)
        comp = re.match(r"^(?:(?:even|still|a\s+bit|a\s+little)\s+)*(?P<c>[a-z]+er)(?:\s+than\s+that)?(?:\s+(?:even|still|please))*$", t)
        if again:
            return last.text
        relative = re.search(r"\b(?:in|out|up|down|louder|quieter|brighter|dimmer|darker|faster|slower|bigger|smaller|larger|"
                             r"increase|decrease|raise|lower|reduce|boost|more|less|next|previous|forward|backward|ahead)\b", last.text)
        if more and relative:
            return last.text
        if comp and re.search(rf"\b{comp.group('c')}\b", last.text):
            return last.text
        return None

    _TYPED_VERBS = r"(?P<v>move|copy|rename|compress|zip|unzip|extract|open|show|print|back\s+up|install|launch|start|run)"

    def _typed_verb(self, t: str, last: Turn | None) -> str | None:
        """'move it to documents' after opening report.docx, 'zip that folder up' after creating it, 'then install it'
        after asking whether OBS is installed: the pronoun is the resource of the turn just before, when its type fits the
        verb (a file or folder for move / copy / rename / compress, an app for install). Never for delete, send, share,
        uninstall or pay - those name their object."""
        if last is None or last.pending:
            return None
        t2 = re.sub(r"^(?:(?:and|then|now|so|ok(?:ay)?|go\s+ahead\s+and|after\s+that)\s*,?\s+)+", "", t)
        m = re.match(rf"^{self._TYPED_VERBS}\s+(?:it|that|this|them|(?:that|this|the)\s+(?:one|file|folder|document|doc|pdf|photo|"
                     rf"picture|image|app|program|thing))(?:\s+up)?(?P<rest>(?:\s+(?:to|into|in|as|on|from|with)\s+.+)?)$", t2)
        if not m:
            return None
        verb, rest = re.sub(r"\s+", " ", m.group("v")), m.group("rest")
        file_tools = ("open_file", "find_file", "search_files", "create_folder", "create_file", "move_file", "copy_file", "rename_file",
                      "compress_files", "list_directory", "open_known_folder", "document_qa")
        app_tools = ("check_app_installed", "get_app_location", "app_version", "search_software", "open_app", "close_app")
        if last.tool in file_tools and verb not in ("install", "launch", "start", "run"):
            value = next((str(last.slots[k]) for k in ("path", "source", "file", "document_path", "query", "name", "folder")
                          if isinstance(last.slots.get(k), str) and last.slots[k].strip()), "")
            if not value or verb == "rename" and not rest:
                return None
            return f"{verb} {value}{rest}"
        if last.tool in app_tools and verb in ("install", "open", "launch", "start", "run") and not rest:
            name = str(last.slots.get("name") or last.slots.get("app") or "").strip()
            if name and not (verb == "install" and last.tool in ("open_app", "close_app")):
                return f"{verb} {name}"
        return None

    @staticmethod
    def _question_pronoun(t: str, last: Turn | None) -> str | None:
        """'where on disk is it installed' after 'is git installed': a question's 'it' is the app the last question was about."""
        if last is None or last.tool not in ("check_app_installed", "get_app_location", "app_version", "search_software"):
            return None
        name = str(last.slots.get("name") or "").strip()
        if not name or not re.match(r"^(?:where|what|which|when|how|is|does|do|can)\b", t) or not re.search(r"\b(?:it|that)\b", t):
            return None
        return re.sub(r"\b(?:it|that)\b", name, t, count=1)

    @staticmethod
    def _refine(t: str, last: Turn | None) -> str | None:
        """'only the urgent ones', 'just the unread ones from them' after a list -> the same list with that qualifier."""
        if last is None or last.tool not in ("read_whatsapp_messages", "gmail_list_recent", "find_file", "search_files", "list_directory",
                                             "list_reminders", "calendar_list_events", "notifications", "list_notifications"):
            return None
        m = re.match(r"^(?:(?:and|now|ok(?:ay)?|but)\s+)?(?:(?:just|only|show\s+(?:me\s+)?(?:just|only)|only\s+show(?:\s+me)?)\s+)?(?:the\s+)"
                     r"(?P<q>[a-z]+(?:\s+[a-z]+)?)\s+ones?(?:\s+from\s+(?:them|him|her|that\s+\w+|those))?$", t)
        if not m:
            return None
        q = m.group("q")
        n = list(re.finditer(r"\b(?P<n>messages|msgs|emails|e-mails|mails|files|events|reminders|notifications|photos|pdfs|documents|"
                             r"chats|tasks|notes|meetings)\b", last.text))
        if not n:
            return None
        k = n[-1]
        return last.text[:k.start()] + f"{q} " + last.text[k.start():]

    @staticmethod
    def _settings_page(t: str, last: Turn | None) -> str | None:
        """'go to the bluetooth page in there' after opening settings -> 'open bluetooth settings'."""
        if last is None or not (last.tool == "open_system_settings" or re.search(r"\bsettings\b", last.text)):
            return None
        m = re.match(r"^(?:(?:now|and|then)\s+)*(?:go\s+to|open|show(?:\s+me)?|switch\s+to|jump\s+to)\s+(?:the\s+)?(?P<x>[\w -]+?)\s+"
                     r"(?:page|section|tab|screen|settings|part)(?:\s+(?:in\s+there|there|in\s+(?:it|that|here)))?$", t)
        return f"open {m.group('x').strip()} settings" if m else None

    @staticmethod
    def _device_ui(t: str, last: Turn | None) -> str | None:
        """Right after working on the phone ('mirror my phone screen'), 'tap on settings' is on the phone too."""
        if last is None or not (last.tool.startswith("android") or re.search(r"\b(?:phone|mobile|android)\b", last.text)):
            return None
        if re.match(r"^(?:tap|long\s+press|press|swipe|scroll)\b", t) and not re.search(r"\b(?:phone|pc|laptop|computer|mobile)\b", t):
            return f"{t} on my phone"
        return None

    @staticmethod
    def _extend(t: str, last: Turn | None) -> str | None:
        """'extend it to everyone' / 'apply that to Priya too' -> the last command with the new target."""
        if last is None or last.pending or re.search(r"send|delete|uninstall|pay|share|forward|email|post|upload|call|dial", last.tool):
            return None
        m = re.match(r"^(?:(?:and|now|also)\s+)?(?:extend|apply|expand|widen|change|switch|do)\s+(?:it|that|this|the\s+same)\s+(?:to|for)\s+"
                     r"(?P<x>[\w .'-]{1,30}?)(?:\s+(?:too|also|as\s+well|instead))?$", t)
        tgt = last.target() or next(((k, str(last.slots[k])) for k in ("who", "sender", "person", "contact")
                                     if isinstance(last.slots.get(k), str) and last.slots[k].strip()), None)
        if not m or tgt is None:
            return None
        key, value = tgt
        x = m.group("x").strip()
        pos = last.text.lower().find(value.lower())
        if pos < 0 or _NOT_A_TARGET.match(x):
            return None
        return last.text[:pos] + x + last.text[pos + len(value):]

    _SWAP_CATEGORIES = None

    @classmethod
    def _categories(cls) -> list[list[str]]:
        if cls._SWAP_CATEGORIES is None:
            try:
                from jarvis.core.semantics.constraints import _CATEGORIES
                cats = [list(c) for c in _CATEGORIES]
            except Exception:
                cats = []
            cats.append(list(_ADJUSTABLE))
            cats.append(["wifi", "wi-fi", "bluetooth", "hotspot", "data", "mobile data", "location", "nfc", "airplane mode",
                         "flashlight", "torch", "do not disturb", "dark mode", "night light", "auto rotate"])
            cls._SWAP_CATEGORIES = cats
        return cls._SWAP_CATEGORIES

    def _category_swap(self, t: str, last: Turn | None) -> str | None:
        """'and the data too' after turning wifi off, 'what about friday' after thursday's calendar, 'do the same for brightness'
        after a volume change, 'what about the march one' after the april invoice: a word of the same kind replaces its
        sibling in the last command. On the phone: 'what about on the phone' after a PC-side read."""
        if last is None or last.pending or _NEVER.search(last.text):
            return None
        m = re.match(r"^(?:(?:and|now|then|also|ok(?:ay)?|so|but)\s+)*(?:(?:what|how)\s+about\s+|(?:do|try)\s+the\s+same\s+(?:thing\s+)?(?:for|with|to)\s+|"
                     r"same\s+(?:thing\s+)?(?:for|with)\s+)?(?:(?:the|my|on|in|for|at|with)\s+)*(?P<x>[a-z][\w -]*?)"
                     r"(?:\s+(?:one|ones))?(?:\s+to\s+the\s+same(?:\s+(?:number|level|value|amount|percent|percentage|setting))?)?"
                     r"(?:\s+(?:too|also|as\s+well|instead|then))?\s*\??$", t)
        if not m:
            return None
        x = m.group("x").strip()
        low = last.text.lower()
        if x in ("phone", "mobile", "my phone", "the phone") and not re.search(r"\b(?:phone|mobile|pc|laptop|computer)\b", low):
            if re.match(r"(?:describe_screen|take_screenshot|volume|brightness|battery|screen)", last.tool):
                return f"{last.text} on my phone"
            return None
        for cat in self._categories():
            if x not in cat:
                continue
            for sib in sorted(cat, key=len, reverse=True):
                if sib == x:
                    continue
                hit = re.search(rf"\b{re.escape(sib)}\b", low)
                if hit:
                    return last.text[:hit.start()] + x + last.text[hit.end():]
        return None


def carryover_of(memory: Any) -> CarryOver | None:
    """The carry-over attached to a working memory (created on first use)."""
    if memory is None:
        return None
    co = getattr(memory, "_carryover", None)
    if co is None:
        try:
            co = CarryOver()
            setattr(memory, "_carryover", co)
        except Exception:
            return None
    return co
