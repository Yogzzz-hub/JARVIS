"""Build Stage 2.1 speech-act minimal pairs. Never reads the sealed holdout.

These are declared semantic programs, not public text relabeled as commands.
The adversarial files are development data; they are not an independent test.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

from scripts.build_tanglish_semantic_stage2 import ONTOLOGY, NAMES, ROOT

OUT = ROOT / "data/tanglish/generated/stage21"
ACTS = ("COMMAND", "QUESTION", "CAPABILITY_QUERY", "STATEMENT", "HYPOTHETICAL",
        "NEGATED_COMMAND", "CORRECTION", "CHAT", "META_CONTROL", "AMBIGUOUS")
NO_ACTION = {"QUESTION", "CAPABILITY_QUERY", "STATEMENT", "HYPOTHETICAL",
             "NEGATED_COMMAND", "CHAT", "AMBIGUOUS"}
ELIGIBLE = {"COMMAND", "CORRECTION", "META_CONTROL"}
HIGH_RISK = {"DELETE", "UNINSTALL", "SEND", "CALL", "SUBMIT", "UPLOAD", "INSTALL", "PAY"}
EXTRA_ACTIONS = {
    "PAY": ("finance", "invoice", "pay", "kaasu kudu", "payment pannu"),
    "CLICK": ("browser", "button", "click", "click pannu", "press pannu"),
    "RESTART": ("pc", "service", "restart", "restart pannu", "marubadi start pannu"),
    "RUN": ("pc", "script", "run", "run pannu", "execute pannu"),
    "STOP": ("pc", "service", "stop", "niruthu", "stop pannu"),
}
ACTION_MAP = {**ONTOLOGY, **EXTRA_ACTIONS}
OBJECTS = ("pdf", "file", "photo", "message", "folder", "app", "tab", "report", "audio", "document")
CHANNELS = ("whatsapp", "email", "browser", "local")
ORDINALS = ("first", "second", "third", "latest")


def fingerprint(text: str) -> str:
    return hashlib.sha256(" ".join(re.findall(r"\w+", text.casefold())).encode()).hexdigest()


def render(rng: random.Random, action: str, act: str, split: str, index: int, group: int) -> dict:
    domain, native_object, english, tanglish, alternative = ACTION_MAP[action]
    lexical = random.Random(f"{split}:{action}:{group}")
    verb = lexical.choice((english, tanglish, alternative))
    obj = lexical.choice((native_object,) + OBJECTS)
    person = lexical.choice(NAMES)
    channel = lexical.choice(CHANNELS)
    ordinal = lexical.choice(ORDINALS)
    prefix = lexical.choice(("", "bro ", "please ", "konjam ", "JARVIS "))
    # A lexical pair shares action, verb and object. Grammar determines speech act.
    base = f"{ordinal} {obj} {verb}"
    recipient = person if action in {"SEND", "SHARE", "FORWARD", "REPLY", "CALL"} else None
    suffix = f" {person} ku" if recipient else ""
    if split == "train":
        forms = {
            "COMMAND": (f"{prefix}{base}{suffix}", f"{prefix}{verb} {ordinal} {obj}{suffix}"),
            "QUESTION": (f"{base}{suffix} pannitiya?", f"did you {verb} {ordinal} {obj}{suffix}?"),
            "CAPABILITY_QUERY": (f"{base}{suffix} panna mudiyuma?", f"can you {verb} {ordinal} {obj}{suffix}?"),
            "STATEMENT": (f"naan {base}{suffix} panniten", f"{person} already {base}{suffix} pannitan"),
            "HYPOTHETICAL": (f"{base}{suffix} panna enna aagum?", f"what if {base}{suffix} pannina?"),
            "NEGATED_COMMAND": (f"{base}{suffix} panna venam", f"{base}{suffix} pannadha"),
            "CORRECTION": (f"{base} Arun ku... illa {person} ku{suffix}", f"{base} {person} ku dhaan, Arun ku venam"),
            "CHAT": (f"{ordinal} {obj} {verb} na enna meaning?", f"{person} sonna {obj} {verb} pathi sollu"),
            "META_CONTROL": (f"pending {base} task cancel pannu", f"current {base} plan pause pannu"),
            "AMBIGUOUS": (f"{base}{suffix} maybe", f"{base}{suffix} nu sonna?"),
        }
    else:
        forms = {
            "COMMAND": (f"{obj} la {ordinal} one ah {person} kitta {verb}, {channel} la", f"{prefix}{person} ku {ordinal} {obj} {verb} da"),
            "QUESTION": (f"{ordinal} {obj} {verb} aacha {person}?", f"{person} kitta {obj} {verb} already pannitiya?"),
            "CAPABILITY_QUERY": (f"{person} kitta {obj} {verb} panna capability irukka?", f"{obj} {verb} panna mudiyuma JARVIS?"),
            "STATEMENT": (f"nethu {person} {ordinal} {obj} {verb} pannanga", f"I was going to {verb} {obj} myself"),
            "HYPOTHETICAL": (f"suppose {person} {obj} {verb} panna, result enna?", f"{obj} {verb} pannina enna nadakkum?"),
            "NEGATED_COMMAND": (f"{person} ku {obj} {verb} panna venda", f"don't {verb} that {ordinal} {obj}"),
            "CORRECTION": (f"{obj} Arun ku illa, {person} ku {verb}", f"{obj} {verb}, sorry {ordinal} one {person} ku"),
            "CHAT": (f"{obj} {verb} meaning explain pannu", f"'{obj} {verb}' nu phrase pathi pesalam"),
            "META_CONTROL": (f"{obj} {verb} pending request ah stop pannu", f"existing {obj} {verb} workflow cancel pannu"),
            "AMBIGUOUS": (f"{person} {obj} {verb} perhaps?", f"{ordinal} {obj} {verb} or wait?"),
        }
    text = rng.choice(forms[act])
    # Context changes the referent, not the action label.
    context = []
    if index % 5 == 0:
        context = [f"{person} oda {obj} list kaatu", f"{ordinal} {obj} select panninen"]
        text = text.replace(f"{ordinal} {obj}", "atha", 1)
    # Explicitly labelled slots; absent means unsupported, not guessed.
    slots = {
        "target": obj if obj in text else ("context.selected_resource" if context else None),
        "recipient": person if re.search(rf"\b{re.escape(person)}\s+(?:ku|kitta)\b", text, re.I) else None,
        "ordinal": ordinal if ordinal in text else (ordinal if context else None),
        "file_type": "pdf" if obj == "pdf" else None,
        "application": obj if obj == "app" else None,
        "source": None, "destination": channel if channel in text else None,
    }
    corrections = []
    if act == "CORRECTION":
        corrections = [{"slot": "recipient", "superseded": "Arun", "active": person}]
        slots["recipient"] = person
    return {"text": text, "previous_turns": context, "speech_act": act,
            "action_concept": action, "should_act": act in ELIGIBLE,
            "slots": slots, "corrections": corrections, "negated_action": action if act == "NEGATED_COMMAND" else None,
            "pair_family": f"{split}:{action}:{verb}:{obj}:{group}",
            "language": "mixed" if any(x in text for x in ("don't", "did you", "what if", "suppose")) else "tanglish",
            "label_source": "declared_semantic_program"}


def build(seed: int = 2101) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    seen = set()
    report = {"seed": seed, "files": {}, "speech_acts": {}}
    actions = list(ACTION_MAP)
    for split in ("train", "dev_no_action", "dev_command"):
        rng = random.Random(f"{seed}:{split}")
        target = 16000 if split == "train" else 5000
        counts = Counter()
        path = OUT / f"{split}.jsonl.gz"
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            attempts = 0
            while sum(counts.values()) < target:
                attempts += 1
                if attempts > target * 100:
                    raise RuntimeError(f"Not enough unique examples for {split}")
                if split == "dev_no_action":
                    group = attempts // len(NO_ACTION)
                    act = sorted(NO_ACTION)[attempts % len(NO_ACTION)]
                elif split == "dev_command":
                    group = attempts // len(ELIGIBLE)
                    act = sorted(ELIGIBLE)[attempts % len(ELIGIBLE)]
                else:
                    group = attempts // len(ACTS)
                    act = ACTS[attempts % len(ACTS)]
                action = actions[group % len(actions)]
                row = render(rng, action, act, "train" if split == "train" else "dev", attempts, group)
                key = fingerprint(" [TURN] ".join(row["previous_turns"] + [row["text"]]))
                if key in seen:
                    continue
                seen.add(key)
                row["id"] = key
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                counts[act] += 1
        report["files"][split] = {"path": str(path.relative_to(ROOT)), "rows": target,
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        report["speech_acts"][split] = dict(counts)
    (OUT / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
