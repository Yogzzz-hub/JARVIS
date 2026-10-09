"""Novelty checker: every BLIND-12 utterance must differ from all existing test phrases after normalisation."""
import json, re, collections
BASE = '/tmp/claude-0/blind12_gen/'
FILLERS = {"jarvis", "hey", "please", "pls", "now", "um", "ok", "okay", "quickly", "the", "a", "an", "my"}


def norm(s):
    s = s.lower().replace("’", "'")
    s = re.sub(r"[^\w\s]", " ", s)          # drop punctuation
    s = re.sub(r"\bfor me\b", " ", s)        # two-word filler
    words = [w for w in s.split() if w not in FILLERS]
    return " ".join(words)


existing = json.load(open(BASE + 'existing_phrases.json'))
ex_norm = collections.defaultdict(list)
for p in existing:
    n = norm(p)
    if n:
        ex_norm[n].append(p)
cases = [json.loads(l) for l in open(BASE + 'cases.jsonl')]
exact = [c for c in cases if c['utterance'].strip().lower() in {p.strip().lower() for p in existing}]
near = [c for c in cases if norm(c['utterance']) in ex_norm]
ctx_hits = sorted({t for c in cases for t in c.get('context', []) if norm(t) in ex_norm})
lines = [
    "BLIND-12 novelty report",
    f"existing phrases collected: {len(existing)} (distinct normalised: {len(ex_norm)})",
    "sources: /home/user/JARVIS/tests/**, /home/user/JARVIS/jarvis/tests/**, README.md, tests/blind10/cases.py",
    "normalisation: lower-case, strip punctuation, drop wake words (jarvis, hey), fillers (please, pls, now, um, ok, okay, quickly, for me), articles (the, a, an, my)",
    f"utterances checked: {len(cases)}",
    f"exact duplicates: {len(exact)}",
    f"near-copies (normalised equal): {len(near)}",
]
for c in near:
    lines.append(f"  COLLISION {c['id']}: {c['utterance']!r} ~ {ex_norm[norm(c['utterance'])][:2]}")
lines.append(f"context turns that match an existing phrase (informational; they are setup turns, not test utterances): {len(ctx_hits)}")
for t in ctx_hits:
    lines.append(f"  ctx: {t!r}")
lines.append("RESULT: " + ("PASS" if not exact and not near else "FAIL"))
open(BASE + 'novelty_report.txt', 'w').write("\n".join(lines) + "\n")
print("\n".join(lines))
