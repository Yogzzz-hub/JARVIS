"""Expand the phase-500 templates into concrete commands (deterministic), split dev / holdout by template hash."""
from __future__ import annotations

import hashlib
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.phase500.cases import PHASES, POOLS, T  # noqa: E402

_PH = re.compile(r"\{(\w+)\}")
_UP = {"easy": "medium", "medium": "hard", "hard": "very_hard", "very_hard": "very_hard"}
NO_TRANSFORM = ("CONTROL:", "REJECT", "CLARIFY")
_QUESTION = re.compile(r"^(?:what|who|how|why|where|when|which|is|are|do|does|did|can|should|could|will|would|was|were|"
                       r"has|have|am|any)\b")
FILLS = 6


def split_of(t: T) -> str:
    return "holdout" if int(hashlib.sha1(t.text.encode()).hexdigest(), 16) % 4 == 0 else "dev"


def _fill(text: str, values: dict[str, str]) -> str:
    def rep(m: re.Match) -> str:
        key = m.group(1)
        v = values.get(key.lower(), m.group(0))
        return v.upper() if key.isupper() else v.title() if key[0].isupper() else v
    return _PH.sub(rep, text)


def _typo(text: str, which: int) -> str | None:
    """Swap two inner letters of the which-th long word (entities included - real speech-to-text errs anywhere)."""
    words = text.split()
    longs = [i for i, w in enumerate(words) if w.isalpha() and len(w) >= 5 and w not in ("jarvis", "please")]
    if len(longs) <= which:
        return None
    i = longs[which]
    w = words[i]
    words[i] = w[0] + w[2] + w[1] + w[3:]
    return " ".join(words)


def variants(t: T, text: str) -> list[tuple[str, str, str]]:
    """(tier, form, text)."""
    out = [(t.tier, "plain", text)]
    if any(t.expect.startswith(p) for p in NO_TRANSFORM) or "wake_greeting" in t.expect:
        return out + [(t.tier, "wake", f"jarvis {text}")] if not text.startswith(("hey jarvis", "jarvis")) else out
    base = text.rstrip(".!?")
    low = base[0].lower() + base[1:] if base else base
    up = _UP[t.tier]
    if _QUESTION.match(low) or t.expect.startswith("CHAT"):
        forms = [("wake", f"jarvis, {low}"), ("hey", f"hey jarvis {low}"), ("filler", f"um, {low}"),
                 ("okay", f"okay jarvis, {low}"), ("quick", f"quick question, {low}")]
    else:
        forms = [("polite", f"could you please {low}"), ("please", f"please {low}"), ("tail", f"{low} please"),
                 ("filler", f"um {low} jarvis"), ("wake", f"hey jarvis, {low}"), ("forme", f"{low} for me"),
                 ("can", f"can you {low}"), ("okay", f"okay {low}"), ("now", f"{low} now")]
    out += [(up, k, v) for k, v in forms]
    if t.expect not in ("CHAT",):
        for i, k in ((0, "typo"), (1, "typo2")):
            ty = _typo(low, i)
            if ty and ty != low:
                out.append(("very_hard", k, ty))
    return out


def build() -> dict[str, list[dict]]:
    cases: dict[str, list[dict]] = {"dev": [], "holdout": []}
    for phase, templates in PHASES.items():
        for t in templates:
            split = split_of(t)
            rng = random.Random(f"{phase}|{t.text}")
            keys = sorted(set(k.lower() for k in _PH.findall(t.text)))
            n_inst = FILLS if keys else 1
            seen: set[str] = set()
            for _ in range(n_inst):
                vals = {k: rng.choice(POOLS[k]) for k in keys}
                text = _fill(t.text, vals)
                slots = {k: _fill(str(v), vals) for k, v in t.slots.items()}
                for tier, form, variant in variants(t, text):
                    if variant.lower() in seen:
                        continue
                    seen.add(variant.lower())
                    cases[split].append({"id": f"{phase}-{hashlib.sha1(variant.encode()).hexdigest()[:8]}", "phase": phase,
                                         "tier": tier, "form": form, "text": variant, "expect": t.expect,
                                         "slots": slots if form in ("plain", "wake", "polite", "please") else {},
                                         "template": t.text})
    return cases


if __name__ == "__main__":
    from collections import Counter
    c = build()
    for split, rows in c.items():
        print(split, len(rows))
    tot = Counter(r["phase"] for rows in c.values() for r in rows)
    for k, v in sorted(tot.items()):
        print(f"  {k:18} {v}")
