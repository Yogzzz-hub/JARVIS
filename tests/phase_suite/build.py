"""Turn the phrasing templates into concrete commands (dev and blind splits), deterministic."""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.phase_suite.cases import PHASES, POOLS_BLIND, POOLS_DEV, TIERS, T  # noqa: E402

OUT = Path(__file__).resolve().parent
_PH = re.compile(r"\{(\w+)\}")
_UP = {"easy": "medium", "medium": "hard", "hard": "very_hard", "very_hard": "very_hard"}
NO_TRANSFORM = ("CONTROL:", "REJECT", "CLARIFY")
_KNOWN_WORDS = set("""open launch start close quit kill set volume mute take what show please can could would i hey jarvis um uh
don't do never how why should is are tell find where search list create make rename copy move delete remove organize clean
learn read how's turn lower it silence unmute capture grab lock restart reboot shut put system battery am switch snap
minimize maximize which get go draft write compose schedule add block check any did whats reply summarize who text
ask let send stop cancel yes no be change use repeat say reply talk good give remember forget where when list mark remind
generate from convert type press save undo install uninstall update connect pair mirror dial dig that okay hmm jarvis,
sound screen shot note bluetooth wifi wi the a my this""".split())


def split_of(t: T) -> str:
    return "blind" if int(hashlib.sha1(t.text.encode()).hexdigest(), 16) % 4 == 0 else "dev"


def _fill(text: str, values: dict[str, str]) -> str:
    def rep(m: re.Match) -> str:
        key = m.group(1)
        low = key.lower()
        v = values.get(low, m.group(0))
        return v.upper() if key.isupper() else v.title() if key[0].isupper() else v
    return _PH.sub(rep, text)


def _typo(text: str) -> str | None:
    """Swap two letters in the first command word ("open" -> "oepn"); entities stay intact."""
    words = text.split()
    for i, w in enumerate(words[:3]):
        if w.isalpha() and len(w) >= 4 and w not in ("jarvis", "please"):
            words[i] = w[0] + w[2] + w[1] + w[3:]
            return " ".join(words)
    return None


def variants(t: T, text: str) -> list[tuple[str, str]]:
    out = [(t.tier, text)]
    if any(t.expect.startswith(p) for p in NO_TRANSFORM) or "wake_greeting" in t.expect:  # "jarvis" alone: no wrappers
        return out
    base = text.rstrip(".!?")
    low = base[0].lower() + base[1:] if base else base
    if re.match(r"^(?:what|who|how|why|where|when|which|is|are|do|does|did|can|should|could|will|would|tell|to\s+whom|was|were|"
                r"has|have|so|hold\s+on|wait|am|i'?m|i\s+can'?t|any)\b", low):
        out.append((_UP[t.tier], f"jarvis, {low}"))  # a question gets an address, not "could you please what is ..."
    else:
        out.append((_UP[t.tier], f"could you please {low}"))
    out.append(("hard", f"um {low} jarvis"))
    typo = _typo(low)
    first = low.split()[0] if low.split() else ""
    already_misspelt = first.isalpha() and first not in _KNOWN_WORDS  # "opne chrome": no second typo on top
    if typo and t.expect not in ("CHAT",) and not already_misspelt:
        out.append(("very_hard", typo))
    return out


def build() -> dict[str, list[dict]]:
    cases: dict[str, list[dict]] = {"dev": [], "blind": []}
    for phase, templates in PHASES.items():
        for t in templates:
            split = split_of(t)
            pools = POOLS_BLIND if split == "blind" else POOLS_DEV
            rng = random.Random(f"{phase}|{t.text}")
            keys = sorted(set(k.lower() for k in _PH.findall(t.text)))
            n_inst = 3 if keys else 1
            seen: set[str] = set()
            for _ in range(n_inst):
                vals = {k: rng.choice(pools[k if k != "app2" else "app"]) for k in keys}
                if "app2" in vals and vals["app2"] == vals.get("app"):
                    vals["app2"] = next(a for a in pools["app"] if a != vals["app"])
                text = _fill(t.text, vals)
                slots = {k: _fill(str(v), vals) for k, v in t.slots.items()}
                for tier, variant in variants(t, text):
                    if variant.lower() in seen:
                        continue
                    seen.add(variant.lower())
                    # slot values are only checked on untouched phrasings (a typo'd variant may keep the typo)
                    cases[split].append({"id": f"{phase}-{hashlib.sha1(variant.encode()).hexdigest()[:8]}", "phase": phase,
                                         "tier": tier, "text": variant, "expect": t.expect,
                                         "slots": slots if variant == text else {}, "template": t.text})
    return cases


if __name__ == "__main__":
    cases = build()
    for split, rows in cases.items():
        path = OUT / f"{split}.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        from collections import Counter
        print(split, len(rows), dict(Counter(r["phase"] for r in rows)))
