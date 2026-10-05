"""Build the Stage-2 JARVIS SemanticFrame corpus from declared semantic programs.

Public text contributes aggregate language statistics only. No public sentence is
assigned an executable action. The locked split is written once and never used
for model selection.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/tanglish"
OUT = BASE / "generated/semantic_stage2"
SPLITS = {"train": .80, "dev": .10, "test": .05, "locked_holdout": .05}
CATEGORIES = {
    "clear": 20000, "natural_tanglish": 15000, "code_switch": 10000,
    "paraphrase": 10000, "typo_phonetic": 10000, "asr_noise": 5000,
    "contextual": 10000, "negation": 5000, "correction": 5000,
    "non_command": 5000, "ambiguous_no_action": 5000,
}
FIELDS = ("speech_act", "domain", "action_concept", "object_type", "object_ref", "target",
          "recipient", "sender", "source", "destination", "content", "query", "temporal",
          "quantity", "ordinal", "attributes", "include_constraints", "exclude_constraints",
          "negations", "corrections", "references", "context_refs", "should_act")

# ActionConcept is semantic. Tool names are intentionally absent.
ONTOLOGY = {
    "OPEN": ("pc", "file", "open", "thira", "open pannu"),
    "CLOSE": ("pc", "app", "close", "moodu", "close pannu"),
    "SEARCH": ("browser", "web", "search", "thedu", "search pannu"),
    "FIND": ("files", "file", "find", "kandupidi", "find pannu"),
    "SHOW": ("pc", "photo", "show", "kaatu", "kaami"),
    "LIST": ("files", "files", "list", "kaatu", "pattiyal kaatu"),
    "READ": ("whatsapp", "message", "read", "padi", "paaru"),
    "INSPECT": ("ide", "error", "inspect", "paaru", "check pannu"),
    "PROVIDE": ("pc", "answer", "provide", "kudu", "thaa"),
    "ANSWER": ("pc", "question", "answer", "kudu", "pathil sollu"),
    "RETURN": ("files", "file", "return", "kudu", "thiruppi kudu"),
    "WRITE": ("files", "note", "write", "ezhuthu", "write pannu"),
    "TYPE": ("pc", "text", "type", "type pannu", "ezhuthu"),
    "ENTER": ("pc", "password", "enter", "podu", "enter pannu"),
    "INSERT": ("files", "emoji", "insert", "podu", "insert pannu"),
    "SEND": ("whatsapp", "pdf", "send", "anupu", "anuppu"),
    "SHARE": ("files", "file", "share", "share pannu", "kudu"),
    "FORWARD": ("whatsapp", "message", "forward", "forward pannu", "anupu"),
    "REPLY": ("whatsapp", "message", "reply", "reply pannu", "pathil anupu"),
    "CREATE": ("files", "folder", "create", "uruvaakku", "create pannu"),
    "DELETE": ("files", "file", "delete", "azhichidu", "delete pannu"),
    "MOVE": ("files", "file", "move", "maathu", "move pannu"),
    "COPY": ("files", "file", "copy", "copy pannu", "nakal edu"),
    "RENAME": ("files", "file", "rename", "per maathu", "rename pannu"),
    "DOWNLOAD": ("browser", "file", "download", "download pannu", "irakku"),
    "UPLOAD": ("browser", "file", "upload", "upload pannu", "podu"),
    "ATTACH": ("email", "pdf", "attach", "attach pannu", "serthu podu"),
    "SAVE": ("files", "document", "save", "save pannu", "semichu vai"),
    "CONVERT": ("files", "pdf", "convert", "maathu", "convert pannu"),
    "CHANGE": ("pc", "language", "change", "maathu", "change pannu"),
    "REPLACE": ("files", "text", "replace", "maathu", "replace pannu"),
    "SWITCH": ("browser", "tab", "switch", "maathu", "switch pannu"),
    "SET": ("pc", "volume", "set", "podu", "maathu"),
    "INCREASE": ("pc", "brightness", "increase", "adhigam pannu", "raise pannu"),
    "DECREASE": ("pc", "volume", "decrease", "kammi pannu", "reduce pannu"),
    "RUN": ("ide", "script", "run", "run pannu", "ottu"),
    "START": ("pc", "service", "start", "start pannu", "thodangu"),
    "STOP": ("pc", "service", "stop", "niruthu", "stop pannu"),
    "PAUSE": ("pc", "music", "pause", "pause pannu", "niruthi vai"),
    "RESUME": ("pc", "music", "resume", "thodaru", "resume pannu"),
    "CHECK": ("ide", "status", "check", "paaru", "check pannu"),
    "VERIFY": ("ide", "result", "verify", "sari paaru", "verify pannu"),
    "COMPARE": ("files", "documents", "compare", "oppidu", "compare pannu"),
    "SELECT": ("files", "file", "select", "eduthu", "select pannu"),
    "CAPTURE": ("pc", "screenshot", "capture", "eduthu", "screenshot edu"),
    "RETRIEVE": ("files", "data", "retrieve", "eduthu", "data edu"),
    "FILTER": ("files", "pdfs", "filter", "vadikattu", "filter pannu"),
    "SORT": ("files", "files", "sort", "varisai podu", "sort pannu"),
    "PLAY": ("pc", "song", "play", "podu", "play pannu"),
    "MUTE": ("pc", "audio", "mute", "mute pannu", "satham niruthu"),
    "UNMUTE": ("pc", "audio", "unmute", "unmute pannu", "satham podu"),
    "CALL": ("phone", "contact", "call", "call pannu", "koopidu"),
    "INSTALL": ("pc", "software", "install", "podu", "install pannu"),
    "UNINSTALL": ("pc", "software", "uninstall", "neekku", "uninstall pannu"),
    "SUMMARIZE": ("whatsapp", "chat", "summarize", "surukku", "summary kudu"),
    "EXPLAIN": ("ide", "error", "explain", "vilakku", "sollu"),
    "NAVIGATE": ("browser", "page", "navigate", "poi kaatu", "navigate pannu"),
    "SUBMIT": ("browser", "form", "submit", "submit pannu", "samarpikka"),
    "CANCEL": ("pc", "task", "cancel", "rathu pannu", "cancel pannu"),
}

POLYSEMY = {
    "anupu": ("SEND", "SHARE", "FORWARD"),
    "maathu": ("CONVERT", "CHANGE", "REPLACE", "SWITCH", "SET", "MOVE"),
    "kudu": ("PROVIDE", "ANSWER", "RETURN", "SHARE", "REPLY", "EXPLAIN", "SUMMARIZE"),
    "kaatu": ("SHOW", "LIST", "READ", "NAVIGATE"),
    "eduthu": ("CAPTURE", "SELECT", "RETRIEVE"),
    "podu": ("PLAY", "SET", "ENTER", "INSERT", "UPLOAD", "INSTALL", "CREATE"),
    "paaru": ("CHECK", "INSPECT", "READ", "VERIFY", "SHOW"),
}
NAMES = ("Naveen", "Arun", "Priya", "Meena", "Karthik", "Divya", "Ravi", "Anu", "Bala", "Asha", "Siva", "Kumar", "Deepa", "Mohan")
PROJECTS = ("Atlas", "Cedar", "Helix", "Orbit", "Nimbus", "Phoenix", "Delta", "Sigma", "Mango", "CREO")
SELECTORS = (("latest", None), ("second", 2), ("third", 3), ("first", 1), ("last", -1), ("rendaavathu", 2))
TIME = ("ippo", "inniku", "naalaiku", "after lunch", "evening la", "tomorrow", "next week")
CHANNELS = ("whatsapp", "email", "browser", "local")
OBJECT_VARIANTS = {
    "pdf": ("pdf", "PDF", "document", "report"), "file": ("file", "document", "item", "attachment"),
    "message": ("msg", "message", "text", "chat message"), "photo": ("photo", "image", "picture", "pic"),
    "volume": ("volume", "sound", "audio level", "satham"), "software": ("software", "app", "program", "package"),
    "screenshot": ("screenshot", "screen shot", "display capture"),
    "answer": ("answer", "reply", "response"), "question": ("question", "query", "request"),
    "password": ("password", "secret", "login credential"), "emoji": ("emoji", "symbol", "smiley"),
    "data": ("data", "record", "entry"),
    "summary": ("summary", "short note", "surukkam"), "explanation": ("explanation", "reason", "vilakkam"),
    "reply": ("reply", "response", "pathil"),
    "tab": ("tab", "browser tab", "Chrome tab", "second tab"), "song": ("song", "music", "track", "audio"),
}
TEMPLATES = {
    "train": ("{obj} {verb}", "{verb} {obj}", "{selector} {obj} {verb}", "{name} kitta {obj} {verb}",
              "{project} la irukkura {obj} {verb}", "{obj} ah {verb} {time}",
              "{name} sonna {obj}, adha {verb}", "{project} mudiyum munadi {obj} {verb}",
              "{obj} mattum {verb}; vera ethuvum venam", "{name} oda {selector} {obj} {verb}",
              "{obj} {channel} la {verb}", "{project} work ku {obj} thevai; {verb}"),
    "dev": ("{project} pathi pesumbodhu, {obj} ah {verb}", "{time} kulla {selector} {obj} {verb}"),
    "test": ("{obj} ready aana udane {name} sonna maadhiri {verb}",),
    "locked_holdout": ("{name} oda {project} velai ku {selector} {obj} irukku; athaye {verb} {time}",),
}
NO_ACTION = {
    "QUESTION": ("{obj} {verb} mudiyuma nu ketten", "Is it possible to {verb} the {obj}?", "{verb} panna capability irukka?"),
    "STATEMENT": ("naan {obj} {verb} poren", "{name} already {obj} {verb} pannitanga", "Yesterday they said {obj} {verb} panniyachu"),
    "HYPOTHETICAL": ("{obj} {verb} panna enna aagum?", "What if I {verb} this {obj}?", "Suppose {obj} {verb} pannina?"),
    "DEFINITION": ("{verb} na enna?", "Explain what {verb} means for a {obj}"),
}


def language_stats() -> dict:
    """Aggregate only; never copy a public comment into a command."""
    source = BASE / "processed/dravidiancodemix/tamil_unique.jsonl"
    particles = Counter()
    punctuation = Counter()
    script = Counter()
    safe = {"da", "bro", "konjam", "ippo", "la", "ku", "kitta", "mattum", "please", "seri", "romba", "oda", "atha"}
    with source.open(encoding="utf-8") as stream:
        for line in stream:
            value = json.loads(line)["text"]
            words = re.findall(r"[a-z]+", value.casefold())
            particles.update(w for w in words if w in safe)
            punctuation.update(ch for ch in value if ch in "?!.,")
            script["mixed_script"] += bool(re.search(r"[\u0b80-\u0bff]", value) and re.search(r"[A-Za-z]", value))
            script["roman_only"] += not bool(re.search(r"[\u0b80-\u0bff]", value))
    # Only license-eligible, publisher-train transliteration rows contribute variant statistics.
    variant_counts = Counter()
    with (BASE / "processed/aksharantar_tamil/train.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["training_eligible"]:
                variant_counts[row["source"]] += 1
    return {"source": "DravidianCodeMix aggregate + eligible Aksharantar train counts", "safe_particle_counts": dict(particles),
            "punctuation_counts": dict(punctuation), "script_counts": dict(script),
            "eligible_transliteration_source_counts": dict(variant_counts)}


def frame(**kwargs) -> dict:
    result = {key: None for key in FIELDS}
    for key in ("attributes", "include_constraints", "exclude_constraints", "negations", "corrections", "references", "context_refs"):
        result[key] = [] if key != "attributes" else {}
    result.update(kwargs)
    return result


def make_row(rng: random.Random, category: str, split: str, number: int, stats: dict) -> dict:
    action = list(ONTOLOGY)[number % len(ONTOLOGY)]
    domain, typ, en, ta, alt = ONTOLOGY[action]
    language = "english" if category == "clear" and number % 3 else "tanglish"
    if category == "code_switch":
        language = "mixed"
    verb = en if language == "english" else rng.choice((ta, alt, en))
    if language != "english" and rng.random() < .5:
        candidates = [surface for surface, senses in POLYSEMY.items() if action in senses]
        if candidates:
            verb = rng.choice(candidates)
    if verb == "kudu":
        typ = {"ANSWER": "answer", "REPLY": "reply", "EXPLAIN": "explanation", "SUMMARIZE": "summary"}.get(action, typ)
    obj = rng.choice(OBJECT_VARIANTS.get(typ, (typ, typ.upper(), f"{typ} item")))
    name, project = rng.choice(NAMES), rng.choice(PROJECTS)
    selector, ordinal = rng.choice(SELECTORS)
    time = rng.choice(TIME)
    channel = domain if domain in CHANNELS else "local"
    template = rng.choice(TEMPLATES[split])
    text = template.format(obj=obj, verb=verb, selector=selector, name=name, project=project, time=time, channel=channel)
    query_value = None
    content_value = None
    if action in {"SEARCH", "FIND", "FILTER", "SORT", "COMPARE"}:
        query_value = f"{project} {obj}"
        text += f" for {query_value}"
    if action in {"WRITE", "TYPE", "REPLY"}:
        content_value = f"{project} review at 4"
        text += f' "{content_value}"'
    context_turns = []
    context_refs = []
    obj_ref = None
    recipient = name if action in {"SEND", "SHARE", "FORWARD", "REPLY", "CALL"} and "kitta" in text else None
    if action in {"SEND", "SHARE", "FORWARD", "REPLY", "CALL"} and recipient is None:
        text += f" {name} kitta"
        recipient = name
    if category == "natural_tanglish":
        particle = rng.choices(list(stats["safe_particle_counts"]) or ["konjam"],
                               weights=list(stats["safe_particle_counts"].values()) or [1])[0]
        if particle not in {"la", "ku", "kitta", "oda", "atha"}:
            text = f"{particle} {text}"
    if category == "code_switch":
        text = f"{text}, {rng.choice(('please', 'once', 'after checking', 'when ready'))}"
    if category == "paraphrase":
        text = f"{project} matter ku {text}; thevaiyana {obj} dhaan"
    if category == "typo_phonetic":
        variants = {"anupu": "annupu", "maathu": "mathu", "kudu": "kodu", "kaatu": "kaattu", "eduthu": "edthu", "podu": "potu", "paaru": "paru", "pannu": "panu"}
        for old, new in variants.items():
            if old in text:
                text = text.replace(old, new, 1)
                break
        else:
            text = text.replace(obj, obj[: max(2, len(obj)//2)] + obj[max(2, len(obj)//2):].replace("e", "ee", 1), 1)
    if category == "asr_noise":
        asr = {"anupu": "a noop", "maathu": "math who", "kudu": "could do", "kaatu": "car two", "podu": "pour do", "paaru": "par who"}
        for old, new in asr.items():
            if old in text:
                text = text.replace(old, new, 1)
                break
    if category == "contextual" or (category not in {"negation", "non_command", "ambiguous_no_action"} and number % 7 == 0):
        context_turns = [f"Earlier request: {text}", f"{name} oda {project} files la {selector} {obj} select panninen; current thread {channel} la irukku"]
        context_refs = [{"type": typ, "source_turn": -2, "selector": selector, "owner": name}]
        obj_ref = "selected_resource"
        text = f"atha {verb}" + (f" {name} kitta" if recipient else "")
    negations = []
    exclusions = []
    corrections = []
    quantity_value = None
    speech_act = "COMMAND"
    should_act = True
    if category == "negation":
        speech_act, should_act = "PROHIBITION", False
        text += " panna venam"
        negations = [action]
    elif category == "correction":
        if action in {"SEND", "SHARE", "FORWARD", "REPLY", "CALL"}:
            old = rng.choice(tuple(x for x in NAMES if x != name))
            correction_forms = {
                "train": f"{obj} {old} ku {verb}... illa {name} ku {verb}",
                "dev": f"{old} enbadhu thappu; {obj} {name} ku {verb}",
                "test": f"{obj} {name} ku dhaan {verb}; {old} ku venam",
                "locked_holdout": f"munnadi {old} sonnen; ippo {obj} {name} kitta {verb}",
            }
            text = correction_forms[split]
            corrections = [{"slot": "recipient", "superseded": old, "active": name}]
            exclusions = [{"slot": "recipient", "value": old}]
            recipient = name
        elif action in {"SET", "INCREASE", "DECREASE"}:
            before, after = rng.sample((20, 30, 40, 50, 60, 70, 80), 2)
            numeric_forms = {
                "train": f"{obj} {before} ku {verb}... illa {after} ku {verb}",
                "dev": f"{before} illa; {obj} {after} ku {verb}",
                "test": f"{obj} {after} ku dhaan {verb}; {before} venam",
                "locked_holdout": f"munnadi {before} sonnen; ippo {obj} {after} ku {verb}",
            }
            text = numeric_forms[split]
            corrections = [{"slot": "quantity", "superseded": before, "active": after}]
            quantity_value = after
        else:
            text = f"{obj} first {verb}... illa second {obj} {verb}"
            corrections = [{"slot": "ordinal", "superseded": 1, "active": 2}]
            ordinal = 2
    elif category == "non_command":
        speech_act = rng.choice(tuple(NO_ACTION))
        prompt = rng.choice(NO_ACTION[speech_act]).format(obj=obj, verb=verb, name=name)
        text = f'"{text}" nu irundha, {prompt}'
        should_act = False
    elif category == "ambiguous_no_action":
        speech_act, should_act = "AMBIGUOUS", False
        text = f'"{text}" nu irundha, ' + rng.choice((f"{project} la {selector} {obj} {ta} nu sonna enna meaning?",
                           f"{ta} or {alt}, which one for {name} oda {obj} {time}?",
                           f"{name} {project} oda {selector} {obj} {ta} nu sonnanga; athu enna meaning?"))
    if category == "asr_noise" and number % 3 == 0:
        speech_act, should_act = "UNCERTAIN_ASR", False
    if action in {"DELETE", "UNINSTALL", "SUBMIT", "CALL", "SEND"} and should_act:
        # Semantic request recognition is not authorization for execution.
        policy = "policy_review_required"
    else:
        policy = "normal"
    values = frame(speech_act=speech_act, domain=domain, action_concept=action, object_type=typ,
                   object_ref=obj_ref, target=obj if not obj_ref else None, recipient=recipient,
                   source=project if "project" in text.lower() or project in text else None,
                   destination=channel if action in {"SEND", "SHARE", "FORWARD", "UPLOAD", "DOWNLOAD", "MOVE"} else None,
                   content=content_value if content_value and content_value in text else None,
                   query=query_value if query_value and query_value in text else None,
                   temporal=time if time in text else None,
                   quantity=quantity_value, ordinal=ordinal if selector in text or obj_ref or category == "correction" and corrections and corrections[0]["slot"] == "ordinal" else None,
                   attributes={"policy_gate": policy}, include_constraints=[{"type": typ}] if action in {"SELECT", "FIND", "SEND"} else [],
                   exclude_constraints=exclusions, negations=negations, corrections=corrections,
                   references=[{"surface": "atha", "resolved_ref": obj_ref}] if obj_ref else [],
                   context_refs=context_refs, should_act=should_act)
    return {"text": text, "previous_turns": context_turns, "semantic_frame": values,
            "category": category, "language": language, "construction_family": f"{category}:{split}:{TEMPLATES[split].index(template)}",
            "label_source": "declared_semantic_program", "public_text_copied": False}


def normalized(text: str) -> str:
    return " ".join(re.findall(r"[\w]+", text.casefold()))


def build(seed: int = 842) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    locked_path = OUT / "locked_holdout.jsonl.gz"
    if locked_path.exists():
        raise FileExistsError(f"Locked holdout already exists; use a new versioned output directory: {locked_path}")
    stats = language_stats()
    (BASE / "manifests/semantic_language_stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    counts = Counter()
    category_counts = defaultdict(Counter)
    fingerprints = set()
    for split, proportion in SPLITS.items():
        path = OUT / f"{split}.jsonl.gz"
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            for category, total in CATEGORIES.items():
                target = int(total * proportion)
                rng = random.Random(f"{seed}:{split}:{category}")
                attempts = 0
                while category_counts[split][category] < target:
                    attempts += 1
                    if attempts > target * 200:
                        raise RuntimeError(f"Diversity exhausted: {split}/{category}")
                    row = make_row(rng, category, split, attempts, stats)
                    fingerprint = hashlib.sha256(normalized(" ".join(row["previous_turns"] + [row["text"]])).encode()).hexdigest()
                    if fingerprint in fingerprints:
                        continue
                    fingerprints.add(fingerprint)
                    row["id"] = fingerprint
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                    counts[split] += 1
                    category_counts[split][category] += 1
    report = {"seed": seed, "total": sum(counts.values()), "splits": dict(counts),
              "categories": {s: dict(c) for s, c in category_counts.items()},
              "ontology_actions": len(ONTOLOGY), "template_families": {s: len(TEMPLATES[s]) * len(CATEGORIES) for s in SPLITS},
              "public_sources_as_aggregate_only": ["DravidianCodeMix", "Aksharantar eligible publisher-train rows"],
              "locked_holdout_policy": "Never use for model selection; replace if inspected after final evaluation."}
    (BASE / "manifests/semantic_stage2_build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=842)
    args = parser.parse_args()
    print(json.dumps(build(args.seed), indent=2))
