"""English + Thanglish: understand commands in either, and reply in the language the owner uses.

Thanglish = Tamil written in English letters, usually mixed with English ("chrome open pannu", "volume konjam
kammi pannu", "amma ku late aagum nu message anuppu").

* ``to_english_command`` rewrites Tamil word order (object first, verb last) into the English commands the
  router already understands. Only whole, recognised patterns are rewritten; anything else is left untouched.
* ``reply_language`` decides the reply language: "auto" mirrors the owner (Thanglish in -> Thanglish out),
  or a fixed "english" / "thanglish" chosen with "reply in thanglish" / "english la pesu".
* ``in_thanglish`` turns JARVIS's short action confirmations ("Chrome is open.") into Thanglish; chat answers
  are written in Thanglish by the model itself (``prompt_instruction``).
* ``tamil_to_latin`` romanises Tamil script, in case speech recognition writes Tamil letters.
"""
from __future__ import annotations

import json
import re
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

ENGLISH, THANGLISH, AUTO = "english", "thanglish", "auto"

# Language of the reply for the request being handled (set by the command service, read by the assistant).
REPLY_LANGUAGE: ContextVar[str] = ContextVar("reply_language", default=ENGLISH)

_STATE = Path(__file__).resolve().parents[2] / "data" / "language.json"

# Verbs and particles that only occur in Thanglish commands (added to the WhatsApp detector's Tamil lexicon).
_COMMAND_WORDS = frozenset("""mattum matum ellaa ellam ellame ellathaiyum ellathayum paatu paattu paadal adutha aduththa munnadi munnaadi pannu panu pannunga pannuga pannidu panniduda panni podu podunga pottu potu anuppu anupu anuppidu
anuppunga thedu theadu thedunga niruthu nirutthu nirutu moodu mudu moodunga thora thorakku thiranthu edu eduthu edunga
kammi korai kurai kuraichu korachidu koraichidu kuraichidu solliru jaasthi jasthi athigam adhigam kootu koottu ethu eathu vai vechidu vachidu sollu sollidu
sollunga kitta ku kku ukku nu apdinu enna ennachu evlo evvalavu eppadi epdi pesu pesunga paaru kaattu kattu
pannitu pannittu panitu pannanum manikku nyabagam yaar yaaru pannirukka pannirukanga panniruka anupchaa anupiyaa anuppiyaa anupicha poyiducha enga engey
iruku irukku kaatu kaatunga aachu ippo panniru panniruga padichu padithu eduda koraiyi koraiyu kuraiyu kuraiyi nimisham nimidam kaalaila kaalaiyil ezhuppu sathama satham saththama valikuthu valikkudhu kann theerndhuduma theernthuduma venum vennum mudiyuma poren veliya yaaravathu pannangala pannangalaa ellarukkum thavira vaangi kudikka romba adikudhu adikuthu thookam varudhu pasikudhu velicham inniku innaiku naalaikku ennoda""".split())


def _tamil_lexicon() -> frozenset[str]:
    try:
        from jarvis.integrations.whatsapp.personal_reply.language import _TAMIL_SEED
        return frozenset(_TAMIL_SEED) | _COMMAND_WORDS
    except Exception:
        return _COMMAND_WORDS


_LEXICON = _tamil_lexicon()
_WORD = re.compile(r"[a-z]+")


def tamil_words(text: str) -> list[str]:
    """Tamil words (Latin script) in ``text`` - only real lexicon words, never guesses from word endings."""
    return [w for w in _WORD.findall((text or "").lower()) if w in _LEXICON and w not in _ENGLISH_HOMOGRAPHS]


# Words in the Tamil lexicon that are also everyday English in commands.
_ENGLISH_HOMOGRAPHS = frozenset({"en", "ana", "pa", "ma", "va", "vai", "ku", "nu", "edu", "ok", "po", "mama", "ethu", "adi"})


def is_thanglish(text: str) -> bool:
    words = _WORD.findall((text or "").lower())
    if not words:
        return False
    ta = tamil_words(text)
    return len(ta) >= 2 or (len(ta) == 1 and (len(words) <= 4 or ta[0] in _COMMAND_WORDS))


# ------------------------------------------------------------------ preference ("reply in thanglish")
def get_preference() -> str:
    try:
        value = json.loads(_STATE.read_text(encoding="utf-8")).get("reply", AUTO)
        return value if value in (AUTO, ENGLISH, THANGLISH) else AUTO
    except Exception:
        return AUTO


def set_preference(mode: str) -> str:
    mode = mode if mode in (AUTO, ENGLISH, THANGLISH) else AUTO
    try:
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps({"reply": mode}), encoding="utf-8")
    except Exception:
        pass
    return mode


def reply_language(text: str, preference: Optional[str] = None) -> str:
    pref = preference or get_preference()
    if pref in (ENGLISH, THANGLISH):
        return pref
    return THANGLISH if is_thanglish(text) or to_english_command(text) != text else ENGLISH


_SWITCH = [
    (re.compile(r"^(?:(?:please\s+)?(?:reply|talk|speak|answer|respond)\s+(?:to\s+me\s+)?(?:in|using)\s+(?:thanglish|tanglish|tamil)"
                r"|(?:thanglish|tanglish|tamil)\s*(?:la|le|lae)\s+(?:pesu|pesunga|sollu|reply\s+pannu|bathil\s+sollu)"
                r"|(?:use|switch\s+to)\s+(?:thanglish|tanglish))(?:\s+(?:da|please|from\s+now(?:\s+on)?))*[.!]?$"), THANGLISH),
    (re.compile(r"^(?:(?:please\s+)?(?:reply|talk|speak|answer|respond)\s+(?:to\s+me\s+)?(?:in|using)\s+english"
                r"|english\s*(?:la|le|lae)\s+(?:pesu|pesunga|sollu|reply\s+pannu)|(?:use|switch\s+to)\s+english)"
                r"(?:\s+(?:da|please|only|from\s+now(?:\s+on)?))*[.!]?$"), ENGLISH),
    (re.compile(r"^(?:reply|talk|speak|answer)\s+in\s+(?:my|the\s+same)\s+language|^match\s+my\s+language"
                r"|^(?:set\s+)?(?:reply\s+)?language\s+(?:to\s+)?auto(?:matic)?[.!]?$"), AUTO),
]


def match_language_switch(text: str) -> Optional[str]:
    t = " ".join((text or "").lower().split()).strip(" .!?")
    t = re.sub(r"^(?:hey\s+)?jarvis\s*,?\s*", "", t)
    t = re.sub(r"^(?:from\s+now(?:\s+on)?|hereafter|going\s+forward|always)\s*,?\s*", "", t)
    for pattern, mode in _SWITCH:
        if pattern.search(t):
            return mode
    return None


# ------------------------------------------------------------------ Thanglish command -> English command
_P_END = r"(?:\s+(?:da|di|dei|pa|ma|please|plz|jarvis|ippo|seekiram|konjam|ok|sari|seri|bro|machi|macha|dude|ji|nga|boss))*"
_OPEN = r"(?:(?:open|launch|start|run)\s+(?:pannu|panu|pannunga|pannidu|panni\s+vidu|panniduda)|thora|thorakku|thiranthu\s+vidu|open)"
_CLOSE = r"(?:(?:close|quit|exit|kill)\s+(?:pannu|panu|pannunga|pannidu|panni\s+vidu)|moodu|mudu|moodunga)"
_PLAY = r"(?:podu|podunga|pottu\s+vidu|potu\s+vidu|play\s+(?:pannu|panu|pannunga|panni\s+vidu))"
_SEND = r"(?:anuppu|anupu|anuppidu|anuppunga|anuppi\s+vidu|send\s+(?:pannu|panu|pannunga|pannidu)|(?:message|msg|text|whatsapp)\s+(?:pannu|panu|pannunga|pannidu|panniru|pannu\s+da))"
_TELL = r"(?:sollu|sollidu|sollunga|solli\s+vidu|solliru|solliduda|sollirunga)"
_EN_VERBS = (r"open|close|play|pause|stop|mute|unmute|lock|search|install|uninstall|download|restart|shutdown|shut down|"
             r"minimize|maximize|refresh|reload|copy|paste|save|delete|check|read|summarize|summarise|increase|decrease|"
             r"reduce|scroll down|scroll up|select all|undo|redo|call|connect|update|start|translate|type|record|share|"
             r"organize|organise|clean|sort|find|install|remind|minimise|pause|resume")
_PANNU = r"(?:pannu|panu|pannunga|pannuga|pannidu|panni\s+vidu|panni\s+kudu|panni\s+kudunga|panniduda|pannu\s+da)"
_DOWN = r"(?:kammi|korai|kurai|kuraichu|koraichu|korachidu|koraichidu|kuraichidu|reduce|decrease)"
_UP = r"(?:jaasthi|jasthi|athigam|adhigam|koodu|kootu|koottu|ethu|eathu|increase)"
_SET = r"(?:vai|vechidu|vachidu|vachu\s+vidu|set\s+" + _PANNU + r"|podu|pannu)"


def _clean(text: str) -> str:
    t = " ".join((text or "").strip().split())
    try:
        from jarvis.core.router.normalize import strip_ramble
        t = strip_ramble(t) or t  # "da pc ah lock pannu, i'm going out"
    except Exception:
        pass
    t = re.sub(r"^(?:(?:da|dei|bro|machi|macha|dude|boss|hey)\s*,?\s+)+", "", t, flags=re.I)
    t = re.sub(r"^(?:(?:hey\s+)?jarvis\s*,?\s*|um+\s+|uh+\s+|(?:can|could|would)\s+(?:you|u)\s+(?:please\s+)?|please\s+|plz\s+|kindly\s+)+",
               "", t, flags=re.I)
    t = re.sub(r"\s*,?\s+(?:jarvis|please|plz|thanks|thank\s+you)$", "", t, flags=re.I)
    t = re.sub(r"^(?:konjam|please|plz|seekiram)\s+", "", t, flags=re.I)
    return t.strip(" .!?")


def to_english_command(text: str) -> str:
    """English command for a Thanglish one ("chrome open pannu" -> "open chrome"); ``text`` itself otherwise."""
    raw = _clean(text)
    t = raw.lower()
    if not t or not (set(_WORD.findall(t)) & _LEXICON):
        return text
    if re.search(r"\b(?:venam|vendam|vendaam|vendaa|pannadha|pannaadha|pannatha|koodadhu|illa\s+illa|illa\s+venam)\b\s*,|,\s*(?:illa|illa\s+illa)\b", t):
        return text   # two clauses with a Tanglish 'not / no': the constraint layer splits them first, then each is translated
    body = re.sub(_P_END + "$", "", t).strip()
    body = re.sub(r"(?:^|\s+)konjam\b\s*", " ", body).strip()
    # "ellaa files um", "ellam photos yum": all of them
    body = re.sub(r"\b(?:ellaa|ella|ellam|ellame|ellathaiyum|ellathayum|motham)\s+(\w+)(?:\s+(?:um|yum|vum))?\b", r"all \1", body)
    # the object marker after the thing named first: "volume ah 48 ku vai", "chrome ah open pannu"
    body = re.sub(r"^(\S+(?:\s+\S+)?)\s+(?:ah|aa|ai|a)\s+(?=\S)", r"\1 ", body)

    def keep(fragment: str) -> str:  # original casing for names / message text
        i = raw.lower().find(fragment)
        return raw[i:i + len(fragment)] if i >= 0 else fragment

    # media: "paatu stop pannu", "paatu niruthu", "next paatu podu", "munnadi paatu"
    m = re.fullmatch(r"(?:(?:inda|indha|this)\s+)?(?:paatu|paattu|pattu|paadal|song|music)\s+(?:ah\s+|a\s+)?(?:stop|niruthu|nirutthu|niruthunga|"
                     r"pause|nippattu)(?:\s+" + _PANNU + r")?", body)
    if m:
        return "pause the music"
    m = re.fullmatch(r"(?P<d>next|adutha|aduththa|previous|munnadi|munnaadi|pazhaya)\s+(?:paatu|paattu|pattu|paadal|song|track)(?:\s+(?:podu|"
                     r"potu|play|pannu|vai|vei))?", body)
    if m:
        return "next track" if m.group("d") in ("next", "adutha", "aduththa") else "previous track"
    # word order: "wifi on pannu phone la" == "phone la wifi on pannu"
    m = re.fullmatch(r"(?P<x>[a-z ]{2,30}?)\s+(?P<s>on|off)\s+" + _PANNU + r"\s+(?P<d>phone|mobile)\s*(?:la|le|il|lla)", body)
    if m:
        return f"turn {m.group('s')} {m.group('x').strip()} on my phone"
    # two steps: "word open pannitu volume 10 ku vai" -> "open word and then set volume to 10"
    parts = re.split(r"\s+(?:pannitu|pannittu|panitu|pannittu)\s+", body, maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        first, second = to_english_command(parts[0] + " pannu"), to_english_command(parts[1])
        if first != parts[0] + " pannu" and second != parts[1]:
            return f"{first} and then {second}"
    # reminders: "kumar ku call pannanum nu 5 manikku remind pannu"
    m = re.fullmatch(r"(?P<x>.+?)\s+(?:nu|apdinu)\s+(?:(?P<n>\d{1,2})\s*(?:manikku|mani\s*ku|mani\s+ku)\s+)?(?:remind|nyabagam)\s+" + _PANNU
                     + r"(?:\s+(?P<n2>\d{1,2})\s*(?:manikku|mani\s*ku))?", body)
    if m:
        x = m.group("x")
        c = re.fullmatch(r"(?P<w>[a-z][a-z .]{0,30}?)\s*(?:ku|kku|ukku)\s+call\s+(?:pannanum|panna\s+venum|pannu)", x)
        what = f"call {keep(c.group('w'))}" if c else keep(re.sub(r"\s+(?:pannanum|panna\s+venum)$", "", x))
        n = m.group("n") or m.group("n2")
        return f"remind me to {what}" + (f" at {n}" if n else "")
    # questions and chat
    m = re.fullmatch(r"(?P<x>[a-z0-9 .+-]{2,40}?)\s+(?:na|naa|nna|endral|endraal)\s+(?:enna|yenna|ennadhu|ennaadhu)", body)
    if m:
        return f"what is {keep(m.group('x'))}"
    m = re.fullmatch(r"(?:(?P<d>inniku|innaiku|indru|naalaikku|nalaiku)\s+)?(?:en\s+|ennoda\s+)?(?P<w>calendar|schedule|screen|to\s*do\s*list)\s*(?:la|le|il)\s+"
                     r"(?:enna|yenna)\s+(?:iruku|irukku|irukka)", body)
    if m:
        day = {"naalaikku": " tomorrow", "nalaiku": " tomorrow"}.get(m.group("d") or "", " today" if m.group("d") else "")
        return f"what's on my {m.group('w')}{day if m.group('w') in ('calendar', 'schedule') else ''}".strip()
    if re.fullmatch(r"whats?\s*app\s*(?:la|le|il)\s+(?:yaar|yaaru|yar|yaru|evan|evanga)\s+(?:message|msg|text)\s+"
                    r"(?:pannirukka|pannirukanga|panniruka|pannanga|anupirukka|anupirukanga|anupichirukanga)", body):
        return "who messaged me on whatsapp"
    # "whatsapp la evlo message vandhirukku" / "evlo unread message iruku": how many unread messages
    if re.fullmatch(r"(?:whats?\s*app\s*(?:la|le|il)\s+)?(?:(?:evlo|evalo|evvalavu|ethana|eththana)\s+(?:unread\s+|new\s+|puthu\s+)?"
                    r"(?:message|messages|msg|msgs|text)|(?:unread\s+)?(?:message|messages|msg|msgs)\s+(?:evlo|evalo|ethana))\s+"
                    r"(?:vandhirukku|vandhiruku|vanthirukku|vanthiruku|vandhuruku|iruku|irukku|irukka|pending)(?:\s+(?:whats?\s*app\s*(?:la|le|il)))?", body):
        return "how many unread whatsapp messages"
    if re.fullmatch(r"whats?\s*app\s*(?:la|le|il)\s+(?:enna|yenna)\s+(?:puthusa|pudhusa|new\s*ah|new)(?:\s+(?:iruku|irukku|vandhirukku))?", body):
        return "summarize my whatsapp"
    m = re.fullmatch(r"(?P<p>[a-z][a-z .]{1,30}?)\s+(?:enna|yenna)\s+(?:message|msg|text)\s+(?:pannirukanga|pannirukka|panniruka|pannaru|"
                     r"pannanga|anupirukanga|anupichirukanga|anupirukka)", body)
    if m:
        return f"what did {keep(m.group('p'))} say"
    if re.fullmatch(r"(?:en\s+)?(?:message|msg|text)\s+(?:anupchaa|anupiyaa|anuppiyaa|anupicha|anupuniya|poyiducha|poocha|pochaa|sent\s+aa)", body):
        return "did the message go through"
    m = re.fullmatch(r"(?:en\s+|ennoda\s+)?(?P<f>[a-z0-9 .+-]{2,40}?)\s+(?:enga|engey|engae)\s+(?:iruku|irukku|irukka)(?:\s+nu\s+(?:thedu|paaru|kandupidi|sollu))?", body)
    if m:
        return f"where's my {keep(m.group('f'))}"
    m = re.fullmatch(r"(?:phone|mobile)\s*(?:la|le|il)\s+(?P<x>[a-z -]{2,20}?)\s+(?P<s>on|off)\s+" + _PANNU, body)
    if m:
        return f"turn {m.group('s')} {m.group('x')} on my phone"
    m = re.fullmatch(r"(?:screen|brightness|velicham)\b.*?\b(?P<dir>" + _DOWN + "|" + _UP + r")(?:\s+" + _PANNU + ")?", body)
    if m and not re.search(r"\b(?:volume|sound|saththam)\b", body):
        return "dim the screen" if re.fullmatch(_DOWN, m.group("dir")) else "make the screen brighter"
    for pat, eng in ((r"(?:romba\s+)?bore\s+(?:adikudhu|adikuthu|adikkudhu)", "i'm so bored"),
                     (r"(?:romba\s+)?(?:tired|tayard)\s+(?:ah\s+)?(?:iruku|irukku)", "i'm so tired"),
                     (r"(?:romba\s+)?thookam\s+(?:varudhu|varuthu)", "i'm sleepy"), (r"(?:romba\s+)?pasikudhu", "i'm hungry")):
        if re.fullmatch(pat, body):
            return eng

    # "unread mattum sollu" - just tell me X
    m = re.fullmatch(r"(?P<x>.+?)\s+(?:mattum|matum)\s+(?:sollu|sollunga|sollungo|kaattu|kattu|kaatu|paaru)(?P<on>\s+on\s+\S+)?", body)
    if m:
        x = m.group("x").strip()
        if re.fullmatch(r"(?:unread|pudhu|new)(?:\s+(?:messages?|msgs?))?", x):
            x = "unread messages"
        return f"show me {x}{m.group('on') or ''}"
    # a mode: "sleep la podu" (put it to sleep), "silent mode la vai", "dark mode la podu"
    m = re.fullmatch(r"(?P<x>sleep|hibernate|silent|airplane|flight|dark|light|focus|do\s+not\s+disturb|dnd)(?:\s+mode)?\s+"
                     r"(?:la|le|lla|ku|kku)\s+(?:podu|potu|vai|vei|pannu|panu|maathu|mathu)", body)
    if m:
        x = m.group("x")
        return "put the pc to sleep" if x == "sleep" else ("hibernate the pc" if x == "hibernate" else f"turn on {x} mode")
    # a channel said first: "whatsapp la priya ku hi anuppu" (also "whatsap", "wa")
    channel = re.match(r"^(?:whats?\s*app?|whatsap|watsapp|wa)\s+(?:la|le|il|lla|vazhiya|mela|moolama)\s+", body)
    if channel:
        body = body[channel.end():]
    # messages: "amma ku late aagum nu message anuppu", "arun kitta naan varala nu sollu"
    m = re.fullmatch(r"(?P<who>[a-z][a-z .]{0,30}?)\s*(?:ku|kku|ukku|kitta)\s+(?:" + _SEND + r")\s+['\"]?(?P<msg>[^'\"]+?)['\"]?", body)
    if m:   # "vignesh ku anuppu 'ready'": the verb before the quoted message
        return f"send a message to {keep(m.group('who').strip())} saying {keep(m.group('msg').strip())}"
    m = re.fullmatch(r"(?P<who>[a-z][a-z .]{0,30}?)\s*(?:ku|kku|ukku|kitta)\s+(?P<msg>(?:\S+\s+){0,5}?\S+)\s+(?:" + _SEND + ")", body)
    if m and not re.search(r"\b(?:nu|apdinu|endru|nnu)\b", m.group("msg")):
        # "priya ku hi anuppu": a short message without the quotative "nu"
        return f"send a message to {keep(m.group('who').strip())} saying {keep(m.group('msg').strip())}"
    m = re.fullmatch(r"(?P<who>[a-z][a-z .]{0,30}?)\s*(?:ku|kku|ukku|kitta)\s+(?P<msg>.+?)\s+(?:nu|apdinu|endru|nnu)\s+"
                     r"(?:(?:whatsapp\s+)?(?:message|msg|text)\s+)?(?:" + _SEND + "|" + _TELL + ")", body)
    if m:
        return f"send a message to {keep(m.group('who').strip())} saying {keep(m.group('msg').strip())}"
    m = re.fullmatch(r"(?P<who>[a-z][a-z .]{0,30}?)\s*(?:ku|kku|ukku)\s+call\s+" + _PANNU, body)
    if m:
        return f"call {keep(m.group('who').strip())}"

    # volume / brightness
    m = re.fullmatch(r"(?:volume|sound|saththam|sattham)\s+(?P<n>\d{1,3})\s*(?:ku|kku|%|percent)?\s*" + _SET, body)
    if m:
        return f"set volume to {m.group('n')}"
    m = re.fullmatch(r"brightness\s+(?P<n>\d{1,3})\s*(?:ku|kku|%|percent)?\s*" + _SET, body)
    if m:
        return f"set brightness to {m.group('n')}"
    m = re.fullmatch(r"(?P<what>volume|sound|saththam|sattham|brightness)\s+(?P<dir>" + _DOWN + "|" + _UP + r")(?:\s+" + _PANNU + ")?", body)
    if m:
        what = "brightness" if m.group("what") == "brightness" else "volume"
        return f"{what} {'down' if re.fullmatch(_DOWN, m.group('dir')) else 'up'}"
    if re.fullmatch(r"(?:sound|volume|saththam)\s+(?:mute\s+" + _PANNU + r"|off\s+" + _PANNU + r"|niruthu|illama\s+" + _PANNU + ")", body):
        return "mute"

    # "youtube la lofi music podu" / "lofi music podu" / "song podu"
    m = re.fullmatch(r"(?:youtube\s*(?:la|le|il)\s+)(?P<q>.+?)\s+" + _PLAY, body)
    if m:
        return f"play {keep(m.group('q'))} on youtube"
    m = re.fullmatch(r"(?:spotify\s*(?:la|le|il)\s+)(?P<q>.+?)\s+" + _PLAY, body)
    if m:
        return f"play {keep(m.group('q'))} on spotify"
    m = re.fullmatch(r"(?P<q>.+?)\s+" + _PLAY, body)
    if m:
        q = m.group("q")
        return "play music" if q in ("song", "songs", "paatu", "paattu", "music", "oru song", "oru paatu") else f"play {keep(q)}"

    # "google la ipl score thedu", "ipl score search pannu"
    m = re.fullmatch(r"(?:google\s*(?:la|le|il)\s+)?(?P<q>.+?)\s+(?:thedu|theadu|thedunga|search\s+" + _PANNU + r"|google\s+" + _PANNU + ")", body)
    if m:
        return f"search google for {keep(m.group('q'))}"

    # "screenshot edu", "oru screenshot eduthu vai"
    if re.fullmatch(r"(?:oru\s+)?(?:screenshot|screen\s*shot|ss)\s+(?:edu|eduthu|edunga|eduthu\s+vai|eduthudu|" + _PANNU + ")", body):
        return "take a screenshot"
    if re.fullmatch(r"(?:oru\s+)?(?:screenshot|ss)\s+(?:edu|eduthu)\s+(?:inga|ingae|here)\s+(?:paste|potu|podu)\s*(?:" + _PANNU + ")?", body):
        return "take a screenshot and paste it here"

    # "chrome open pannu", "chrome la gmail open pannu", "notepad close pannu"
    m = re.fullmatch(r"(?P<host>[a-z0-9 .+-]{2,30}?)\s*(?:la|le|il)\s+(?P<obj>[a-z0-9 .+-]{2,40}?)\s+" + _OPEN, body)
    if m:
        host, obj = keep(m.group("host")), keep(m.group("obj"))
        if host.lower() in ("chrome", "google chrome", "edge", "firefox", "brave", "browser"):
            return f"open {obj}"  # sites open in the browser anyway
        return f"open {obj} in {host}"
    m = re.fullmatch(r"(?P<obj>[a-z0-9 .+-]{2,40}?)\s+" + _OPEN, body)
    if m and not tamil_words(m.group("obj")):
        return f"open {keep(m.group('obj'))}"
    m = re.fullmatch(r"(?P<obj>[a-z0-9 .+-]{2,40}?)\s+" + _CLOSE, body)
    if m and not tamil_words(m.group("obj")):
        return f"close {keep(m.group('obj'))}"
    # "<thing> type pannu" -> type <thing>
    m = re.fullmatch(r"(?P<text>.+?)\s+(?:nu\s+)?type\s+(?:" + _PANNU + "|adi)", body)
    if m:
        return f"type {keep(m.group('text'))}"
    # generic "<object> <english verb> pannu": "wifi on pannu", "pc lock pannu", "volume increase pannu"
    m = re.fullmatch(r"(?P<obj>[a-z0-9 .+-]{1,40}?)\s+(?P<verb>" + _EN_VERBS + r"|on|off)\s+" + _PANNU, body)
    if m:
        verb, obj = m.group("verb"), keep(m.group("obj"))
        if verb in ("on", "off"):
            return f"turn {verb} {obj}"
        return f"{verb} {obj}"
    m = re.fullmatch(r"(?P<verb>" + _EN_VERBS + r")\s+(?P<obj>.+?)\s+" + _PANNU, body)  # "open chrome pannu"
    if m:
        return f"{m.group('verb')} {keep(m.group('obj'))}"
    m = re.fullmatch(r"(?P<verb>" + _EN_VERBS + r")\s+" + _PANNU, body)  # "mute pannu", "lock pannu"
    if m:
        return m.group("verb")

    # questions: "time enna", "inniku date enna", "battery evlo iruku", "weather eppadi iruku"
    if re.fullmatch(r"(?:ippo\s+)?(?:time|mani)\s+(?:enna|ennachu|evlo|evvalavu|aachu)(?:\s+(?:aagudhu|aachu|agudhu))?", body):
        return "what time is it"
    if re.fullmatch(r"(?:inniku|innaiku|indru)?\s*(?:date|thethi|theadhi)\s+(?:enna|ennachu)", body):
        return "what is today's date"
    if re.fullmatch(r"(?:en\s+|laptop\s+|pc\s+)?(?:battery|charge)\s+(?:evlo|evvalavu|eppadi|enna)(?:\s+(?:iruku|irukku))?", body):
        return "what's my battery"
    m = re.fullmatch(r"(?:(?P<place>[a-z ]{2,20}?)\s*(?:la|le)\s+)?(?:weather|climate|mazhai)\s+(?:eppadi|epdi|enna)(?:\s+(?:iruku|irukku|irukum))?", body)
    if m:
        return f"what's the weather in {keep(m.group('place'))}" if m.group("place") else "what's the weather"
    return _gloss(body, keep) or text


# ------------------------------------------------------------------ gloss: shapes the fixed patterns above do not cover
_NOW = r"(?:ippo|ippodhu|ipo)\s+"


def _gloss(body: str, keep) -> Optional[str]:
    """Further Thanglish shapes: an object-marker + show / read, a spoken remark after the command, setting words
    (volume, brightness, battery) said around a state, a request for something with "venum"."""
    # a first-person remark after the command is not part of it: "pc ah lock pannidu, naan veliya poren"
    head, sep, rest = body.partition(",")
    if sep and re.match(r"\s*(?:naan|nan|en|enakku|ennaku|naa)\b", rest) and len(head.split()) >= 2:
        out = to_english_command(head)
        if out != head:
            return out
    # show / open a folder: "downloads folder ah kaatu", "desktop ah kaattu"
    m = re.fullmatch(r"(?P<f>downloads?|documents?|desktop|pictures?|music|videos?)(?:\s+folder)?\s+(?:ah|a)?\s*(?:kaatu|kaattu|kattu|kaatunga|open\s+" + _PANNU + r")", body)
    if m:
        return f"open my {m.group('f')} folder"
    # read the unread messages
    if re.fullmatch(r"(?:unread|pudhu|new|puthu)\s+(?:messages?|msgs?)\s+(?:ellam|ellaa|ellame|all)\s+(?:padichu|padithu|padi)\s+(?:kaattu|kaatu|sollu|kattu)", body):
        return "read my unread messages"
    if re.fullmatch(r"(?:yaar|yaaravathu|yarum|yaarum)\s+(?:message|msg|text)\s+(?:pannangala|pannangalaa|pannaangala|pannirukangala|anupnangala)", body):
        return "who messaged me on whatsapp"
    # settings said around a Tanglish verb
    if re.fullmatch(r"(?:volume|volum|sound|saththam|sattham)\s+(?:ah\s+)?(?:koraiyi|koraiyu|korai|kuraiyu|kuraiyi|kammi|korachidu|koraichidu|kuraichidu)(?:\s+" + _PANNU + ")?", body):
        return "volume down"
    if re.fullmatch(r"(?:romba\s+)?(?:sathama|satham|saththama|sattama)\s+(?:irukku|iruku|irukkudhu|adikudhu)", body):
        return "volume down"
    if re.fullmatch(r"(?:sound|volume|saththam)\s+(?:ah\s+)?(?:full|max|maximum)(?:\s+ah)?\s+(?:vachidu|vechidu|vai|vei|podu|" + _PANNU + ")", body):
        return "set volume to 100"
    if re.fullmatch(r"(?:screen|display|brightness|velicham)\s+(?:ah\s+)?(?:konjam\s+)?(?:dim|kammi|korai|korachidu|koraichidu)(?:\s+" + _PANNU + ")?", body) \
            or re.fullmatch(r"(?:kann|kan|kannu)\s+(?:valikuthu|valikkudhu|valikudhu|erichal)\s*,?\s*(?:screen\s+)?(?:romba\s+)?(?:bright|velicham)", body):
        return "dim the screen"
    if re.fullmatch(r"(?:laptop|pc|en)?\s*(?:battery|charge)\s+(?:evlo|evvalavu|eppadi)(?:\s+percent)?\s+(?:iruku|irukku|irukkudhu)", body) \
            or re.fullmatch(r"(?:laptop|pc)\s+(?:charge|battery)\s+(?:theerndhuduma|theerndhuduchaa|theernthuduma|kammi\s+aagiduma|mudinjiduma)", body):
        return "what's my battery level"
    m = re.fullmatch(r"(?P<x>wifi|bluetooth|hotspot|data|mobile\s+data|torch|flashlight)\s+(?P<s>on|off|aaf|of|aff)\s+" + _PANNU + r"\s+(?P<d>phone|mobile|phonela|phone\s*la|mobilela)", body)
    if m:
        return f"turn {'on' if m.group('s') == 'on' else 'off'} {m.group('x')} on my phone"
    m = re.fullmatch(r"(?:phone|mobile)\s*(?:la|le)\s+(?P<x>wifi|bluetooth|hotspot|data|torch|flashlight)\s+(?:ah\s+)?(?P<s>on|off)\s+(?:pannu|panniru|pannidu|pannunga)", body)
    if m:
        return f"turn {m.group('s')} {m.group('x')} on my phone"
    # a thing wanted: "enakku oru 12 letter password venum"
    m = re.fullmatch(r"(?:enakku|ennaku)\s+(?:oru\s+)?(?P<n>\d{1,3})\s*(?:letter|character|char|digit)s?\s+password\s+(?:venum|vennum|venumnga)", body)
    if m:
        return f"generate a {m.group('n')} character password"
    if re.fullmatch(r"(?:tamil|thamizh|thanglish|tanglish)\s*(?:la|le)\s+(?:pesu|pesunga|sollu)(?:\s+ini\s+mel)?", body):
        return "reply in thanglish"
    # reminders: "anju nimisham la water kudikka sollu", "naalaiku kaalaila 7 manikku ennai ezhuppu"
    num = {"oru": 1, "onnu": 1, "rendu": 2, "moonu": 3, "naalu": 4, "anju": 5, "aaru": 6, "ezhu": 7, "ettu": 8, "onbadhu": 9, "pathu": 10}
    m = re.fullmatch(r"(?P<n>\d{1,3}|" + "|".join(num) + r")\s+(?:nimisham|nimidam|minutes?|mins?)\s*(?:la|le|ku|kku)?\s+(?P<what>.+?)\s+(?:sollu|sollunga|solliru|nyabagam\s+" + _PANNU + ")", body)
    if m:
        n = m.group("n") if m.group("n").isdigit() else str(num[m.group("n")])
        what = m.group("what")
        what = {"water kudikka": "drink water", "saapida": "eat", "thoongu": "sleep"}.get(what, what)
        return f"remind me in {n} minutes to {keep(what)}"
    m = re.fullmatch(r"(?:(?P<d>naalaiku|naalaikku|nalaiku|inniku|innaiku)\s+)?(?:kaalaila|kaalaiyil|morning)\s+(?P<n>\d{1,2})\s*(?:manikku|mani\s*ku)\s+(?:ennai|enna|ennaa)\s+(?:ezhuppu|ezhuppunga|ezhupu|eluppu)", body)
    if m:
        day = "tomorrow" if (m.group("d") or "").startswith(("naal", "nal")) else "today"
        return f"remind me {day} at {m.group('n')} am to wake up"
    return None



# ------------------------------------------------------------------ replies
def prompt_instruction(language: str) -> str:
    if language != THANGLISH:
        return ""
    return ("Reply in Thanglish: Tamil written in English letters, casually mixed with English the way people in "
            "Tamil Nadu text (for example \"Seri, naan check panren\", \"Adhu 25 degree dhaan, konjam hot ah irukum\"). "
            "Never use Tamil script. Keep technical words, names and numbers in English.")


_CONFIRMATIONS = [
    (r"(?P<x>.+?) is open\.?", "{x} open panniten."),
    (r"(?P<x>.+?) is closed\.?", "{x} close panniten."),
    (r"Opened (?P<x>.+?)\.?", "{x} open panniten."),
    (r"Opening (?P<x>.+?)\.?", "{x} open panren."),
    (r"Closed (?P<x>.+?)\.?", "{x} close panniten."),
    (r"Volume set to (?P<x>\d+) percent\.?", "Volume {x} percent ku vechiten."),
    (r"Volume is (?P<x>\d+) percent\.?", "Volume ippo {x} percent la iruku."),
    (r"Volume increased\.?", "Volume jaasthi panniten."),
    (r"Volume decreased\.?", "Volume kammi panniten."),
    (r"Muted\.?|Volume muted\.?", "Sound mute panniten."),
    (r"Unmuted\.?|Volume unmuted\.?", "Sound thirumba on panniten."),
    (r"Brightness set to (?P<x>\d+) percent\.?", "Brightness {x} percent ku vechiten."),
    (r"Screen brightness is (?P<x>\d+) percent\.?", "Brightness ippo {x} percent la iruku."),
    (r"Screenshot saved\.?", "Screenshot eduthuten, save aayiduchu."),
    (r"Took a screenshot and pasted it(?P<x>.*?)\.?", "Screenshot eduthu paste panniten."),
    (r"Playing (?P<x>.+?) on YouTube\.?", "YouTube la {x} play panren."),
    (r"Playing on YouTube\.?", "YouTube la play panren."),
    (r"Timer set for (?P<x>.+?)\.?", "{x} ku timer vechiten."),
    (r"Done\.?", "Mudinjiduchu."),
    (r"Done on the phone\.?", "Phone la panniten."),
    (r"Copied\.?", "Copy panniten."),
    (r"Pasted\.?", "Paste panniten."),
    (r"Pasted into (?P<x>.+?)\.?", "{x} la paste panniten."),
    (r"Stopped\.?", "Niruthiten."),
    (r"Speech stopped\.?", "Seri, pesaradha niruthiten."),
    (r"Sent\.?", "Anuppiten."),
    (r"Typed: (?P<x>.+)", "Type panniten: {x}"),
    (r"It is (?P<x>.+?) on (?P<y>.+?)\.?", "Ippo mani {x}, {y}."),
    (r"Your phone is connected \((?P<x>.+?)\)\.?", "Unga phone connect aayiduchu ({x})."),
    (r"Command was negated\. No action taken\.?", "Seri, edhuvum pannala."),
    (r"I didn't hear a command\. How can I help you\?", "Command kekkala. Enna pannanum?"),
]
_CONFIRMATIONS = [(re.compile(p, re.I), r) for p, r in _CONFIRMATIONS]


def in_thanglish(message: str) -> str:
    """Thanglish version of a known short confirmation; other text (already a model answer, details) unchanged."""
    msg = (message or "").strip()
    for pattern, template in _CONFIRMATIONS:
        m = pattern.fullmatch(msg)
        if m:
            return template.format(**m.groupdict())
    return message


# ------------------------------------------------------------------ Tamil script -> Latin (Thanglish spelling)
_TA_VOWELS = {"அ": "a", "ஆ": "aa", "இ": "i", "ஈ": "ee", "உ": "u", "ஊ": "oo", "எ": "e", "ஏ": "ae", "ஐ": "ai", "ஒ": "o",
              "ஓ": "o", "ஔ": "au", "ஃ": "h"}
_TA_CONS = {"க": "k", "ங": "ng", "ச": "s", "ஞ": "nj", "ட": "d", "ண": "n", "த": "th", "ந": "n", "ப": "p", "ம": "m",
            "ய": "y", "ர": "r", "ல": "l", "வ": "v", "ழ": "zh", "ள": "l", "ற": "r", "ன": "n", "ஜ": "j", "ஷ": "sh",
            "ஸ": "s", "ஹ": "h"}
_TA_SIGNS = {"ா": "aa", "ி": "i", "ீ": "ee", "ு": "u", "ூ": "oo", "ெ": "e", "ே": "ae", "ை": "ai", "ொ": "o", "ோ": "o",
             "ௌ": "au", "்": ""}


def has_tamil_script(text: str) -> bool:
    return any("஀" <= ch <= "௿" for ch in text or "")


def tamil_to_latin(text: str) -> str:
    out: list[str] = []
    chars = list(text or "")
    for i, ch in enumerate(chars):
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if ch in _TA_CONS:
            out.append(_TA_CONS[ch] + ("" if nxt in _TA_SIGNS else "a"))
        elif ch in _TA_SIGNS:
            out.append(_TA_SIGNS[ch])
        elif ch in _TA_VOWELS:
            out.append(_TA_VOWELS[ch])
        else:
            out.append(ch)
    return "".join(out)


# Whisper prompt that nudges recognition toward Thanglish spelling (Latin letters, Tamil words kept as spoken).
STT_PROMPT = ("Jarvis, chrome open pannu. Volume konjam kammi pannu. Amma ku late aagum nu message anuppu. "
              "Seri da, naan varen. Enna time aachu?")
