"""Voice / text commands that grant or revoke WhatsApp auto-reply.

    "Reply to Yoga automatically for the next hour."   -> Yoga only, 60 min
    "Handle Arun's messages until 6 PM."                -> Arun (by stable id), until 18:00
    "Reply to her for 30 minutes."                      -> the contact just talked about
    "For the next two hours, respond to everyone."      -> ALL DIRECT CONTACTS (never groups)
    "Stop replying to her." / "Stop WhatsApp auto reply." / "Who are you auto replying to?"

An auto-reply grant always needs an end time; there is no permanent auto mode from a command.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "ten": 10, "fifteen": 15,
        "twenty": 20, "thirty": 30, "forty five": 45, "forty-five": 45, "a couple of": 2, "couple of": 2, "few": 3}
_NUM_RE = r"\d+(?:\.\d+)?|" + "|".join(sorted((re.escape(k) for k in _NUM), key=len, reverse=True))
_FOR = re.compile(rf"\bfor\s+(?:the\s+)?(?:next\s+)?(?:(?P<half>half\s+an?\s+hour)|(?P<n>{_NUM_RE})\s*(?P<u>minutes?|mins?|hours?|hrs?|h)|"
                  rf"(?P<one>hour|an hour))\b", re.I)
_UNTIL = re.compile(r"\b(?:until|till|til|upto|up to)\s+(?P<t>noon|midnight|tonight|(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?\s*(?P<ap>a\.?m\.?|p\.?m\.?)?)",
                    re.I)
_REST_OF_DAY = re.compile(r"\bfor\s+(?:the\s+)?rest\s+of\s+(?:the\s+)?(?:day|evening|night)\b", re.I)
_EVERYONE = re.compile(r"^(?:every\s*one|every\s*body|all(?:\s+of\s+them)?|all\s+(?:my\s+)?(?:direct\s+)?(?:contacts|chats|people|messages)|"
                       r"all\s+people|anyone|any\s*body)$", re.I)
_PRONOUN = re.compile(r"^(?:her|him|them|this person|that person|this contact|that contact)$", re.I)


def parse_window(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    now = now or datetime.now()
    m = _FOR.search(text)
    if m:
        if m.group("half"):
            return now + timedelta(minutes=30)
        if m.group("one"):
            return now + timedelta(hours=1)
        raw = m.group("n").lower()
        n = float(raw) if raw[0].isdigit() else _NUM[raw]
        unit = m.group("u").lower()
        return now + (timedelta(hours=n) if unit.startswith("h") else timedelta(minutes=n))
    if _REST_OF_DAY.search(text):
        return now.replace(hour=23, minute=59, second=0, microsecond=0)
    m = _UNTIL.search(text)
    if m:
        t = m.group("t").lower()
        if t == "noon":
            hour, minute, ap = 12, 0, "pm"
        elif t in ("midnight", "tonight"):
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0) if t == "midnight" \
                else now.replace(hour=23, minute=0, second=0, microsecond=0)
        else:
            hour, minute = int(m.group("h")), int(m.group("m") or 0)
            ap = (m.group("ap") or "").lower().replace(".", "")
        candidates = []
        if ap == "pm" and hour < 12:
            candidates = [hour + 12]
        elif ap == "am":
            candidates = [0 if hour == 12 else hour]
        elif hour <= 12:
            candidates = [hour % 24, (hour + 12) % 24]  # "until 10" = the next 10 o'clock
        else:
            candidates = [hour]
        best = None
        for h in candidates:
            cand = now.replace(hour=h, minute=minute, second=0, microsecond=0)
            if cand <= now:
                cand += timedelta(days=1)
            if best is None or cand < best:
                best = cand
        return best
    return None


def parse_command(text: str) -> Optional[dict[str, Any]]:
    """Structure of an auto-reply command, or None if the text is something else."""
    t = re.sub(r"\s+", " ", (text or "").strip().lower()).strip(" .!?")
    t = re.sub(r"^(?:hey jarvis|ok jarvis|jarvis|please|can you|could you)[, ]+", "", t)
    if not t:
        return None
    # ---- status
    if re.match(r"^(?:who (?:are you|is jarvis) (?:auto[- ]?)?(?:replying|responding) to(?: on whatsapp)?|"
                r"(?:whatsapp )?auto[- ]?reply status|is (?:whatsapp )?auto[- ]?reply (?:on|active|enabled|running)|"
                r"(?:which|what) (?:contacts|chats|people) (?:have|are on|are in) (?:whatsapp )?auto[- ]?reply(?: on)?)$", t):
        return {"action": "status"}
    # ---- stop (emergency stop for everyone, or one contact)
    m = re.match(r"^(?:stop|disable|turn off|switch off|pause|end|cancel)\s+(?:the\s+|all\s+)?(?:whatsapp\s+)?auto(?:matic)?[- ]?"
                 r"(?:reply|replies|replying|responses?|responder)(?:\s+(?:on\s+)?whatsapp)?(?:\s+(?:for|to)\s+(?P<who>.+?))?$", t)
    if m:
        who = (m.group("who") or "").strip()
        return {"action": "disable_all"} if not who or _EVERYONE.match(who) else {"action": "disable", "who": who}
    m = re.match(r"^(?:stop|quit|don'?t keep)\s+(?:auto[- ]?)?(?:replying|responding|answering)(?:\s+to)?\s+(?P<who>.+?)(?:'s\s+(?:messages|chats))?(?:\s+on whatsapp)?$", t)
    if m:
        who = m.group("who").strip()
        return {"action": "disable_all"} if _EVERYONE.match(who) else {"action": "disable", "who": who}
    # ---- enable (needs a time window, or an explicit "automatically")
    window_present = bool(_FOR.search(t) or _UNTIL.search(t) or _REST_OF_DAY.search(t))
    auto_word = bool(re.search(r"\b(?:automatically|auto[- ]?reply|auto[- ]?respond|on my behalf|for me)\b", t))
    if (window_present or auto_word) and re.match(r"^(?:auto[- ]?reply|auto[- ]?respond|reply|respond|answer|handle|manage|"
                                                  r"turn on|enable|start)\b.*\bgroups?\b", t):
        return {"action": "refuse_groups"}  # group chats are never auto-replied
    patterns = [
        r"^(?:auto[- ]?reply|auto[- ]?respond|reply|respond|answer)\s+(?:automatically\s+)?(?:to\s+)?(?P<who>.+?)(?:'s\s+(?:messages|chats|texts))?"
        r"(?:\s+(?:automatically|on my behalf|for me))?(?:\s+on\s+whatsapp)?\s+(?:for|until|till|til|up ?to)\b.*$",
        r"^(?:handle|manage|take care of|answer|look after)\s+(?P<who>.+?)'s\s+(?:whatsapp\s+)?(?:messages|chats|texts|whatsapp)\b.*$",
        r"^(?:handle|manage|take care of)\s+(?:the\s+)?(?:whatsapp\s+)?(?:messages|chats)\s+(?:from|of)\s+(?P<who>.+?)\s+(?:for|until|till)\b.*$",
        r"^(?:for|until|till)\b.+?,?\s+(?:auto[- ]?)?(?:reply|respond|answer)\s+(?:automatically\s+)?(?:to\s+)?(?P<who>.+?)(?:\s+automatically)?(?:\s+on whatsapp)?$",
        r"^(?:turn on|enable|start|switch on)\s+(?:whatsapp\s+)?auto[- ]?(?:reply|replies|replying)(?:\s+(?:for|to)\s+(?P<who>[a-z][\w .'-]*?))?"
        r"(?=\s+(?:for|until|till)\b|$).*$",
        r"^(?:reply|respond)\s+(?:to\s+)?(?P<who>.+?)\s+automatically$",
    ]
    for pat in patterns:
        m = re.match(pat, t)
        if not m:
            continue
        who = (m.group("who") or "").strip()
        who = re.sub(r"\s+(?:for|until|till|til)\b.*$", "", who).strip()
        who = re.sub(r"^(?:all\s+)?(?:my\s+)?whatsapp\s+", "", who)
        if not (window_present or auto_word):
            return None
        if not who and not pat.startswith("^(?:turn on"):
            continue
        everyone = bool(who) and bool(_EVERYONE.match(who))  # "everyone" must be said explicitly
        if re.search(r"\bgroups?\b", who):
            return {"action": "refuse_groups"}
        return {"action": "enable", "who": "" if everyone else who, "everyone": everyone, "window_text": t,
                "has_window": window_present}
    return None


class AutoReplyInput(Contract):
    action: str = Field(description="enable, disable, disable_all or status")
    who: str = Field(default="", max_length=120, description="Contact name, number, JID, or her/him/them")
    everyone: bool = Field(default=False, description="All DIRECT contacts (groups are always excluded)")
    window_text: str = Field(default="", max_length=300, description="Original wording with the duration / end time")
    has_window: bool = False


class AutoReplyOutput(Contract):
    status: str
    message: str
    expires_at: Optional[float] = None


class WhatsAppAutoReplyTool(Tool):
    definition = ToolDefinition(
        name="whatsapp_auto_reply",
        description="Turns WhatsApp auto-reply on for one contact, several, or all direct contacts for a limited time "
                    "(never groups), turns it off, or reports its status. Replies use the owner's style with each person.",
        input_model=AutoReplyInput, output_model=AutoReplyOutput, read_only=False, risk=RiskLevel.REVERSIBLE,
        timeout_s=10.0, tags=("whatsapp", "auto reply", "messaging"), execution_method=ExecutionMethod.NATIVE,
    )

    def __init__(self, agent: Any = None, resolver: Any = None) -> None:
        self._agent = agent
        self._resolver = resolver

    @property
    def agent(self):
        if self._agent is not None:
            return self._agent
        from jarvis.integrations.whatsapp.personal_reply.agent import get_personal_reply_agent
        return get_personal_reply_agent()

    @property
    def resolver(self):
        if self._resolver is None:
            from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
            self._resolver = ContactResolver()
        return self._resolver

    def _resolve(self, who: str) -> tuple[Optional[str], str, str]:
        """(contact_id, display_name, error). Never guesses between several people."""
        if _PRONOUN.match(who.strip()):
            cid = self.agent.last_contact
            if not cid:
                return None, "", "Who do you mean? Tell me the contact's name."
            return cid, self.agent.store.display_name(cid), ""
        contact, ambiguous, prompt = self.resolver.resolve(who)
        if ambiguous:
            return None, "", prompt or f"More than one contact matches '{who}'. Which one?"
        if contact is None:
            return None, "", prompt or f"I couldn't find a WhatsApp contact called {who}."
        jid = contact.jid if "@" in contact.jid else f"{re.sub(r'[^0-9]', '', contact.jid)}@s.whatsapp.net"
        return jid, contact.display_name, ""

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = AutoReplyInput(**arguments)
        agent, action = self.agent, arguments.action
        if action == "status":
            return {"status": "OK", "message": agent.status_text()}
        if action == "refuse_groups":
            return {"status": "REFUSED", "message": "I never auto-reply in group chats. I can do it for your direct chats."}
        if action == "disable_all":
            return {"status": "STOPPED", "message": agent.stop_all()["message"]}
        if action == "disable":
            cid, name, err = self._resolve(arguments.who)
            if err:
                return {"status": "NEEDS_CLARIFICATION", "message": err}
            agent.stop(cid)
            return {"status": "STOPPED", "message": f"Stopped auto-replying to {name}."}
        if action == "enable":
            now = datetime.fromtimestamp(agent.clock())  # one time source for parsing and enforcement
            until = parse_window(arguments.window_text, now) if arguments.window_text else None
            if until is None:
                return {"status": "NEEDS_CLARIFICATION",
                        "message": "For how long? For example: for the next hour, or until 6 PM."}
            expires = until.timestamp()
            try:
                if arguments.everyone:
                    res = agent.enable([], expires, everyone=True)
                elif not arguments.who.strip():
                    return {"status": "NEEDS_CLARIFICATION",
                            "message": "Who should I auto-reply to? Name a contact, or say everyone (direct chats only)."}
                else:
                    cid, name, err = self._resolve(arguments.who)
                    if err:
                        return {"status": "NEEDS_CLARIFICATION", "message": err}
                    res = agent.enable([cid], expires, names=[name])
            except ValueError as exc:
                return {"status": "REFUSED", "message": str(exc)}
            return {"status": "ENABLED", "message": res["message"], "expires_at": res["expires_at"]}
        return {"status": "UNKNOWN", "message": "Say, for example: reply to Yoga for the next hour."}
