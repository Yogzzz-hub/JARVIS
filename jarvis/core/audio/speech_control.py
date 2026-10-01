"""What the owner says about JARVIS's own voice, recognised by meaning rather than by exact phrase.

    stop      "stop talking", "ok that's enough", "shh", "I got it, thanks", "no need to read all that", "pesadha", "podhum"
    pause     "wait", "hold on", "one second", "give me a moment", "konjam iru"
    resume    "continue", "go on", "carry on", "where were we", "keep reading", "sollu"
    repeat    "say that again", "what did you say", "come again", "pardon", "one more time", "thirumba sollu"
    skip      "skip that", "next", "skip this part"
    slower / faster / louder / softer   "speak slower", "slow down", "talk faster", "speak up", "lower your voice"

Anything else said over JARVIS's voice is a new instruction: speech stops and the words are processed as a command.
"""
from __future__ import annotations

import re
from typing import Optional

_LEAD = re.compile(r"^(?:(?:hey\s+)?jarvis|ok(?:ay)?|okay|alright|hmm+|um+|uh+|please|no(?!\s+(?:need|more))|yeah|yes|so|just|sorry|wait\s+wait)[\s,.!]+",
                   re.I)
_TAIL = re.compile(r"[\s,.!]+(?:jarvis|please|now|thanks|thank\s+you|for\s+now|a\s+bit|a\s+little|bro|da|dei|machan)$", re.I)

_PATTERNS: tuple[tuple[str, str], ...] = (
    ("stop", r"(?:you\s+can\s+|please\s+|just\s+)?(?:stop|quit|cut)\s*(?:it|that|this)?\s*(?:talking|speaking|reading|"
             r"there|the\s+(?:voice|speech|audio|reading))?"
             r"|(?:that'?s|that\s+is|it'?s)?\s*enough(?:\s+(?:talking|speaking|reading|already))?"
             r"|no\s+more\s+(?:talking|speaking|reading)|be\s+quiet|quiet|silence|shut\s+up|shush|hush|sh+|zip\s+it|mute\s+(?:yourself|your\s+voice)"
             r"|i\s+(?:got|get|understand|understood)\s+(?:it|that)(?:\s*,?\s*(?:stop|thanks|enough))?|got\s+it\s*,?\s*(?:stop|enough)"
             r"|no\s+need\s+to\s+(?:read|say|explain|talk|speak|continue)(?:\s+(?:all\s+)?(?:that|it|more|further))?"
             r"|(?:don'?t|do\s+not)\s+(?:read|say|talk|speak)\s+(?:all\s+)?(?:that|it|anymore|any\s+more|further)"
             r"|stop\s+(?:pannu|panu)|pesa+(?:dh|th)?[ae]|podh?u+m|nir?u+t+h?u|summa\s+iru|vaaya\s+moodu"),
    ("pause", r"wait(?:\s+a\s+(?:sec(?:ond)?|moment|minute))?|hold\s+on|hang\s+on|one\s+(?:sec(?:ond)?|moment|minute)"
              r"|(?:(?:give\s+me|just)\s+)?a\s+(?:sec(?:ond)?|moment|minute)|pause(?:\s+(?:talking|speaking|reading|there))?"
              r"|konjam\s+(?:iru|wait\s+pannu)|wait\s+pannu"),
    ("resume", r"(?:please\s+)?(?:continue|go\s+on|carry\s+on|resume|keep\s+going|proceed)(?:\s+(?:talking|speaking|reading|"
               r"from\s+there|where\s+you\s+(?:left|stopped)(?:\s+off)?))?|keep\s+(?:talking|reading|speaking)|where\s+were\s+we"
               r"|you\s+can\s+continue|go\s+ahead\s+and\s+(?:continue|finish)|finish\s+(?:what\s+you\s+were\s+saying|it|that)"
               r"|continue\s+pannu|sollu"),
    ("repeat", r"(?:can\s+you\s+|could\s+you\s+|please\s+)?(?:repeat|say)\s+(?:that|it|this)\s+again|repeat(?:\s+(?:that|it|please))?"
               r"|what\s+did\s+you\s+(?:just\s+)?say|what|huh|sorry\s+what|come\s+again|pardon(?:\s+me)?|sorry\s+what|(?:one\s+more\s+time|once\s+more)"
               r"|i\s+(?:didn'?t|did\s+not)\s+(?:hear|catch|get)\s+(?:that|it|you)|thirumba\s+sollu|repeat\s+pannu"),
    ("skip", r"skip(?:\s+(?:that|this|it|ahead))?(?:\s+part)?|next(?:\s+(?:one|part|sentence|point))?|move\s+on"),
    ("slower", r"(?:speak|talk|read|go)\s+(?:a\s+(?:bit|little)\s+)?(?:more\s+)?(?:slow(?:er|ly)?)|slow\s+(?:down|it\s+down)"
               r"|(?:you'?re|you\s+are)\s+(?:talking|speaking|going)\s+too\s+fast|too\s+fast"),
    ("faster", r"(?:speak|talk|read|go)\s+(?:a\s+(?:bit|little)\s+)?(?:more\s+)?(?:fast(?:er)?|quick(?:er|ly)?)|speed\s+(?:up|it\s+up)"
               r"|(?:you'?re|you\s+are)\s+(?:talking|speaking|going)\s+too\s+slow(?:ly)?|too\s+slow"),
    ("louder", r"(?:speak|talk)\s+(?:up|louder)|louder|(?:i\s+)?can'?t\s+hear\s+you|(?:a\s+bit\s+)?more\s+loud(?:ly)?"
               r"|raise\s+your\s+voice"),
    ("softer", r"(?:speak|talk)\s+(?:softer|quieter|more\s+(?:softly|quietly)|lower|down)|softer|lower\s+your\s+voice"
               r"|(?:you'?re|you\s+are)\s+too\s+loud|too\s+loud|not\s+so\s+loud"),
)
_COMPILED = tuple((action, re.compile(rf"(?:{pattern})", re.I)) for action, pattern in _PATTERNS)


def _clean(text: str) -> str:
    t = " ".join((text or "").lower().replace("’", "'").split()).strip(" .!?")
    for _ in range(3):
        t2 = _TAIL.sub("", _LEAD.sub("", t)).strip(" .!?,")
        if t2 == t:
            break
        t = t2
    return t


def classify(text: str, speaking: bool = True) -> Optional[str]:
    """The voice action the owner asked for, or None when the words are a normal command.

    ``speaking=False`` (nothing is being said right now): only unambiguous voice settings and "say that again" count;
    "next", "wait" or "continue" on their own are left to the normal router.
    """
    t = _clean(text)
    if not t or len(t.split()) > 9:
        return None
    for action, pattern in _COMPILED:
        if pattern.fullmatch(t):
            if not speaking and action in ("pause", "resume", "skip"):
                if not re.search(r"\b(?:talking|speaking|reading|voice|where\s+you|where\s+were)\b", t):
                    return None
            if not speaking and action == "repeat":
                return None  # when JARVIS is quiet, "say that again" is answered from the action record
            if not speaking and action == "stop" and not re.search(
                    r"\b(?:talking|speaking|reading|read|say|explain|voice|speech|quiet|shut|shush|hush|enough|mute|pesa\w*|podh?u+m|summa|"
                    r"niru\w*|zip|sh+|silence|got\s+it|get\s+it)\b", t):
                return None
            return action
    # "stop talking and open chrome" / "wait, open chrome": a stop word followed by a new instruction is a new command
    return None


def leading_stop(text: str) -> Optional[str]:
    """'stop, open chrome instead' -> 'open chrome instead': the instruction after an interrupting stop word."""
    t = " ".join((text or "").split())
    m = re.match(r"^(?:(?:hey\s+)?jarvis[\s,]+)?(?:ok(?:ay)?[\s,]+)?(?:stop(?:\s+(?:talking|speaking|it|that))?|wait|hold\s+on|enough|"
                 r"no\s+no|no)\s*[,.!]+\s*(?:and\s+|instead\s+)?(?P<rest>\S.{2,})$", t, re.I)
    return m.group("rest").strip() if m else None
