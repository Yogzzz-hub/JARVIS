"""Synthetic WhatsApp data for the personal reply agent (no real people, no real messages).

Four relationships with clearly different OWNER styles:
* Yoga      (91900000001) - casual Tanglish, short, emojis
* Arun Kumar(91900000002) - professional English, full sentences, no emojis
* Karthik   (91900000003) - very short casual replies ("ok", "seri", "haa varan")
* Arun      (91900000004) - a SECOND "Arun": casual English with "bro" (identity must stay separate)

``export_text()`` renders an Android-style "Export chat" file; ``StandInLLM`` is a deterministic
stand-in for the local model that answers ONLY from the prompt the pipeline built (it reuses the most
relevant retrieved owner example and the requested language) - it measures the pipeline (profile,
retrieval, isolation, gating), not language-model quality.
"""
from __future__ import annotations

import random
import re
from datetime import datetime, timedelta
from typing import Any

OWNER = "Me"

CONTACTS = {
    "yoga": {"jid": "91900000001@s.whatsapp.net", "name": "Yoga", "style": "tanglish"},
    "arunk": {"jid": "91900000002@s.whatsapp.net", "name": "Arun Kumar", "style": "professional"},
    "karthik": {"jid": "91900000003@s.whatsapp.net", "name": "Karthik", "style": "short"},
    "arun": {"jid": "91900000004@s.whatsapp.net", "name": "Arun", "style": "casual_en"},
}

# (contact message, owner reply) pairs per style, grouped by situation so held-out situations stay unseen.
PAIRS = {
    "tanglish": [
        ("dei tomorrow varuviya?", "haa varen da 😄"), ("nalaiku office varuviya", "varen da, 10 ku reach aagiduven"),
        ("enna panra da", "summa iruken da, nee?"), ("saptiya?", "saptachu da 😋 nee?"),
        ("match paathiya?", "paathen da semma match 🔥"), ("evening meet pannalama", "seri da evening pogalam 👍"),
        ("movie ku polama saturday", "polam da, ticket paaru 😄"), ("free ah irundha call pannu", "seri da konjam late ah pannuren"),
        ("enga iruka", "office la iruken da"), ("birthday party ku varuva?", "kandippa varen da 🎉"),
        ("assignment mudichiya", "innum illa da, night mudichiduven"), ("cricket vilayadalama sunday", "seri da, morning ah?"),
        ("bike service pannitiya", "illa da, next week pannuren"), ("trip plan enna aachu", "innum decide pannala da 😅"),
        ("un phone switch off ah irundhuchu", "charge illa da, ippo on pannitten"), ("dinner ku enna", "biryani sollalam da 😋"),
        ("exam epdi pochu", "paravala da, nalla than ezhudhinen"), ("gym ku varuviya", "innaiku illa da, tired ah iruken"),
        ("amma kitta sollitiya", "sollitten da 👍"), ("bus stop la wait pannuren", "5 mins da varen"),
    ],
    "professional": [
        ("Can we review the proposal tomorrow?", "Sure, tomorrow works. I'll block 30 minutes in the afternoon."),
        ("Are you available for a call at 3?", "Yes, 3 works for me. I'll call you then."),
        ("Did the client respond to our email?", "Not yet. I'll follow up today and update you."),
        ("Please share the updated slides when ready.", "Will do. I'll send them by end of day."),
        ("The meeting is moved to Thursday.", "Noted, thanks for letting me know."),
        ("Can you join the vendor call tomorrow morning?", "Yes, I can join. Please send me the invite."),
        ("How is the migration going?", "It's on track. Testing should finish by Friday."),
        ("Could you review my pull request?", "Sure, I'll review it this afternoon."),
        ("Are we still on for lunch with the team?", "Yes, still on. See you at 1."),
        ("Can you send the quarterly numbers?", "I'll check with finance and get back to you."),
        ("Thanks for the quick turnaround.", "Happy to help. Thanks for the clear brief."),
        ("Is the demo environment ready?", "Almost. I'll confirm once the last check passes."),
        ("Can we push the deadline by a day?", "That should be fine. I'll update the plan."),
        ("Did you get a chance to read the report?", "Yes, it looks good. I have two small comments."),
        ("Will you be at the office tomorrow?", "Yes, I'll be in from 10."),
        ("Please approve the leave request.", "Done, approved. Enjoy the break."),
        ("The server is slow again.", "Thanks, I'll ask the infra team to take a look."),
        ("Can you present the update on Monday?", "Sure, I'll prepare a short summary."),
    ],
    "short": [
        ("coming?", "haa varan"), ("free now?", "ok"), ("reached?", "seri"), ("done?", "done"), ("call pannatuma", "ok"),
        ("tomorrow 9 ok?", "seri"), ("lunch?", "haa"), ("sent the file", "ok"), ("wait pannu", "seri"), ("where?", "home"),
        ("start pannitiya", "haa"), ("5 mins la varen", "ok"), ("tea?", "haa varan"), ("busy ah", "illa"), ("sleep ah", "haa"),
        ("ticket book pannitten", "ok"), ("seri ah?", "seri"), ("nalaiku leave ah", "illa"),
    ],
    "casual_en": [
        ("bro are you coming tomorrow?", "yeah bro I'll be there"), ("what's up bro", "nothing much bro, chilling"),
        ("did you watch the match?", "yes bro crazy finish"), ("wanna play football sunday?", "sure bro, what time?"),
        ("send me that meme lol", "haha sending bro"), ("free this evening?", "yeah after 7 bro"),
        ("how was the trip", "awesome bro, pics soon"), ("lunch tomorrow?", "sure bro"),
        ("you busy?", "a bit bro, call you later"), ("new phone?", "yeah bro finally upgraded"),
        ("gym today?", "not today bro, tired"), ("movie this weekend?", "sure bro, you pick"),
    ],
}

# Situations never present in any imported history (generalisation tests).
UNSEEN = {
    "tanglish": ["dei nalaiku beach ku polama?", "un laptop repair aachu ah?", "temple ku varuviya sunday",
                 "hostel la food epdi iruku", "new job epdi da pogudhu"],
    "professional": ["Could you share feedback on the new logo?", "Are you joining the offsite next month?",
                     "Can we reschedule our one-on-one?", "Did the contract draft come through?"],
    "short": ["bus vandhucha?", "coffee?", "office ah?", "ready ah?"],
    "casual_en": ["bro wanna go cycling tomorrow?", "did you try that new cafe?", "you coming for the party?"],
}


def history(style: str, n: int, seed: int = 7, hold_back: int = 0) -> list[tuple[str, str]]:
    """``n`` exchanges sampled from the style's situations (optionally holding the last ``hold_back`` situations out)."""
    rng = random.Random(seed)
    pairs = PAIRS[style][: len(PAIRS[style]) - hold_back] if hold_back else PAIRS[style]
    return [rng.choice(pairs) for _ in range(n)]


def export_text(contact_key: str, n: int = 120, seed: int = 7, start: datetime | None = None, hold_back: int = 0,
                owner: str = OWNER, extra_system: bool = True) -> str:
    c = CONTACTS[contact_key]
    t = start or datetime(2026, 3, 1, 9, 0)
    rng = random.Random(seed)
    lines = []
    if extra_system:
        lines.append(t.strftime("%d/%m/%y, %I:%M %p").lower() + " - Messages and calls are end-to-end encrypted. No one outside of this chat can read them.")
    for them, me in history(c["style"], n, seed, hold_back):
        t += timedelta(hours=rng.randint(3, 40), minutes=rng.randint(0, 59))
        lines.append(f"{t.strftime('%d/%m/%y, %I:%M %p').lower()} - {c['name']}: {them}")
        t += timedelta(minutes=rng.randint(1, 20))
        lines.append(f"{t.strftime('%d/%m/%y, %I:%M %p').lower()} - {owner}: {me}")
        if rng.random() < 0.05:
            lines.append(f"{t.strftime('%d/%m/%y, %I:%M %p').lower()} - {c['name']}: <Media omitted>")
    return "\n".join(lines) + "\n"


class StandInLLM:
    """Deterministic stand-in for OllamaClient.chat_json used by tests and the benchmark."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def chat_json(self, messages: list[dict[str, Any]], schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        from jarvis.core.llm.client import LLMError
        prompt = "\n".join(m["content"] for m in messages)
        self.calls.append({"prompt": prompt, "kwargs": kwargs})
        if self.fail:
            raise LLMError("model offline")
        current = prompt.split("CURRENT_MESSAGE:\n", 1)[1].split("\n\nREPLY_POLICY", 1)[0].strip()
        target = re.search(r"language for this reply: (\w+)", prompt).group(1)
        you = re.findall(r"^\s+You: (.+)$", prompt, re.M)
        if re.fullmatch(r"[\W\d_]*|(?:[bcdfghjklmnpqrstvwxz]{5,}\s*)+", current.lower()):
            return {"reply": "?", "understood": False, "confidence": 0.1, "intent": "unclear"}
        if you:
            reply = you[0]
        elif target == "ENGLISH":
            reply = "Sure, sounds good."
        else:
            reply = "seri"
        return {"reply": reply, "understood": True, "confidence": 0.85, "intent": "reply"}
