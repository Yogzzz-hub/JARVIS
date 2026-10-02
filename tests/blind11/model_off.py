"""Classify the Blind-11 cases that fell through the deterministic router to the (unavailable) model.

    python -m tests.blind11.model_off <run_b.json> [--out docs/BLIND11_MODEL_OFF.md]

A case "fell through" when JARVIS answered that it could not reach its local model. Each such case gets one class:

- MODEL_REQUIRED_UNAVAILABLE - the expected behaviour needs the model by design: a conversational answer, a multi-step
  plan, composing or summarising text, open-ended web / computer tasks, vision, document Q&A.
- ROUTER_CORRECT_ESCALATION_MODEL_UNAVAILABLE - a single-tool request said indirectly or ambiguously (category
  ``implicit`` / ``ambiguous``): handing it to the model is the intended architecture; it is not counted as a router bug.
- ROUTER_WRONG - an explicit request the deterministic router is expected to handle on its own (plain, noisy, Tanglish,
  negated or corrected wording of a tool it has), and every must-not-act case: safety must never depend on the model.

None of these count as successes. The split only says where the repair belongs.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

CASES = Path(__file__).with_name("cases.jsonl")
MODEL_TOOLS = {"ollama_chat", "quick_answer", "web_task", "computer_task", "summarize_whatsapp_messages", "whatsapp_summary",
               "describe_screen", "screen_op", "document_qa", "knowledge_search", "reply_whatsapp_message", "reply_whatsapp_all",
               "gmail_create_draft", "code_repair_loop", "explain_route", "planner"}
FELL = ("can't reach my local ai", "cannot reach my local ai", "couldn't reach my local ai")


def classify(case: dict) -> str:
    caps = set(case.get("capabilities") or [])
    if case["outcome"] in ("refuse",) or case.get("category") == "must_not_act":
        return "ROUTER_WRONG"
    if case["outcome"] in ("chat", "plan") or (caps and caps <= MODEL_TOOLS) or "compound" in caps and case.get("steps"):
        return "MODEL_REQUIRED_UNAVAILABLE"
    if case.get("category") in ("implicit", "ambiguous"):
        return "ROUTER_CORRECT_ESCALATION_MODEL_UNAVAILABLE"
    return "ROUTER_WRONG"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_b")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    cases = {json.loads(l)["id"]: json.loads(l) for l in CASES.read_text().splitlines() if l.strip()}
    rows = json.load(open(a.run_b))["rows"]
    fell = [r for r in rows if any(f in (r.get("message") or "").lower() for f in FELL)]
    cls = {r["id"]: classify(cases[r["id"]]) for r in fell}
    by = Counter(cls.values())
    by_phase = Counter((cases[i]["phase"], c) for i, c in cls.items())
    lines = ["# Blind-11: cases that needed the (unavailable) model", "",
             f"Run: `{a.run_b}`. {len(fell)} of {len(rows)} cases fell through the deterministic router to the local model, which is "
             "not installed in this environment (DEPENDENCY_UNAVAILABLE). None of them count as successes. The class says where the "
             "repair belongs (rules in `tests/blind11/model_off.py`).", "",
             "| Class | Cases | Meaning |", "|---|---:|---|",
             f"| ROUTER_WRONG | {by['ROUTER_WRONG']} | Explicit requests (or must-not-act cases) the deterministic router should handle itself. |",
             f"| ROUTER_CORRECT_ESCALATION_MODEL_UNAVAILABLE | {by['ROUTER_CORRECT_ESCALATION_MODEL_UNAVAILABLE']} | Indirect or ambiguous single-tool requests; escalating them to the model is intended. |",
             f"| MODEL_REQUIRED_UNAVAILABLE | {by['MODEL_REQUIRED_UNAVAILABLE']} | Conversation, planning, composing, vision, document Q&A: the model is the capability. |",
             "", "## By phase", "", "| Phase | Router wrong | Correct escalation | Model required |", "|---|---:|---:|---:|"]
    for ph in sorted({p for p, _ in by_phase}):
        lines.append(f"| {ph} | {by_phase[(ph, 'ROUTER_WRONG')]} | {by_phase[(ph, 'ROUTER_CORRECT_ESCALATION_MODEL_UNAVAILABLE')]} | "
                     f"{by_phase[(ph, 'MODEL_REQUIRED_UNAVAILABLE')]} |")
    lines += ["", "## Every case", "", "| Case | Class | Category | Expected | Command |", "|---|---|---|---|---|"]
    for r in fell:
        c = cases[r["id"]]
        lines.append(f"| {r['id']} | {cls[r['id']]} | {c.get('category', '')} | {c['outcome']}:{','.join((c.get('capabilities') or [])[:2])} | "
                     f"{c['utterance'].replace('|', '/')} |")
    text = "\n".join(lines) + "\n"
    if a.out:
        Path(a.out).write_text(text)
    print(f"fell through: {len(fell)}; " + ", ".join(f"{k} {v}" for k, v in by.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
