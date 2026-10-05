"""Render Stage 2.2 development-only results with explicit measurement limits."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/tanglish/generated/stage22"
REPORT = ROOT / "reports/TANGLISH_STAGE22_REPORT.md"


def pct(value):
    return "N/A" if value is None else f"{value * 100:.2f}%"


def main():
    tri = json.loads((DATA / "tri_state_dev.json").read_text(encoding="utf-8"))
    caps = json.loads((DATA / "capability_dev.json").read_text(encoding="utf-8"))
    frame = json.loads((DATA / "frame_probe.json").read_text(encoding="utf-8"))
    s21 = json.loads((ROOT / "data/tanglish/generated/stage21/evaluation.json").read_text(encoding="utf-8"))
    final = tri["final"]
    precision = final["action_trigger_precision"]
    recall = final["candidate_command_recall"]
    f1 = 2*precision*recall/(precision+recall) if precision and recall else None
    t = tri["thresholds"]
    lines = ["# Tanglish Stage 2.2 development report", "",
             "**Recommendation: RETRAIN AGAIN.** The candidate remains offline; the original test and sealed holdout were not opened or evaluated.", "",
             "## Architecture and data", "",
             "The Stage 2.1 word TF-IDF binary gate is Lane 0. Scores below `T_NO_ACTION` return NO_ACTION; scores above `T_EXECUTE` produce EXECUTE_CANDIDATE; the middle goes to a word-plus-character 2–4 gram linear semantic fallback that reuses the word features. That fallback has its own no-action and candidate thresholds. A narrow full-action prohibition check overrides candidate routing while leaving object exclusions in the frame. Cases left between the thresholds require planner review or clarification. EXECUTE_CANDIDATE is a semantic label and never invokes a tool.",
             "The fallback was trained on the existing 80,000 Stage 2 train and 16,000 repair-train rows. No new large corpus was generated. Original Stage 2 dev and the two 5,000-case adversarial development sets were partitioned by stable ID or minimal-pair family before threshold tuning; one half calibrated the thresholds and the other half supplied the results below. The fallback is a second encoder, so this is not the requested one-pass multitask or contrastive model.",
             f"Calibration rows: {tri['calibration_rows']:,}. Development evaluation rows: {tri['evaluation_rows']:,}. The repair development partition has 865 calibration and 909 evaluation minimal-pair families with zero family overlap. Public corpora were not relabelled as executable commands.", "",
             "## Tri-state actionability", "",
             "| Threshold | Value |", "|---|---:|",
             f"| T_NO_ACTION | {t['t_no_action']:.4f} |",
             f"| T_EXECUTE | {t['t_execute']:.4f} |",
             f"| Semantic no-action | {t['t_semantic_no_action']:.4f} |",
             f"| Semantic candidate | {t['t_semantic_execute']:.4f} |", "",
             "| Metric | Fast lane | After fallback |", "|---|---:|---:|",
             f"| Action trigger precision | {pct(tri['fast']['action_trigger_precision'])} | {pct(precision)} |",
             f"| Candidate command recall | {pct(tri['fast']['candidate_command_recall'])} | {pct(recall)} |",
             f"| False action rate | {pct(tri['fast']['false_action_rate'])} | {pct(final['false_action_rate'])} |",
             f"| False NO_ACTION on true commands | {pct(tri['fast']['false_no_action_rate_on_commands'])} | {pct(final['false_no_action_rate_on_commands'])} |",
             f"| Uncertain | {pct(tri['fast']['uncertain_rate'])} | {pct(final['uncertain_rate'])} |", "",
             f"FastPathCoverage: {pct(tri['fast']['fast_coverage'])}. SemanticEscalationRate: {pct(tri['semantic_escalation_rate'])}. PlannerEscalationRate: {pct(tri['planner_or_clarification_rate'])}. Candidate action F1: {pct(f1)}. These candidate metrics do not count uncertain requests as completed actions.",
             f"Fine SpeechAct accuracy: {pct(tri['speech_act_accuracy'])}. ActionConcept accuracy: {pct(tri['action_concept_accuracy'])}. NEGATED_COMMAND speech recognition: {pct(tri['negated_command_recognition'])}. Explicit negated-command blocking: {pct(tri['explicit_negation_guard_accuracy'])} on the synthetic development labels. The check is grammar-limited and does not establish broad negation understanding. Fine speech and action heads are carried over from Stage 2.1.",
             "Risk-conditioned execution thresholds were not applied to semantic truth. Every candidate still needs a complete frame, capability, and downstream policy decision. The risk table below groups by ActionConcept proxy, not by an executed capability.", "",
             "| Risk proxy | Rows | False action rate | False candidates |", "|---|---:|---:|---:|"]
    for name, v in tri["risk_false_action"].items():
        lines.append(f"| {name} | {v['rows']} | {pct(v['false_action_rate'])} | {v['fp']} |")
    lines += ["", "## Language and failure clusters", "",
              "| Language | Rows | Trigger precision | Candidate recall | False action rate | SpeechAct accuracy | ActionConcept accuracy |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, v in tri["language"].items():
        lines.append(f"| {name} | {v['rows']} | {pct(v['action_trigger_precision'])} | {pct(v['candidate_command_recall'])} | {pct(v['false_action_rate'])} | {pct(v['speech_act_accuracy'])} | {pct(v['action_concept_accuracy'])} |")
    lines += ["", "| Construction category | Rows | Candidate recall | Uncertain |", "|---|---:|---:|---:|"]
    for name, v in tri["category"].items():
        lines.append(f"| {name} | {v['rows']} | {pct(v['candidate_command_recall'])} | {pct(v['uncertain_rate'])} |")
    lines += ["", "The largest unresolved cluster is genuine commands routed to UNCERTAIN. A much smaller number of commands enter NO_ACTION. The existing fine speech head still confuses corrections, meta controls, questions and statements with commands; the [Stage 2.1 matrix](TANGLISH_ACTIONABILITY_REPAIR.md) gives counts. Noisy and ASR-like categories are synthetic and have limited coverage. Prosody was unavailable.",
              "Verb-sense accuracy was not re-estimated under this new partition; the prior [Stage 2.1 per-family results](TANGLISH_ACTIONABILITY_REPAIR.md) remain the relevant diagnostic. A new contrastive representation or weighted neural multitask loss was not trained.", "",
              "## Typed frame and constraints", "",
              "The offline typed frame defines all 33 requested slot names and uses ContactRefCandidate, FileRefCandidate, AppRefCandidate, BrowserTabRefCandidate, and TemporalRange values where grounded. It extracts some corrections, exclusions, ordinal, numeric, temporal, and contextual references. Unsupported or unresolved values remain empty. It has no executor access.",
              f"On {frame['cases']} hand-specified development probes, **selected annotated fields only** scored precision {pct(frame['slot_precision'])}, recall {pct(frame['slot_recall'])}, F1 {pct(frame['slot_f1'])}, and selected-field exact match {pct(frame['selected_field_exact_match'])}. The probes were inspected during implementation; these scores are sanity checks, not independent validation.",
              f"The earlier {s21['slot_probe']['evaluated_rows']:,}-row synthetic probe for six supported slots scored micro F1 {pct(s21['slot_probe']['micro_f1'])} and limited-slot exact match {pct(s21['slot_probe']['exact_match'])}. Many required slots have zero gold support. Full SemanticFrame exact match, general correction accuracy, constraint accuracy, and reference-resolution accuracy are **not measured**. The frame probe's per-slot counts are in the ignored local `data/tanglish/generated/stage22/frame_probe.json`.", "",
              "## Capability ranking", "",
              f"The existing registry has {caps['registry_capabilities']} capabilities. Eighteen independently specified confusion cases were ranked with its lexical retriever, then with a frame-aware reranker using action, domain, resource, schema compatibility, and registry descriptions. Live availability was not checked.",
              "| Rank metric | Existing lexical | Frame aware |", "|---|---:|---:|",
              *[f"| Recall@{k} | {pct(caps['lexical_baseline'][f'recall_at_{k}'])} | {pct(caps['frame_aware'][f'recall_at_{k}'])} |" for k in (1,3,5,10)],
              f"| MRR | {caps['lexical_baseline']['mrr']:.3f} | {caps['frame_aware']['mrr']:.3f} |",
              "The small authored set includes file versus web search, WhatsApp versus Gmail send, file versus shortcut delete, app versus URL open, and git versus system status. The registry lacks a phone-call mute capability and separate project-status capability, so those requested confusion pairs cannot be scored against a real gold capability. This ranking score is not representative capability accuracy. No capability was invoked.", "",
              "## Latency and acceptance", "",
              "| Offline phase | p50 ms | p95 ms | p99 ms |", "|---|---:|---:|---:|"]
    for name, value in tri["latency_ms"].items():
        lines.append(f"| {name} | {value['p50']:.2f} | {value['p95']:.2f} | {value['p99']:.2f} |")
    lines += ["", f"Capability ranking averaged {caps['latency_ms_per_case']:.2f} ms per authored case including one-time registry/index construction; it was not timed as a warmed runtime component. English-only latency was not measured separately. The Stage 2.1 model artifact is {(ROOT / 'models/tanglish_stage21/candidate_dev_only.pkl').stat().st_size / 1_000_000:.1f} MB and the fallback artifact is {(DATA / 'semantic_fallback.pkl').stat().st_size / 1_000_000:.1f} MB. Peak RAM and VRAM were not measured. The linear fallback runs on CPU and does not use GPU VRAM.",
              "**Sandbox action precision, action recall/F1, ExactVerifiedActionAccuracy, and FalseSuccessRate: N/A.** Semantic candidate recall, complete slots, and general capability accuracy are below the evidence needed for a meaningful sandbox execution benchmark. No external messages, destructive tools, or live JARVIS actions were run.",
              "The fast path covers less than the 60–80% target, and after fallback only about half of true commands become executable candidates. The substantial UNCERTAIN share is correctly withheld for planner or clarification, but no measured planner resolves it. The original test and sealed holdout remain unopened. **Final recommendation: RETRAIN AGAIN.**", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
