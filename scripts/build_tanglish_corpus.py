"""Deterministic, local Tanglish semantic corpus builder.

Usage: python scripts/build_tanglish_corpus.py --total 105000
Generated labels come from declared semantic programs, never the model being
evaluated. Split isolation is by construction family, not row-level shuffling.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path


VERBS = {
    "SEND": ["anupu", "anuppu", "anupidu", "send pannu", "share pannu", "forward pannu"],
    "CONVERT_FORMAT": ["maathu", "mathu", "convert pannu"],
    "SWITCH_RESOURCE": ["maathu", "mathu", "switch pannu"],
    "SET_VALUE": ["maathu", "podu", "vai", "set pannu"],
    "REWRITE_STYLE": ["maathu", "rewrite pannu"],
    "PROVIDE": ["kudu", "kodu", "thaa"],
    "SUMMARIZE": ["kudu", "summarize pannu", "short pannu"],
    "DRAFT_REPLY": ["kudu", "draft pannu", "reply ready pannu"],
    "LIST": ["kaatu", "kaattu", "show pannu"],
    "DISPLAY": ["kaatu", "display pannu"],
    "READ": ["kaatu", "paaru", "read pannu"],
    "CAPTURE": ["eduthu", "edu", "capture pannu"],
    "SELECT": ["eduthu", "edu", "select pannu"],
    "RETRIEVE": ["eduthu", "retrieve pannu", "thedu"],
    "PLAY": ["podu", "play pannu"],
    "ENTER": ["podu", "type pannu", "enter pannu"],
    "CREATE": ["podu", "create pannu"],
    "INSERT": ["podu", "insert pannu"],
    "INSTALL": ["podu", "install pannu"],
    "CHECK_STATUS": ["paaru", "check pannu"],
}
OBJECTS = {
    "SEND": [("PDF", "pdf"), ("DOCUMENT", "document"), ("IMAGE", "photo"), ("FILE", "file"), ("MESSAGE", "message")],
    "CONVERT_FORMAT": [("PDF", "pdf word ah"), ("IMAGE", "image pdf ah"), ("DOCUMENT", "document pdf ah")],
    "SWITCH_RESOURCE": [("TAB", "tab"), ("APP", "Chrome Edge ku"), ("MODE", "dark mode ku")],
    "SET_VALUE": [("VOLUME", "volume 50 ku"), ("BRIGHTNESS", "brightness 30 ku"), ("LANGUAGE", "language English ku")],
    "REWRITE_STYLE": [("TEXT", "sentence professional ah"), ("MESSAGE", "message short ah")],
    "PROVIDE": [("ANSWER", "answer"), ("NUMBER", "number"), ("FILE", "file")],
    "SUMMARIZE": [("SUMMARY", "summary"), ("CHAT", "chat summary")],
    "DRAFT_REPLY": [("REPLY", "reply"), ("REPLY", "message reply")],
    "LIST": [("FILE", "files"), ("FOLDER", "folders")],
    "DISPLAY": [("IMAGE", "photo"), ("SCREEN", "screen")],
    "READ": [("MESSAGE", "latest msg"), ("DOCUMENT", "document")],
    "CAPTURE": [("SCREENSHOT", "screenshot"), ("IMAGE", "photo")],
    "SELECT": [("FILE", "second file"), ("PDF", "third pdf")],
    "RETRIEVE": [("DATABASE", "database la data"), ("FILE", "folder la file")],
    "PLAY": [("AUDIO", "song"), ("AUDIO", "music")],
    "ENTER": [("PASSWORD", "password"), ("TEXT", "login code")],
    "CREATE": [("ALARM", "alarm 7 ku"), ("CALENDAR", "calendar la meeting")],
    "INSERT": [("EMOJI", "message la emoji"), ("TEXT", "document la line")],
    "INSTALL": [("SOFTWARE", "software"), ("APP", "app")],
    "CHECK_STATUS": [("STATUS", "backend status"), ("STATUS", "service status")],
}
NAMES = ["Naveen", "Arun", "Yoga", "Kumar", "Priya", "Anu", "Meena", "Ravi", "Siva", "Karthik",
         "Mohan", "Divya", "Sara", "Akash", "Vimal", "Deepa", "Bala", "Asha", "Hari", "Renu"]
PROJECTS = ["CREO", "Atlas", "Orbit", "Nimbus", "Delta", "Phoenix", "Cedar", "Helix", "Mango", "Sigma"]
CHANNELS = ["whatsapp la", "mail la", "chat la"]
SELECTORS = ["latest", "second", "third", "last", "previous", "new", "old", "yesterday oda"]
PREFIXES = ["", "bro", "jarvis", "please", "konjam", "ippo", "seekiram", "time irundha", "intha task ku"]
SUFFIXES = ["", "da", "please", "pannunga", "thanks", "ippo", "mattum", "seri"]
PHONETIC_NOISE = {"anupu": "annupu", "anuppu": "anuppuuu", "maathu": "mathu", "mathu": "matu",
                  "kaatu": "katu", "kaattu": "kaatu", "pannu": "panu", "kudu": "kodu",
                  "eduthu": "edthu", "edu": "eduu", "podu": "potu", "paaru": "paru"}
ASR_NOISE = {"anupu": "a noop", "anuppu": "a noop", "maathu": "math who", "kaatu": "car two",
             "kudu": "could do", "eduthu": "edit to", "podu": "pour do", "pannu": "pan new"}
CONTEXTS = [
    ("Find {name} oda {obj}", "atha {name} kitta {verb}"),
    ("Show {name} oda docs", "second one {verb}"),
    ("Open {project} project", "anga irukkura {obj} {verb}"),
    ("Check the current thread", "same one {verb}"),
    ("Volume 80", "konjam kammi {verb}"),
    ("{name} message paathu", "athuku {verb}"),
]


def normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def skeleton(text: str) -> str:
    s = normalized(text)
    for word in sorted(NAMES + PROJECTS, key=len, reverse=True):
        s = re.sub(r"\b" + re.escape(word.casefold()) + r"\b", "NAME" if word in NAMES else "PROJECT", s)
    for action, verbs in VERBS.items():
        for verb in sorted(verbs, key=len, reverse=True):
            s = re.sub(r"\b" + re.escape(verb.casefold()) + r"\b", "VERB_" + action, s)
    return re.sub(r"\b\d+\b", "NUMBER", s)


def make_example(rng: random.Random, family: int, index: int) -> dict:
    action = list(VERBS)[(family * 7 + index) % len(VERBS)]
    verb = rng.choice(VERBS[action])
    target_type, obj = rng.choice(OBJECTS[action])
    name, project = rng.choice(NAMES), rng.choice(PROJECTS)
    channel = rng.choice(CHANNELS) if action == "SEND" else ""
    selector = rng.choice(SELECTORS)
    # Family isolates clause order, context construction and speech-act wrapping.
    pattern = (family % 8 if family < 64 else 8 + family % 2 if family < 72
               else 10 + family % 2 if family < 76 else 12 + family % 4 if family < 80
               else 16 + family % 4 if family < 84 else 20 + family % 4 if family < 88
               else 24 + family % 4 if family < 92 else 28 + family % 4 if family < 96 else 32 + family % 4)
    core = [f"{obj} {verb}", f"{selector} {obj} {verb}", f"{name} oda {obj} {verb}",
            f"{obj} ah {verb}", f"{project} la {obj} {verb}", f"{obj} {name} kitta {verb}",
            f"{name} kitta {selector} {obj} {verb}", f"{selector} {obj} ah {name} kitta {verb}",
            f"{obj} {channel} {verb}".strip(), f"{project} oda {selector} {obj} {verb}",
            f"{name} oda {project} {obj} {verb}", f"{channel} {obj} {name} kitta {verb}".strip(),
            f"{project} ku related ana {obj} irundha {verb}",
            f"{name} sonna {selector} {obj} dhan {verb}",
            f"{obj} pathi {name} ketta, {verb}",
            f"{project} velai ku {name} oda {obj} mattum {verb}",
            f"if {project} la {selector} {obj} irundha, adha {verb}",
            f"intha {name} oda {obj} dhan venum; {verb}",
            f"naan sonna {project} item, {selector} {obj}, adha {verb}",
            f"{name} request pannina {obj} irukku; adhaye {verb}",
            f"{project} discussion la {name} mention pannina {selector} {obj}; atha {verb}",
            f"oru {obj} irukku {project} kulla, {name} kitta ketu {verb}",
            f"{name} oda list la {selector} item is {obj}, adha {verb}",
            f"{project} mudiyum munadi {obj} mattum {verb}",
            f"{name} mentioned {obj} in {project}; ippo adha {verb}",
            f"{selector} ah irukkura {obj} than, {name} sonna mathiri {verb}",
            f"{project} list la {obj} kadaisila irukku; adha {verb}",
            f"{obj} venum nu {name} sonnanga; {verb}",
            f"{project} la last review ku {obj} thevai; {verb}",
            f"{name} oda {project} list pathi pesinom; andha {obj} {verb}",
            f"{selector} choice ah irukkura {obj} mattum {verb}",
            f"{project} work start aagurathukku munadi {obj} {verb}",
            f"{project} review mudinja apram, {name} oda {obj} paathu {verb}",
            f"next step la {selector} {obj} irukku {project} ku; {verb}",
            f"{name} yesterday sonna {obj} ready ah irukku; adhai {verb}",
            f"work note {project} la {obj} mark panniyachu; ippo {verb}"][pattern]
    if action != "SEND":
        # A recipient phrase changes GIVE/PROVIDE into a transfer and makes
        # unrelated actions such as setting volume semantically inconsistent.
        core = core.replace(f"{name} kitta ketu", f"{name} sonna mathiri")
        core = core.replace(f"{name} kitta", f"{name} oda")
    if action == "SEND" and pattern not in (5, 6, 7, 8, 11, 13):
        core = f"{core} {name} kitta {channel}"
    if index % 5 == 0:
        core = f"{rng.choice(PREFIXES[1:])} {core}"
    if index % 7 == 0:
        core = f"{core} {rng.choice(SUFFIXES[1:])}"
    if index % 11 == 0:
        core = f"{core}, screenshot venam" if target_type != "SCREENSHOT" else f"{core}, old one venam"
    turns = []
    context = {}
    if index % 4 == 0:
        turns = ([f"First we discussed {project}", f"Then {name} selected {selector} {obj}"] if family >= 96
                 else [f"{name} selected {selector} {obj} for {project}"])
        context = {"selected_resource": {"target_type": target_type, "selector": selector},
                   "semantic_hints": ["word"] if action == "CONVERT_FORMAT" else []}
        refword = "idhu" if family >= 96 else "atha"
        core = f"{refword} {name} kitta {channel} {verb}" if action == "SEND" else f"{refword} {verb}"
        if action == "SET_VALUE":
            number = re.search(r"\d+", obj)
            core = f"atha {number.group() if number else 'English'} ku {verb}"
        elif action == "CONVERT_FORMAT":
            core = f"atha word ah {verb}"
        elif action == "SELECT":
            core = f"{selector} one {verb}"
        elif action == "INSERT":
            core = f"message la atha {verb}"
        elif action == "ENTER":
            core = f"login field la atha {verb}"
    noise = "none"
    if index % 29 == 0 and index % 10 >= 5:
        first = verb.split()[0]
        if first in ASR_NOISE:
            core = core.replace(first, ASR_NOISE[first], 1)
            noise = "uncertain_asr"
    elif index % 13 == 0:
        first = verb.split()[0]
        if first in PHONETIC_NOISE:
            core = core.replace(first, PHONETIC_NOISE[first], 1)
            noise = "phonetic_typo"
    speech = ["COMMAND", "QUESTION", "PROHIBITION", "STATEMENT", "HYPOTHETICAL"][index % 10 if index % 10 < 5 else 0]
    if noise == "uncertain_asr":
        speech = "UNKNOWN"
    if speech == "QUESTION":
        core = f"{core} mudiyuma?"
    elif speech == "PROHIBITION":
        core = f"{core} panna venam"
    elif speech == "STATEMENT":
        core = f"naan {core} panna poren"
    elif speech == "HYPOTHETICAL":
        core = f"{core} panna enna aagum?"
    return {"text": core, "previous_turns": turns, "context": context, "frame": {"speech_act": speech,
        "action": action if speech == "COMMAND" else None, "target_type": target_type,
        "recipient": name if action == "SEND" and "kitta" in core else None,
        "channel": "email" if action == "SEND" and "mail la" in core else "whatsapp" if action == "SEND" and "whatsapp la" in core else None,
        "selector": selector if selector in core else None}, "family": family,
        "source": "compositional_grammar", "noise": noise}


def build(root: Path, total: int, seed: int = 842) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    targets = {"train": int(total * .8), "dev": int(total * .1), "test": int(total * .05)}
    targets["holdout"] = total - sum(targets.values())
    # Whole grammar families, including context and wrapper style, are held out.
    family_sets = {"train": range(0, 64), "dev": range(64, 72), "test": range(72, 76), "holdout": range(76, 80)}
    seen: set[str] = set()
    counts = Counter()
    family_counts = Counter()
    for split, target in targets.items():
        path = root / f"{split}.jsonl.gz"
        with gzip.open(path, "wt", encoding="utf-8") as out:
            attempts = 0
            while counts[split] < target:
                attempts += 1
                if attempts > target * 100:
                    raise RuntimeError(f"Corpus diversity exhausted for {split}: {counts[split]}/{target}")
                family = rng.choice(tuple(family_sets[split]))
                row = make_example(rng, family, attempts)
                fingerprint = hashlib.sha256(normalized(" ".join(row["previous_turns"] + [row["text"]])).encode()).hexdigest()
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                row["id"] = fingerprint
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                counts[split] += 1
                family_counts[f"{split}:{family}"] += 1
    report = {"total": sum(counts.values()), "splits": dict(counts), "unique_normalized": len(seen),
              "family_counts": dict(family_counts), "family_isolation": True,
              "sources": ["compositional_grammar"],
              "limitations": "Synthetic examples only; no user chats, human paraphrases or independent semantic annotation."}
    (root / "leakage_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def build_locked(root: Path, count: int = 5000, seed: int = 1974, version: int = 3) -> dict:
    """Create a fresh split with grammar families absent from all earlier splits."""
    known = set()
    prior_structures = set()
    for name in ("train", "dev", "test", "holdout", "locked_holdout_v2", "locked_holdout_v3", "locked_holdout_v4", "locked_holdout_v5"):
        corpus = root / f"{name}.jsonl.gz"
        if not corpus.exists():
            continue
        with gzip.open(corpus, "rt", encoding="utf-8") as source:
            for line in source:
                row = json.loads(line)
                known.add(row["id"])
                prior_structures.add(skeleton(" ".join(row.get("previous_turns", []) + [row["text"]])))
    rng = random.Random(seed)
    start_family = 96 if version == 6 else 92 if version == 5 else 88 if version == 4 else 84 if version == 3 else 80
    path = root / f"locked_holdout_v{version}.jsonl.gz"
    counts = Counter()
    with gzip.open(path, "wt", encoding="utf-8") as out:
        attempts = 0
        while counts["total"] < count:
            attempts += 1
            if attempts > count * 100:
                raise RuntimeError("Locked holdout diversity exhausted")
            row = make_example(rng, rng.choice(range(start_family, start_family + 4)), attempts)
            full_text = " ".join(row["previous_turns"] + [row["text"]])
            fingerprint = hashlib.sha256(normalized(full_text).encode()).hexdigest()
            if fingerprint in known or skeleton(full_text) in prior_structures:
                continue
            known.add(fingerprint)
            row["id"] = fingerprint
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            counts["total"] += 1
            counts["multi_turn"] += bool(row["previous_turns"])
            counts["no_action"] += row["frame"]["action"] is None
    report = {"path": str(path), "count": count, "multi_turn": counts["multi_turn"],
              "no_action": counts["no_action"], "normalized_overlap": 0,
              "grammar_families": list(range(start_family, start_family + 4)),
              "previous_grammar_families": list(range(start_family))}
    (root / f"locked_holdout_v{version}_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--total", type=int, default=105000)
    parser.add_argument("--output", type=Path, default=Path("jarvis/tests/fixtures/tanglish_corpus"))
    parser.add_argument("--locked-only", action="store_true")
    parser.add_argument("--locked-version", type=int, default=6, choices=(2, 3, 4, 5, 6))
    args = parser.parse_args()
    print(json.dumps(build_locked(args.output, version=args.locked_version) if args.locked_only else build(args.output, args.total), indent=2))
