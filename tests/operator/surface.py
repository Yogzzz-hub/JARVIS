"""Surface-form generator: one meaning, many wordings.

Dev forms (used while building the router): formal, casual, short, polite, filler/ASR noise, wake word, typo.
Holdout forms (never used for tuning, reported separately): long run-up, trailing context, mixed politeness,
spoken-number substitutions, a different typo model, "for me" tails. Negation and correction forms change the
expected outcome: a negated request must not run; "X, no wait, Y" must run Y.
"""
from __future__ import annotations

import random
import re

_SPOKEN = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "10": "ten", "30": "thirty", "45": "forty five"}


def _typo(s: str, rng: random.Random, mode: int = 0) -> str:
    words = s.split()
    cand = [i for i, w in enumerate(words) if len(w) >= 5 and w.isalpha()]
    if not cand:
        return s
    i = rng.choice(cand)
    w = words[i]
    j = rng.randrange(1, len(w) - 2)
    if mode == 0:                                       # transposition
        w = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    else:                                               # dropped letter
        w = w[:j] + w[j + 1:]
    words[i] = w
    return " ".join(words)


def dev_forms(seed: str, rng: random.Random) -> list[tuple[str, str]]:
    s = seed.strip()
    if re.match(r"^(?:what|which|who|where|when|how|is|are|does|did|any)\b|^do\b(?!\s+not\b)", s):
        # a question keeps its shape: "can you what's on my clipboard" is not something a person says
        out = [("canonical", s), ("formal", f"{s[0].upper()}{s[1:]}?"), ("casual", f"hey {s}"),
               ("polite", f"tell me {s} please"), ("wake", f"jarvis {s}"),
               ("asr", re.sub(r"[^\w\s:.%x+-]", "", s.lower())), ("typo", _typo(s, rng, 0))]
        seen, uniq = set(), []
        for k, v in out:
            if v not in seen:
                seen.add(v)
                uniq.append((k, v))
        return uniq
    out = [("canonical", s), ("formal", f"Please {s}."), ("casual", f"can you {s}"), ("polite", f"could you {s} please"),
           ("wake", f"jarvis {s}"), ("asr", re.sub(r"[^\w\s:.%x+-]", "", s.lower())), ("short", re.sub(r"\b(the|a|an|my)\s+", "", s)),
           ("typo", _typo(s, rng, 0))]
    seen, uniq = set(), []
    for k, v in out:
        if v not in seen:
            seen.add(v)
            uniq.append((k, v))
    return uniq


def holdout_forms(seed: str, rng: random.Random) -> list[tuple[str, str]]:
    s = seed.strip()
    num = re.sub(r"(?<![:.\d])\b(" + "|".join(_SPOKEN) + r")\b(?![:.\d])", lambda m: _SPOKEN[m.group(1)], s)
    return [("long", f"hey jarvis, when you get a sec, {s}"), ("tail", f"{s} for me"),
            ("spoken_numbers", num), ("kindly", f"kindly {s}"), ("typo2", _typo(s, rng, 1)),
            ("hesitant", f"um, {s}")]


def negated(seed: str) -> str:
    s = seed.strip()
    return f"don't {s}"


def corrected(wrong: str, right: str) -> str:
    return f"{wrong}, no wait, {right}"
