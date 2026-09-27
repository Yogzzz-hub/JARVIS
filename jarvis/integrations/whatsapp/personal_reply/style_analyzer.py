"""Build a compact ContactStyleProfile from the OWNER's messages to one contact.

Only USER-authored lines are analysed; the contact's own writing never shapes the owner's style.
"""
from __future__ import annotations

import re
import statistics
import time
from collections import Counter
from typing import Iterable

from jarvis.integrations.whatsapp.personal_reply import language as lang
from jarvis.integrations.whatsapp.personal_reply.models import ChatLine, ContactStyleProfile, Direction

_STOP = set("""i me my you your the a an and or but to of in on at for is are was were be been am it its this that
these those so if then just not no yes do did does have has had will would can could should with from by as up out
about what when where how why who which there here we us our they them their he she his her""".split())
_POLITE = re.compile(r"\b(?:please|kindly|regards|thank you|sir|madam|ma'am|dear|appreciate|apologi[sz]e|sincerely)\b", re.I)
_SLANG = re.compile(r"\b(?:lol|lmao|haha+|hehe+|bro|dude|da|di|dei|machan|machi|macha|ya|yaa|k|kk|u|ur|pls|plz|gonna|wanna)\b", re.I)
_HUMOR = re.compile(r"(?:\b(?:lol|lmao|haha+|hehe+|rofl)\b|😂|🤣|😆|😜|😝)", re.I)
_ACK = re.compile(r"^(?:ok(?:ay|ey)?|k+|seri|sari|haa+|ha+n|hmm+|yes|yeah|yep|sure|done|fine|noted|aama|cool|got it)\b[\s!.👍🙂😊]*$", re.I)


def _words(text: str) -> list[str]:
    return re.findall(r"[\w']+", text.lower())


def _first_phrase(text: str, n: int = 2) -> str:
    w = _words(text)
    return " ".join(w[:n]) if w else ""


def analyze(contact_id: str, display_name: str, lines: Iterable[ChatLine],
            preferences: dict | None = None) -> ContactStyleProfile:
    user = [ln for ln in lines if ln.direction == Direction.USER and ln.text.strip()]
    prof = ContactStyleProfile(contact_id=contact_id, display_name=display_name, preferences=dict(preferences or {}))
    prof.messages_analyzed = len(user)
    prof.updated_at = time.time()
    if not user:
        return prof
    texts = [ln.text.strip() for ln in user]

    # language mix (message level)
    labels = [lang.detect(t) for t in texts]
    known = [m for m in labels if m.label != lang.UNKNOWN]
    tang = sum(1 for m in known if lang.is_tanglish_mode(m.label))
    prof.tanglish_ratio = round(tang / len(known), 3) if known else 0.0
    prof.english_ratio = round(1 - prof.tanglish_ratio, 3) if known else 1.0
    pure_tanglish = sum(1 for m in known if m.label == lang.TANGLISH)
    if prof.tanglish_ratio < 0.2:
        prof.preferred_language = "ENGLISH"
    elif known and pure_tanglish / len(known) >= 0.5:
        prof.preferred_language = "TANGLISH"
    else:
        prof.preferred_language = "MIXED"

    # length
    lengths = [len(_words(t)) or 1 for t in texts]
    prof.avg_message_length = round(sum(lengths) / len(lengths), 2)
    prof.median_message_length = float(statistics.median(lengths))
    med = prof.median_message_length
    prof.typical_reply_length = ("1-3 words" if med <= 3 else "1 short sentence" if med <= 8
                                 else "1-2 sentences" if med <= 20 else "a few sentences")

    # emoji
    all_emojis = [e for t in texts for e in lang.emojis(t)]
    prof.emoji_frequency = round(len(all_emojis) / len(texts), 3)
    prof.common_emojis = [e for e, _ in Counter(all_emojis).most_common(6)]

    # punctuation / capitalization
    ends = sum(1 for t in texts if t[-1] in ".!?")
    expressive = sum(1 for t in texts if re.search(r"[!?]{2,}|\.{3,}", t))
    end_rate = ends / len(texts)
    prof.punctuation_style = ("expressive" if expressive / len(texts) >= 0.2 else "standard" if end_rate >= 0.6
                              else "minimal" if end_rate >= 0.15 else "none")
    starts_upper = sum(1 for t in texts if t[:1].isupper())
    all_lower = sum(1 for t in texts if t == t.lower())
    prof.capitalization_style = ("lowercase" if all_lower / len(texts) >= 0.7 else "sentence" if starts_upper / len(texts) >= 0.7
                                 else "mixed")

    # greetings / closings / acknowledgements / patterns
    openers = Counter(_first_phrase(t, 1) for t in texts if len(_words(t)) >= 3)
    greet = {"hi", "hey", "hello", "dei", "da", "bro", "machan", "machi", "good", "morning", "sir", "dear", "hii", "heyy", "vanakkam"}
    prof.greeting_patterns = [w for w, c in openers.most_common(10) if w in greet and c >= 2][:4]
    closers = Counter(_words(t)[-1] for t in texts if len(_words(t)) >= 3)
    close_words = {"da", "bro", "thanks", "regards", "bye", "tc", "di", "pa", "ma", "sir", "cheers"}
    prof.closing_patterns = [w for w, c in closers.most_common(10) if w in close_words and c >= 2][:4]
    acks = Counter(re.sub(r"[\s!.👍🙂😊]+$", "", t.lower()) for t in texts if _ACK.match(t))
    prof.acknowledgement_style = [a for a, _ in acks.most_common(4)]
    short = Counter(t.lower() for t in texts if len(_words(t)) <= 4)
    prof.response_patterns = [s for s, c in short.most_common(8) if c >= 2][:6]

    # vocabulary: learned ONLY from the owner's messages
    word_counts = Counter(w for t in texts for w in _words(t) if w not in _STOP and len(w) > 1 and not w.isdigit())
    prof.common_words = [w for w, c in word_counts.most_common(15) if c >= 2]
    tamil_counts = Counter(w for m in labels for w in m.tamil_words)
    bigrams = Counter()
    for t in texts:
        ws = _words(t)
        for a, b in zip(ws, ws[1:]):
            if lang.classify_token(a) == "TA" or lang.classify_token(b) == "TA":
                bigrams[f"{a} {b}"] += 1
    phrases = [w for w, c in tamil_counts.most_common(12) if c >= 2] + [p for p, c in bigrams.most_common(6) if c >= 2]
    prof.common_tanglish_phrases = phrases[:15]

    # tone
    polite = sum(1 for t in texts if _POLITE.search(t)) / len(texts)
    slang = sum(1 for t in texts if _SLANG.search(t)) / len(texts)
    score = (polite * 2.5 + (1 if prof.capitalization_style == "sentence" else 0) * 0.6 + end_rate * 0.6
             - slang * 1.6 - min(prof.emoji_frequency, 1.5) * 0.5 - (0.3 if med <= 3 else 0))
    prof.formality = ("PROFESSIONAL" if score >= 1.2 else "NEUTRAL" if score >= 0.45 else "CASUAL" if score >= -0.4 else "VERY_CASUAL")
    humor = sum(1 for t in texts if _HUMOR.search(t)) / len(texts)
    prof.humor_level = "HIGH" if humor >= 0.25 else "MEDIUM" if humor >= 0.08 else "LOW"
    questions = sum(1 for t in texts if "?" in t) / len(texts)
    prof.question_style = "often asks questions" if questions >= 0.3 else "sometimes asks" if questions >= 0.1 else "rarely asks"
    prof.directness = "HIGH" if med <= 5 else "MEDIUM" if med <= 15 else "LOW"
    prof.example_message_ids = [ln.message_id for ln in user[-10:] if ln.message_id]
    habits(prof, user, texts)

    # confidence: enough samples AND a consistent style
    n_factor = min(1.0, len(texts) / 40.0)
    spread = statistics.pstdev(lengths) / (prof.avg_message_length + 1)
    consistency = max(0.3, 1.0 - min(spread, 1.0) * 0.5)
    lang_consistency = max(prof.tanglish_ratio, prof.english_ratio)
    prof.confidence = round(n_factor * (0.6 * consistency + 0.4 * lang_consistency), 3)
    return prof


def default_profile(contact_profiles: list[ContactStyleProfile], owner_lines: list[ChatLine]) -> ContactStyleProfile:
    """DefaultUserStyleProfile: the owner's general style across approved chats (fallback only)."""
    prof = analyze("__default__", "Default (you)", owner_lines)
    prof.confidence = round(min(prof.confidence, 0.6), 3)  # never as trusted as a person-specific profile
    return prof


# ------------------------------------------------------------------ texting habits
ADDRESS_TERMS = ("da", "di", "dei", "bro", "bruh", "machan", "machi", "macha", "mama", "maams", "akka", "anna", "thambi",
                 "thangachi", "ma", "pa", "sis", "dude", "buddy", "nanba", "nanbaa", "sir", "madam", "maam", "darling",
                 "dear", "chellam", "kanna", "boss", "thala", "baby", "babe", "chief", "ji")
SHORTHAND = {"you": ("u",), "your": ("ur",), "are": ("r",), "okay": ("ok", "k", "kk"), "please": ("pls", "plz", "plss"),
             "tomorrow": ("tmrw", "tmr", "tmrow", "tomo"), "message": ("msg",), "thanks": ("thx", "tq", "ty", "tnx"),
             "because": ("coz", "bcoz", "cuz", "bcz"), "what": ("wat", "wht"), "good night": ("gn",),
             "good morning": ("gm",), "brother": ("bro",), "people": ("ppl",), "really": ("rly",)}
_LAUGH = re.compile(r"\b(?:a?ha(?:ha)+h?|he(?:he)+|hi(?:hi)+|lol+|lmao+|rofl)\b|😂+|🤣+|😆+", re.I)
_ELONG = re.compile(r"\b[a-z]*([a-z])\1{2,}[a-z]*\b", re.I)


def _emoji_runs(text: str) -> int:
    best, run, prev = 0, 0, ""
    for ch in text:
        if lang.is_emoji(ch) and ch not in "\ufe0f\u200d":
            run = run + 1 if ch == prev else 1
            prev = ch
            best = max(best, run)
        elif ch not in "\ufe0f\u200d":
            prev, run = "", 0
    return best


def habits(prof: ContactStyleProfile, user: list[ChatLine], texts: list[str]) -> None:
    n = len(texts)
    all_emojis = [e for t in texts for e in lang.emojis(t)]
    prof.emoji_vocab = [e for e, _ in Counter(all_emojis).most_common(20)]
    with_emoji = [t for t in texts if lang.emojis(t)]
    if with_emoji:
        pos = Counter()
        for t in with_emoji:
            plain = "".join(ch for ch in t if not lang.is_emoji(ch) and ch not in "\ufe0f\u200d").strip(" .!?,")
            stripped = t.rstrip(" .!?,")
            if not plain:
                pos["alone"] += 1
            elif lang.is_emoji(stripped[-1]) or stripped[-1] in "\ufe0f":
                pos["end"] += 1
            elif lang.is_emoji(t.lstrip()[0]):
                pos["start"] += 1
            else:
                pos["inline"] += 1
        prof.emoji_position = pos.most_common(1)[0][0]
        prof.emoji_end_rate = round(sum(1 for t in texts if (t.rstrip(" .!?,") or " ")[-1:] and
                                        (lang.is_emoji(t.rstrip(" .!?,")[-1]) or t.rstrip(" .!?,")[-1] == "\ufe0f")) / n, 3)
        prof.emoji_only_rate = round(pos["alone"] / n, 3)
        runs = sorted(_emoji_runs(t) for t in with_emoji)
        prof.emoji_run = max(1, runs[len(runs) // 2])
    # written laughs ("hahaha", "lol") first: laughing emojis are already covered by the emoji habits
    laughs = Counter(m.group(0).lower() for t in texts for m in _LAUGH.finditer(t) if not lang.emojis(m.group(0)))
    prof.laugh_style = laughs.most_common(1)[0][0] if laughs and laughs.most_common(1)[0][1] >= 2 else ""
    elongated = [m.group(0).lower() for t in texts for m in _ELONG.finditer(t) if not m.group(0).isdigit()
                 and not m.group(0).lower().startswith("www") and not _LAUGH.fullmatch(m.group(0))]
    prof.elongation_rate = round(sum(1 for t in texts if any(not _LAUGH.fullmatch(m.group(0)) for m in _ELONG.finditer(t))) / n, 3)
    prof.elongation_examples = [w for w, _ in Counter(elongated).most_common(4)]
    # bursts: several owner messages within 90 s form one reply turn
    turns, size = [], 0
    ordered = sorted(user, key=lambda ln: ln.timestamp)
    for i, ln in enumerate(ordered):
        size += 1
        nxt = ordered[i + 1] if i + 1 < len(ordered) else None
        if nxt is None or nxt.timestamp - ln.timestamp > 90:
            turns.append(size)
            size = 0
    prof.burst_rate = round(sum(1 for s in turns if s >= 2) / len(turns), 3) if turns else 0.0
    words = Counter(w for t in texts for w in _words(t))
    prof.address_terms = [w for w, c in sorted(((w, words[w]) for w in ADDRESS_TERMS), key=lambda x: -x[1]) if c >= 2][:4]
    short: dict[str, str] = {}
    joined = " ".join(t.lower() for t in texts)
    for full, variants in SHORTHAND.items():
        full_n = len(re.findall(rf"\b{re.escape(full)}\b", joined))
        best = max(variants, key=lambda v: len(re.findall(rf"\b{re.escape(v)}\b", joined)))
        best_n = len(re.findall(rf"\b{re.escape(best)}\b", joined))
        if best_n >= 2 and best_n > full_n:
            short[full] = best
    prof.shorthand = short
