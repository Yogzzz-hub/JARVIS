"""Write docs/UNIVERSAL_OPERATOR_500PLUS_ACCEPTANCE.md from runner results.

    python -m tests.operator.runner --json dev.json
    python -m tests.operator.runner --holdout --json holdout.json
    python scripts/write_operator_acceptance.py dev.json holdout.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def table(title: str, d: dict) -> list[str]:
    rows = [f"### {title}", "", "| Slice | Passed | Total | Accuracy |", "|---|---:|---:|---:|"]
    for k, v in d.items():
        rows.append(f"| {k} | {v['passed']} | {v['total']} | {v['accuracy']}% |")
    return rows + [""]


def main() -> None:
    dev = json.loads(Path(sys.argv[1]).read_text())
    hold = json.loads(Path(sys.argv[2]).read_text())
    first = json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv) > 3 else None
    from tests.operator.scenarios import SCENARIOS
    fams = Counter(s.family for s in SCENARIOS)
    out = ["# Universal Operator - 500+ Scenario Acceptance", "",
           "Router-level acceptance of the operator scenarios (`tests/operator/`), measured in the CI container with "
           "**no AI model** (DisabledProvider): every number below is deterministic understanding. Execution on a real "
           "PC/phone is the separate checklist in `reports/UNIVERSAL_OPERATOR_REAL_ACCEPTANCE.md` (not yet run).", "",
           "## What a scenario is", "",
           "A meaning, not a sentence: setup state, semantic goal, constraints, the capability that must run (or that "
           "JARVIS must ask / refuse / plan), the expected state change, how it is verified, and the risk. Surface "
           "wordings are generated from each scenario's seed: **dev** forms (canonical, formal, casual, polite, wake "
           "word, ASR-style, short, typo) were used while building the parser; **holdout** forms (long run-up, \"for me\" "
           "tails, spoken numbers, \"kindly\", a different typo model, hesitation) were never used for tuning. Every "
           "action scenario is also checked in negated form (\"don't ...\") - nothing may run.", "",
           f"Scenarios: **{len(SCENARIOS)}** - " + ", ".join(f"{k} {v}" for k, v in sorted(fams.items())), "",
           "## Headline", "",
           "| Metric | Dev forms | Holdout forms |", "|---|---:|---:|",
           f"| Surface forms routed | {dev['forms']} | {hold['forms']} |",
           f"| Form accuracy | {dev['form_accuracy']}% | {hold['form_accuracy']}% |",
           f"| Scenarios with every form correct | {dev['scenario_all_forms_pass']} / {dev['scenarios']} | "
           f"{hold['scenario_all_forms_pass']} / {hold['scenarios']} |",
           f"| Negated forms checked / executed | {dev['negation']['total']} / {dev['negation']['executed']} | "
           f"{hold['negation']['total']} / {hold['negation']['executed']} |",
           f"| Security-bypass routes (secret fields, unlock, CAPTCHA) | {dev['zero_fail']['security_bypass_routes']} | "
           f"{hold['zero_fail']['security_bypass_routes']} |",
           f"| Forms routed to a different runnable tool | {dev['zero_fail']['wrong_capability_executed']} | "
           f"{hold['zero_fail']['wrong_capability_executed']} |",
           f"| Routing p50 / p95 (ms) | {dev['routing_ms']['p50']} / {dev['routing_ms']['p95']} | "
           f"{hold['routing_ms']['p50']} / {hold['routing_ms']['p95']} |", "",
           *([f"**Holdout first run** (before anything was changed in response to it): {first['form_accuracy']}% of "
              f"{first['forms']} forms, {first['scenario_all_forms_pass']} / {first['scenarios']} scenarios with every "
              f"form correct, {first['negation']['executed']} negated executions, "
              f"{first['zero_fail']['security_bypass_routes']} secret-field forms routed to the planner instead of a "
              "refusal. Its failures were mostly polite run-ups (\"hey jarvis, when you get a sec, ...\" was read as a "
              "standing rule) and dropped-letter typos (\"phne\", \"frst\", \"wrds\" - the dev typo model only "
              "swapped letters). Those were fixed generically (run-up stripping before routing, one-dropped-letter "
              "repair against the operator vocabulary, a text-unit guard on file deletion), so the holdout numbers "
              "in the table are **after** that round and are no longer a pure holdout; the first-run figure is the "
              "honest generalization estimate.", ""] if first else []),
           "\"Different runnable tool\" counts every form whose route was not the scenario's capability or one of its "
           "listed equivalents and was not a question or a plan. Most are typo forms of real English words "
           "(\"froth\", \"filed\") that are deliberately not corrected; they are listed below so nothing is hidden.", ""]
    out += table("Dev forms by family", dev["by_family"])
    out += table("Dev forms by surface form", dev["by_form"])
    out += table("Holdout forms by family", hold["by_family"])
    out += table("Holdout forms by surface form", hold["by_form"])
    for name, res in (("Dev", dev), ("Holdout", hold)):
        out += [f"## {name} failures ({len(res['failures'])})", ""]
        if res["failures"]:
            out += ["| Scenario | Form | Text | Why |", "|---|---|---|---|"]
            for r in res["failures"]:
                out.append(f"| {r['id']} | {r['form']} | {r['text'].replace('|', '/')} | {r['why'].replace('|', '/')[:140]} |")
        out.append("")
    out += ["## Zero-fail rules and how they are held", "",
            "| Rule | Mechanism | Evidence |", "|---|---|---|",
            "| Wrong-app typing = 0 | focus re-verified before every keystroke batch (`TextOperator._guard`, LiveDictation `_focus_ok`) | `test_typing_refuses_a_window_that_lost_focus`, `test_live_dictation_pauses_when_target_is_lost` |",
            "| Wrong control invocation = 0 | resolver ties -> question; nested scopes/references -> plan or ask | `test_resolver_scores_asks_on_ties_and_respects_ordinals` |",
            "| Negated action execution = 0 | negation guard before the operator parser | negated forms above; `test_negated_wording_never_runs` |",
            "| Unrelated capability = 0 for text units | 'delete the last three words' is text_op, never delete_file | `test_former_misroutes_are_fixed` |",
            "| Unverified send success = 0 | send needs approval; success only when the composer empties / Stop appears | `test_send_needs_approval`, `test_ide_prompt_write_and_send_are_observed` |",
            "| Duplicate uncertain send = 0 | approval re-runs the same prepared call once; no automatic retry of sends | `CommandService._operator_approval` |",
            "| Prompt-injection execution = 0 | page/notification/IDE/clipboard text returned as untrusted data | `evidence.untrusted` on reads |",
            "| Security bypass = 0 | secret fields refused, CAPTCHA/lock -> owner, no UAC automation | `test_sensitive_and_consequential_controls`, `test_phone_typed_operations_and_lock_guard` |",
            "| Ungrounded visual click = 0 | vision point validated against the element under it | `computer_use.validate_point` |", ""]
    path = ROOT / "docs" / "UNIVERSAL_OPERATOR_500PLUS_ACCEPTANCE.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
