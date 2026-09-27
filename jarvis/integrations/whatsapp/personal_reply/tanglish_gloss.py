"""Meanings of common Tanglish words, so a small local model understands the message it is answering.

Used ONLY for understanding the incoming message (shown to the model as a hint). Reply wording still comes from
the owner's own messages with this person - the glossary never writes replies.
"""
from __future__ import annotations

import re

GLOSS: dict[str, str] = {
    # questions
    "enna": "what", "ena": "what", "yenna": "what", "ennachu": "what happened", "enachu": "what happened",
    "epdi": "how", "eppadi": "how", "epadi": "how", "eppo": "when", "epo": "when", "ippo": "now", "ipo": "now",
    "enga": "where", "yenga": "where", "yaaru": "who", "yaru": "who", "yaar": "who", "yen": "why", "yenda": "why (to a guy)",
    "evlo": "how much / how many", "evvalavu": "how much", "ethana": "how many", "edhuku": "why / for what",
    "ethuku": "why / for what", "yedhuku": "why",
    # common verbs (question forms end in -ya / -ngala / -la)
    "saptiya": "did you eat?", "saaptiya": "did you eat?", "sapteengala": "did you eat? (respectful)",
    "saptacha": "have you eaten?", "sapadu": "food", "saapadu": "food", "saptu": "after eating",
    "varuviya": "will you come?", "varuveengala": "will you come? (respectful)", "varriya": "are you coming?",
    "variya": "are you coming?", "vaa": "come", "va": "come", "vaanga": "come (respectful)", "vanga": "come (respectful)",
    "varen": "I'm coming", "varan": "he is coming", "varala": "not coming / didn't come", "vandhen": "I came",
    "vandhutiya": "did you arrive?", "vanthutiya": "did you arrive?", "vandhachu": "arrived",
    "poren": "I'm going", "poitu": "after going", "po": "go", "poda": "go away (casual)", "pogalam": "shall we go",
    "pannu": "do", "panren": "I'm doing / I will do", "pannitiya": "did you do it?", "panniten": "I did it",
    "panra": "doing", "panringa": "you are doing (respectful)", "pannalam": "we can do / let's do",
    "sollu": "tell", "sonna": "said", "sonnen": "I said", "solren": "I'll tell", "sollunga": "tell (respectful)",
    "paaru": "look / see", "paathiya": "did you see?", "paathen": "I saw", "paakalam": "let's see / we'll see",
    "pesu": "talk", "pesalam": "let's talk", "pesuren": "I'll talk", "call pannu": "call me",
    "kudu": "give", "kudukren": "I'll give", "anuppu": "send", "anupu": "send", "anupiten": "I sent",
    "theriyuma": "do you know?", "theriyum": "I know", "theriyala": "I don't know", "theriyadhu": "don't know",
    "mudiyuma": "can you?", "mudiyum": "can", "mudiyadhu": "can't", "mudiyala": "couldn't / can't bear",
    "venuma": "do you want?", "venum": "want / need", "vendam": "don't want", "venam": "don't want",
    "thoongu": "sleep", "thoongitiya": "did you sleep?", "thoongala": "didn't sleep", "ezhundhutiya": "are you awake?",
    "kelambitiya": "have you left?", "kelambiten": "I've left", "kelambu": "leave / start", "reach aayita": "reached?",
    "iruka": "are you there?", "irukiya": "are you there?", "iruku": "there is / have", "irukku": "there is",
    "illa": "no / not there", "illai": "no", "illaya": "isn't it?", "irukeengala": "are you there? (respectful)",
    # answers / fillers
    "seri": "okay", "sari": "okay", "aama": "yes", "amam": "yes", "aamam": "yes", "hmm": "hmm / okay",
    "paravala": "no problem / it's fine", "parava": "no problem", "kandippa": "definitely", "nalla": "good",
    "nallaa": "well", "nalladhu": "good thing", "romba": "very", "konjam": "a little", "semma": "awesome",
    "super": "great", "mass": "awesome", "vera level": "next level / amazing", "summa": "just like that / nothing",
    "chumma": "just / for no reason", "sema": "awesome", "mokka": "boring / lame", "kadupu": "annoyed",
    "tension": "stressed", "bayama": "scared", "santhosham": "happy", "sogam": "sad", "kova": "angry",
    # time
    "inniku": "today", "innaiku": "today", "indru": "today", "naalaiku": "tomorrow", "nalaiku": "tomorrow",
    "nethu": "yesterday", "nettu": "yesterday", "kaalaila": "in the morning", "kalaila": "in the morning",
    "saayangalam": "evening", "rathri": "night", "raathiri": "night", "apram": "later", "appuram": "later / then",
    "aprom": "later", "seekiram": "quickly / soon", "late aagum": "will be late", "time aachu": "it's time / got late",
    # people / address
    "naan": "I", "nan": "I", "nee": "you", "ni": "you", "neenga": "you (respectful)", "unga": "your (respectful)",
    "un": "your", "en": "my", "enakku": "for me / I", "enaku": "for me", "unakku": "for you", "unaku": "for you",
    "namma": "our / us", "avan": "he", "aval": "she", "avanga": "they / she (respectful)",
    "da": "(friendly address, male)", "di": "(friendly address, female)", "dei": "hey (casual)",
    "machan": "buddy", "machi": "buddy", "nanba": "friend", "akka": "elder sister", "anna": "elder brother",
    "thambi": "younger brother", "amma": "mom", "appa": "dad", "paati": "grandma", "thatha": "grandpa",
    # places / things
    "veedu": "home", "veetla": "at home", "veetuku": "to home", "office la": "at office", "college la": "at college",
    "kadai": "shop", "saapadu": "food", "kaasu": "money", "panam": "money", "vela": "work", "velai": "work",
    "padikiren": "I'm studying", "padi": "study", "exam la": "in the exam", "class la": "in class",
    # particles
    "thaan": "only / indeed", "dhaan": "only / indeed", "mattum": "only", "kooda": "also / with", "ellam": "all",
    "ellarum": "everyone", "onnum": "nothing", "edhavadhu": "something / anything", "ah": "(question tag: is it?)",
    "aa": "(question tag)", "la": "in / at (suffix)", "ku": "to / for (suffix)",
}

_PHRASES = sorted((k for k in GLOSS if " " in k), key=len, reverse=True)
_WORD = re.compile(r"[a-z]+")
_SKIP = {"la", "ku", "aa", "ah", "en", "ni", "va", "po", "da", "di", "super", "tension", "hmm", "nalla", "un"}


def gloss(text: str, limit: int = 10) -> list[str]:
    """'word = meaning' hints for the Tanglish words in ``text`` (most informative first, max ``limit``)."""
    t = (text or "").lower()
    out: list[str] = []
    seen: set[str] = set()
    for phrase in _PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", t) and phrase not in seen:
            out.append(f"{phrase} = {GLOSS[phrase]}")
            seen.update(phrase.split())
    for w in _WORD.findall(t):
        if w in GLOSS and w not in seen and w not in _SKIP:
            out.append(f"{w} = {GLOSS[w]}")
            seen.add(w)
    return out[:limit]
