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
from jarvis.integrations.whatsapp.personal_reply.models import Authorship, ChatLine, ContactStyleProfile, Direction
from jarvis.integrations.whatsapp.personal_reply.legacy_provenance import evidence_weight

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
    user = [ln for ln in lines if ln.direction == Direction.USER and ln.text.strip()
            and evidence_weight(ln.provenance, ln.provenance_confidence) > 0]
    prof = ContactStyleProfile(contact_id=contact_id, display_name=display_name, preferences=dict(preferences or {}))
    prof.messages_analyzed = len(user)
    prof.verified_messages = sum(ln.provenance in (
        Authorship.USER_TYPED, Authorship.VERIFIED_MANUAL_OWNER_SEND, Authorship.USER_EDITED_AI_DRAFT,
        Authorship.USER_APPROVED_AI_DRAFT, Authorship.VERIFIED_LEGACY_OWNER) for ln in user)
    prof.legacy_messages = sum(ln.provenance == Authorship.LEGACY_OWNER_LIKELY for ln in user)
    weights = [evidence_weight(ln.provenance, ln.provenance_confidence) for ln in user]
    verified_raw = sum(w for ln, w in zip(user, weights) if ln.provenance != Authorship.LEGACY_OWNER_LIKELY)
    legacy_raw = sum(w for ln, w in zip(user, weights) if ln.provenance == Authorship.LEGACY_OWNER_LIKELY)
    if verified_raw > 0 and legacy_raw > 0:
        legacy_scale = min(1.0, .5 * verified_raw / legacy_raw)
        weights = [w * legacy_scale if ln.provenance == Authorship.LEGACY_OWNER_LIKELY else w
                   for ln, w in zip(user, weights)]
    total_weight = sum(weights)
    prof.effective_evidence = round(total_weight, 3)
    prof.updated_at = time.time()
    if not user:
        return prof
    texts = [ln.text.strip() for ln in user]

    # language mix (message level)
    labels = [lang.detect(t) for t in texts]
    known = [(m, w) for m, w in zip(labels, weights) if m.label != lang.UNKNOWN]
    known_weight = sum(w for _, w in known)
    tang = sum(w for m, w in known if lang.is_tanglish_mode(m.label))
    prof.tanglish_ratio = round(tang / known_weight, 3) if known_weight else 0.0
    prof.english_ratio = round(1 - prof.tanglish_ratio, 3) if known_weight else 1.0
    pure_tanglish = sum(w for m, w in known if m.label == lang.TANGLISH)
    if prof.tanglish_ratio < 0.2:
        prof.preferred_language = "ENGLISH"
    elif known_weight and pure_tanglish / known_weight >= 0.5:
        prof.preferred_language = "TANGLISH"
    else:
        prof.preferred_language = "MIXED"

    # length
    lengths = [len(_words(t)) or 1 for t in texts]
    prof.avg_message_length = round(sum(v*w for v, w in zip(lengths, weights)) / total_weight, 2)
    ordered_lengths = sorted(zip(lengths, weights))
    cumulative = 0.0
    prof.median_message_length = float(ordered_lengths[-1][0])
    for value, weight in ordered_lengths:
        cumulative += weight
        if cumulative >= total_weight / 2:
            prof.median_message_length = float(value)
            break
    med = prof.median_message_length
    prof.typical_reply_length = ("1-3 words" if med <= 3 else "1 short sentence" if med <= 8
                                 else "1-2 sentences" if med <= 20 else "a few sentences")

    # emoji
    all_emojis = Counter()
    for text, weight in zip(texts, weights):
        all_emojis.update({emoji: weight * count for emoji, count in Counter(lang.emojis(text)).items()})
    prof.emoji_frequency = round(sum(all_emojis.values()) / total_weight, 3)
    prof.common_emojis = [e for e, _ in all_emojis.most_common(6)]
    combinations = Counter()
    for text, weight in zip(texts, weights):
        run = ""
        for char in text:
            if lang.is_emoji(char) or (run and char in "\ufe0f\u200d"):
                run += char
            else:
                if len(lang.emojis(run)) >= 2:
                    combinations[run] += weight
                run = ""
        if len(lang.emojis(run)) >= 2:
            combinations[run] += weight
    prof.emoji_combinations = [value for value, _ in combinations.most_common(5)]
    modalities = Counter()
    for text, weight in zip(texts, weights):
        emoji = bool(lang.emojis(text))
        letters = "".join(ch for ch in text if not lang.is_emoji(ch) and ch not in "\ufe0f\u200d").strip(" \t.!?,")
        modalities["EMOJI_ONLY" if emoji and not letters else "TEXT_EMOJI" if emoji else "TEXT"] += weight
    prof.modality_counts = dict(modalities)

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
    habits(prof, user, texts, weights)

    # confidence: enough samples AND a consistent style
    # Legacy can bootstrap a profile but cannot swamp later verified behavior.
    legacy_effective = sum(w for ln, w in zip(user, weights) if ln.provenance == Authorship.LEGACY_OWNER_LIKELY)
    verified_effective = total_weight - legacy_effective
    n_factor = min(1.0, (verified_effective + min(legacy_effective, 12.0)) / 40.0)
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


def habits(prof: ContactStyleProfile, user: list[ChatLine], texts: list[str], weights: list[float] | None = None) -> None:
    n = len(texts)
    weighted = [(t, w) for t, w in zip(texts, weights or [evidence_weight(ln.provenance, ln.provenance_confidence)
                                                         for ln in user])]
    total_weight = sum(w for _, w in weighted)
    all_emojis = Counter()
    for text, weight in weighted:
        all_emojis.update({e: weight * count for e, count in Counter(lang.emojis(text)).items()})
    prof.emoji_vocab = [e for e, _ in all_emojis.most_common(20)]
    with_emoji = [(t, w) for t, w in weighted if lang.emojis(t)]
    if with_emoji:
        pos = Counter()
        for t, weight in with_emoji:
            plain = "".join(ch for ch in t if not lang.is_emoji(ch) and ch not in "\ufe0f\u200d").strip(" .!?,")
            stripped = t.rstrip(" .!?,")
            if not plain:
                pos["alone"] += weight
            elif lang.is_emoji(stripped[-1]) or stripped[-1] in "\ufe0f":
                pos["end"] += weight
            elif lang.is_emoji(t.lstrip()[0]):
                pos["start"] += weight
            else:
                pos["inline"] += weight
        prof.emoji_position = pos.most_common(1)[0][0]
        prof.emoji_end_rate = round(sum(w for t, w in weighted if t.rstrip(" .!?,") and
                                        (lang.is_emoji(t.rstrip(" .!?,")[-1]) or t.rstrip(" .!?,")[-1] == "\ufe0f")) / total_weight, 3)
        prof.emoji_only_rate = round(pos["alone"] / total_weight, 3)
        runs = sorted(_emoji_runs(t) for t, _ in with_emoji)
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
