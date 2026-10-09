"""Structural validator for BLIND-12 cases.jsonl."""
import json, re, sys, collections
sys.path.insert(0, '/tmp/claude-0/blind12_gen/fixtures')
BASE = '/tmp/claude-0/blind12_gen/'
caps = json.load(open(BASE + 'capabilities.json'))
ARGS = {t['tool']: set(t['args']) for t in caps['tools']}
for t in caps['runtime_and_control']:
    ARGS.setdefault(t['tool'], set(t.get('args', {})) - {''})
ARGS['pc_quick_action'] |= {'action', 'app'}
ARGS['compound'] = set()
PHASES = ["01_router", "02_core_os", "03_safety", "04_whatsapp", "05_multistep", "06_files", "07_intelligence",
          "08_voice_output", "09_phone", "10_google", "11_browser_control", "12_vision", "13_pc_control",
          "14_history_memory", "15_chat", "16_tanglish", "17_voice_input", "18_operator", "19_browser_automation",
          "20_phone_calls", "21_automation", "22_workflows_dev"]
CATS = {"normal", "paraphrase", "noisy", "implicit", "context", "negation_correction", "ambiguous", "must_not_act", "edge"}
OUTS = {"action", "plan", "clarify", "refuse", "chat", "control"}
CONS = {"negation", "correction", "exclusion", "inclusion", "quantity", "time", "filetype", "location", "recipient",
        "ordinal", "scope", "sender"}
CHAT_OK = {"ollama_chat", "quick_answer", "search_web", "knowledge_search", "document_qa", "explain_route", "CONTROL:cancel_task"}
PAGES = {"index.html", "search.html", "form.html", "shop.html", "cart.html", "table.html", "downloads.html", "modal.html",
         "delayed.html", "captcha.html", "article.html", "pricing.html", "newwindow.html"}
BROWSER_POST = {"js", "url_endswith", "download_name_contains", "any_page_url_endswith", "page_count_at_least", "url_changed"}
REQ = ["id", "phase", "category", "utterance", "should_act", "outcome", "capabilities", "slots", "forbidden_capabilities",
       "confirmation", "constraints", "criticality", "note"]
try:
    from sandbox import FILES
except Exception:
    FILES = {}
SANDBOX = set(FILES)

errors, warnings = [], []
cases = [json.loads(l) for l in open(BASE + 'cases.jsonl') if l.strip()]
ids = collections.Counter(c.get('id') for c in cases)
for i, n in ids.items():
    if n > 1:
        errors.append(f"duplicate id {i}")
per = collections.Counter(c.get('phase') for c in cases)
for p in PHASES:
    if per[p] != 50:
        errors.append(f"phase {p} has {per[p]} cases (want 50)")
if len(cases) != 1100:
    errors.append(f"total {len(cases)} (want 1100)")


def norm(v):
    return re.sub(r"[^a-z0-9 ]+", "", str(v).lower()).strip()


utt_seen = collections.defaultdict(list)
for c in cases:
    cid = c.get('id', '?')
    E = lambda m: errors.append(f"{cid}: {m}")
    for k in REQ:
        if k not in c:
            E(f"missing field {k}")
    if c.get('phase') not in PHASES:
        E("bad phase")
    if not re.fullmatch(rf"B12-{re.escape(c.get('phase', ''))}-\d\d", cid):
        E("id does not match phase")
    if c.get('category') not in CATS:
        E("bad category")
    out = c.get('outcome')
    if out not in OUTS:
        E("bad outcome")
    acting = out in ("action", "plan", "control")
    if c.get('should_act') is not acting:
        E(f"should_act {c.get('should_act')} inconsistent with outcome {out}")
    cp = c.get('capabilities', [])
    steps = c.get('steps', [])
    for t in cp + steps + c.get('forbidden_capabilities', []):
        if t not in ARGS:
            E(f"unknown tool {t}")
    if out in ("action", "control") and not cp:
        E("action/control without capabilities")
    if out == "control" and not any(t.startswith("CONTROL:") for t in cp):
        E("control outcome without a CONTROL:* capability")
    if out in ("clarify", "refuse") and cp:
        E("clarify/refuse must not list capabilities")
    if out == "chat" and set(cp) - CHAT_OK:
        E(f"chat lists acting tools {set(cp) - CHAT_OK}")
    if "compound" in cp and len(steps) < 2:
        E("compound without >=2 steps")
    overlap = set(c.get('forbidden_capabilities', [])) & (set(cp) | set(steps))
    if overlap:
        E(f"forbidden capability also expected: {overlap}")
    for tool, args in c.get('slots', {}).items():
        if tool not in ARGS:
            E(f"slot tool {tool} unknown")
            continue
        if tool not in cp and tool not in steps:
            E(f"slot tool {tool} not in capabilities/steps")
        for a, vals in args.items():
            if a not in ARGS[tool]:
                E(f"slot arg {a} not an argument of {tool}")
            if not isinstance(vals, list) or not vals or not all(isinstance(v, str) for v in vals):
                E(f"slot {tool}.{a} must be a non-empty list of strings")
            for fv in c.get('forbidden_values', []):
                if any(norm(fv) and norm(fv) == norm(v) for v in vals):
                    E(f"forbidden value {fv!r} equals required slot {tool}.{a}")
    conf = c.get('confirmation')
    if conf not in ("required", "none", "n/a"):
        E("bad confirmation")
    if acting and conf == "n/a":
        E("acting case with confirmation n/a")
    if not acting and conf != "n/a":
        E("non-acting case must have confirmation n/a")
    if c.get('criticality') not in ("C0", "C1", "C2", "C3", "C4"):
        E("bad criticality")
    for con in c.get('constraints', []):
        if con.get('type') not in CONS or not con.get('value'):
            E(f"bad constraint {con}")
    if 'context' in c and (not isinstance(c['context'], list) or not all(isinstance(x, str) and x for x in c['context'])):
        E("context must be a list of strings")
    if c.get('category') == 'context' and not c.get('context'):
        E("context category without context turns")
    ex = c.get('exec')
    if ex is not None:
        if out != "action":
            E("exec on a non-action case")
        if not ex.get('post'):
            E("exec without postcondition")
        if ex.get('kind') == 'file':
            for p in ex['post']:
                (k, v), = p.items()
                if k not in ("exists", "missing", "file_contains"):
                    E(f"bad file post {k}")
                if k == 'missing' and v not in SANDBOX:
                    warnings.append(f"{cid}: 'missing' check on {v} which is not an original sandbox file (negative check)")
        elif ex.get('kind') == 'browser':
            if ex.get('start') not in PAGES:
                E(f"bad start page {ex.get('start')}")
            for p in ex['post']:
                keys = set(p) - {"equals"}
                if not keys or not keys <= BROWSER_POST:
                    E(f"bad browser post {p}")
                if "js" in p and "equals" not in p:
                    E("js post without equals")
        else:
            E("exec kind must be file or browser")
    if c.get('phase') == "19_browser_automation" and out == "action" and not ex:
        E("browser automation action without exec")
    if not str(c.get('note', '')).strip():
        E("empty note")
    key = norm(c.get('utterance', '')) + " || " + " | ".join(norm(x) for x in c.get('context', []))
    utt_seen[key].append(cid)

dups = {k: v for k, v in utt_seen.items() if len(v) > 1}
for k, v in dups.items():
    errors.append(f"duplicate utterance+context within dataset: {v}")

oc = collections.Counter(c['outcome'] for c in cases)
crit = collections.Counter(c['criticality'] for c in cases)
nexec = collections.Counter(c['exec']['kind'] for c in cases if 'exec' in c)
print(f"cases: {len(cases)}  phases: {len(per)}  ids unique: {len(ids) == len(cases)}")
print("outcomes:", dict(oc))
print("criticality:", dict(sorted(crit.items())))
print("exec:", dict(nexec), " with context:", sum(1 for c in cases if c.get('context')))
print("should_act true:", sum(c['should_act'] for c in cases))
print(f"warnings: {len(warnings)}")
for w in warnings:
    print("  WARN", w)
print(f"errors: {len(errors)}")
for e in errors:
    print("  ERR", e)
print("RESULT:", "PASS" if not errors else "FAIL")
sys.exit(1 if errors else 0)
