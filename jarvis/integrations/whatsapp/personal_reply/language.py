"""English / Tanglish detection for short chat messages.

Tanglish = Tamil written in Latin letters, mixed with English ("seri da, naalaiku varen").

The seed lexicon and suffix rules below are used ONLY to *detect* which language mix a message uses.
They are never used to write replies: reply vocabulary comes exclusively from the owner's own imported
messages (``ContactStyleProfile.common_tanglish_phrases``).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ENGLISH = "ENGLISH"
TANGLISH = "TANGLISH"
MIXED = "MIXED"
UNKNOWN = "UNKNOWN"

_DATA = Path(__file__).resolve().parent / "data" / "english_words.txt"

# Chat English that a frequency list of written English misses.
_ENGLISH_CHAT = set("""ok okay okey k kk yes yeah yea yep yup nope no hi hey hello bye thanks thank thx ty pls plz please sorry
lol lmao haha hahaha hehe hmm hmmm omg btw idk tmrw tmr tomo gn gm u ur r y bro dude sis guys gonna wanna gotta cool nice
awesome sure fine done noted busy call later soon tomorrow today tonight morning evening night meeting office home reach
reached coming come going went wait sent send check free good great np alright alrite congrats congratulations bday""".split())

# Detection-only lexicon of frequent Tamil words / particles in Latin script.
_TAMIL_SEED = set("""enna ena yenna epdi eppadi epadi eppo epo enga yenga yaaru yaru yaar yen en illa ila illai illaya seri sari
iruken irukken irukan iruku irukku irukkum iruka irukka irukiya irukiyaa irukeenga irukinga irundha iruntha vaa va vaanga vanga po poda podi pogalam pogala da di dei machan
machi mama nanba nanbaa nalla nalladhu romba rombha konjam koncham sollu solu solren sollren sonna sonnen pannu pannu panren
panren pannalam pannitu panniten varen varan varuven varuviya varuva varala vandhen vandhutu vanthuten aama aamaa amam
naan nan nee ni neenga nenga unga ungalukku enakku enaku unakku unaku avan aval avanga inga anga ange inge sapadu saapadu
saaptiya saptiya saptacha thoongu thoonga paathu paaru parunga pesu pesalam pesuren mudiyuma mudiyadhu mudiyathu venum
vennum vendam venam theriyum theriyadhu theriyathu kandippa nalaiku naalaiku nalaikku inniku innaiku inaiku ippo ipo apram
appuram aprom appo adhu athu idhu ithu edhu ethu edhuku ethuku yenna oru rendu moonu enakkum paravala paravalla parava
seriya sariya aana ana aprum illana illena ok-da okda sollunga pannunga vanakkam nandri kalaila kaalaila saayangalam
raathri nite pa ma dhan than thaan dhaan kooda kuda mattum ellam ellaam onnum onnume edhavadhu yaarum velai vela office-la
""".split())

_TAG_PARTICLES = {"ah", "aa"}

# Word endings that are very common in romanised Tamil and rare in English (weak evidence only).
_TAMIL_SUFFIX = re.compile(r"(?:kku|ukku|ikku|ku|la|le|nu|nga|inga|unga|ren|rom|lam|chu|tten|ten|dhu|thu|ndi|ttu|kum|um|iya|va)$")

_TOKEN = re.compile(r"[a-z][a-z']*")
_EMOJI_RANGES = ((0x1F300, 0x1FAFF), (0x2600, 0x27BF), (0x1F000, 0x1F2FF), (0xFE00, 0xFE0F), (0x1F900, 0x1F9FF))


@lru_cache(maxsize=1)
def english_words() -> frozenset[str]:
    words = set(_ENGLISH_CHAT)
    try:
        for line in _DATA.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                words.add(line.strip())
    except OSError:
        pass
    return frozenset(words - _TAMIL_SEED)


def is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES) or unicodedata.category(ch) == "So"


def emojis(text: str) -> list[str]:
    return [ch for ch in text or "" if is_emoji(ch) and ch not in "️‍"]


def tokens(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def classify_token(tok: str) -> str:
    """'EN', 'TA' or '' (unknown: names, numbers, typos)."""
    if tok in _TAMIL_SEED:
        return "TA"
    if tok in english_words():
        return "EN"
    base = tok.rstrip("'s")
    if base in english_words():
        return "EN"
    if len(tok) >= 4 and _TAMIL_SUFFIX.search(tok):
        return "TA"
    return ""


@dataclass
class LanguageMix:
    label: str            # ENGLISH / TANGLISH / MIXED / UNKNOWN
    tamil_share: float    # share of recognised tokens that are Tamil
    english_tokens: int
    tamil_tokens: int
    tamil_words: list[str]


def detect(text: str) -> LanguageMix:
    toks = tokens(text)
    en = ta = 0
    tamil_words: list[str] = []
    for i, t in enumerate(toks):
        # "free ah?", "busy aa" - the Tanglish question tag (a leading "ah" stays an English interjection)
        c = "TA" if t in _TAG_PARTICLES and i > 0 else classify_token(t)
        if c == "EN":
            en += 1
        elif c == "TA":
            ta += 1
            tamil_words.append(t)
    known = en + ta
    if known == 0:
        return LanguageMix(UNKNOWN, 0.0, 0, 0, [])
    share = ta / known
    if share >= 0.6:
        label = TANGLISH
    elif share >= 0.2 or (ta >= 1 and known <= 3):
        label = MIXED
    else:
        label = ENGLISH
    return LanguageMix(label, share, en, ta, tamil_words)


def is_tanglish_mode(label: str) -> bool:
    return label in (TANGLISH, MIXED)
