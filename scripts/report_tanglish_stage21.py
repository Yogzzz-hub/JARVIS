"""Render the offline Stage 2.1 development evaluation as a reviewable report."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "data/tanglish/generated/stage21/evaluation.json"
AUDIT = ROOT / "data/tanglish/generated/stage21/audit.json"
REPORT = ROOT / "reports/TANGLISH_ACTIONABILITY_REPAIR.md"


def pct(value):
    return "N/A" if value is None else f"{100 * value:.2f}%"


def main():
    data = json.loads(EVAL.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    models = data["models"]
    lines = ["# Tanglish Stage 2.1 actionability repair", "",
             "**Decision: RETRAIN AGAIN. No production or sandbox executor is connected.**",
             "The existing sealed holdout was not opened, inspected, hashed, evaluated, or changed. The original test was not opened in this stage.", "",
             "## Data and method", "",
             f"Original train plus repair train: {data['train_rows']:,} rows. Original dev plus adversarial dev: {audit['dev_rows']:,} rows.",
             "The adversarial dev material contains 5,000 action-word noncommands and 5,000 commands/corrections/meta controls."
             " Each set was split in half for threshold calibration and reporting. All examples are synthetic declared programs; none is independent human annotation.",
             "The repair train contains 1,450 complete ten-way minimal-pair families sharing an action, object, and verb across speech acts.",
             f"Normalized train/dev overlap: {audit['normalized_train_dev_overlap']}. Train unique: {audit['train_unique_normalized']:,}; dev unique: {audit['dev_unique_normalized']:,}.",
             "The speech taxonomy is COMMAND, QUESTION, CAPABILITY_QUERY, STATEMENT, HYPOTHETICAL, NEGATED_COMMAND, CORRECTION, CHAT, META_CONTROL, AMBIGUOUS."
             " Execution eligibility is derived from COMMAND, CORRECTION, and META_CONTROL; corrections still require a pending frame.",
             "Original PROHIBITION, DEFINITION, and UNCERTAIN_ASR labels were mapped to NEGATED_COMMAND, CHAT, and AMBIGUOUS for training.", "",
             "| Speech act | Train count | Share | Inverse-frequency weight (descriptive only) |", "|---|---:|---:|---:|"]
    total = data["speech_training_rows"]
    for name, count in sorted(data["train_speech_distribution"].items()):
        lines.append(f"| {name} | {count:,} | {100*count/total:.1f}% | {total/(len(data['train_speech_distribution'])*count):.2f} |")
    lines += ["", f"The speech and binary gate heads used {total:,} rows and sklearn `class_weight=balanced`; the action head used all {data['train_rows']:,} rows. The weight column describes the resulting distribution. A one-in-eight COMMAND sampling experiment reduced speech accuracy to 73.11% and hierarchical command recall to 25.88%; it was rejected.",
              "The common word 1–3 gram TF-IDF vector feeds both architectures. Architecture A sums executable speech-class probabilities and runs the action head only above threshold. Architecture B uses a binary hierarchical gate before the same action and slot probes. These are linear baselines, not a neural shared semantic encoder.", "",
              "## Development evaluation", "",
              "Thresholds were selected on 10,000 calibration rows using the highest command recall subject to ≥99% precision and <0.5% false-action rate. The other 10,000 development rows supply the table below. These are related synthetic families, so the numbers can be optimistic.", "",
              "| Architecture | Threshold | Trigger precision | Command recall | False action rate | No-action specificity | Speech act accuracy | Action concept accuracy | Negation recognition | Brier | ECE |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, model in models.items():
        m = model["evaluation"]
        lines.append(f"| {name} | {model['threshold']:.4f} | {pct(m['action_trigger_precision'])} | {pct(m['command_recall'])} | {pct(m['false_action_rate'])} | {pct(m['no_action_specificity'])} | {pct(m['speech_act_accuracy'])} | {pct(m['action_concept_accuracy'])} | {pct(m['negated_command_recognition'])} | {m['brier']:.4f} | {m['ece_10_bins']:.4f} |")
    lines += ["", "No-action specificity is 1 minus false-action rate. SafetyWeightedError penalizes false actions by 10, or 20 for a high-risk action concept; missed actions cost 2. The class and cost values are experimental, not production policy.", "",
              "| Architecture | TP | FP | FN | TN | SafetyWeightedError/row |", "|---|---:|---:|---:|---:|---:|"]
    for name, model in models.items():
        m = model["evaluation"]
        lines.append(f"| {name} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | {m['safety_weighted_error_per_row']:.4f} |")
    lines += ["", "Full precision–recall arrays, threshold options, and confidence histograms are in the ignored local `data/tanglish/generated/stage21/evaluation.json`. Calibration here means threshold selection; probability calibration was measured with Brier/ECE but no post-hoc calibrator was fitted.", "",
              "### Speech-act confusion matrix", "", "Rows are truth, columns are prediction; class order:",
              "`" + ", ".join(models["shared_multitask"]["evaluation"]["speech_classes"]) + "`", "", "```text"]
    for name, row in zip(models["shared_multitask"]["evaluation"]["speech_classes"], models["shared_multitask"]["evaluation"]["speech_confusion"]):
        lines.append(f"{name:20} " + " ".join(f"{value:5}" for value in row))
    lines += ["```", "", "## Verb sense and contextual probes", "",
              "| Surface family | Rows | ActionConcept accuracy |", "|---|---:|---:|"]
    for name, score in data["verb_sense"].items():
        lines.append(f"| {name} | {score['rows']} | {pct(score['action_accuracy'])} |")
    lines += ["", f"Synthetic context-reference target accuracy: {pct(data['reference_accuracy_on_synthetic_context'])}. Synthetic correction-recipient accuracy: {pct(data['correction_recipient_accuracy_on_synthetic_dev'])}. These probes do not measure general reference or correction accuracy.",
              "", "## Typed slots and remaining gaps", "",
              "The offline slot probe extracts explicit target, recipient, ordinal, file type, application, and destination relations. It leaves absent values unresolved; it does not authorize any action. Its synthetic label support is sparse and partly inconsistent, so the following is diagnostic only.",
              "", "| Slot | Gold positives | Precision | Recall | F1 |", "|---|---:|---:|---:|---:|"]
    slot = data["slot_probe"]
    for name, m in slot["per_slot"].items():
        lines.append(f"| {name} | {m['gold_positive']} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} |")
    lines += ["", f"Observed-slot micro precision/recall/F1: {pct(slot['micro_precision'])} / {pct(slot['micro_recall'])} / {pct(slot['micro_f1'])}. Exact match across supported slots: {pct(slot['exact_match'])} on {slot['evaluated_rows']:,} development rows.",
              "Unlabelled requested slots, include/exclude constraints, correction application, temporal constraints, and typed reference resolution have no valid accuracy estimate. Whole SemanticFrame exact match is likewise unmeasured.",
              "Capability Recall@1/3/5, MRR, selection confusion pairs, sandbox execution, verified action accuracy, and false-success rate are unmeasured because the semantic frame fails the gate. No test or sealed holdout evaluation was performed.", "",
              "## Runtime and recommendation", "",
              f"Offline semantic inference p50/p95/p99: {data['latency_ms']['p50']:.2f}/{data['latency_ms']['p95']:.2f}/{data['latency_ms']['p99']:.2f} ms per request on this machine. Training plus development evaluation took {data['training_seconds']:.1f} seconds. The model uses CPU; GPU VRAM use for this benchmark is zero. The local candidate pickle is {(ROOT / 'models/tanglish_stage21/candidate_dev_only.pkl').stat().st_size / 1_000_000:.1f} MB. Peak RAM was not measured.",
              "The dominant failures are speech-act confusions around corrections, meta controls, questions and ambiguous wording, followed by missing typed slots. The targets of ≥99% trigger precision, <0.5% false actions, ≥95% command recall, ≥95% speech accuracy, ≥99% negation recognition, and ≥99% no-action specificity are **not jointly met**. Further work needs independently reviewed labels, better correction/context supervision, and a trained slot decoder before any test or sealed holdout run.", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    training = ROOT / "reports/TANGLISH_SEMANTIC_TRAINING.md"
    old = training.read_text(encoding="utf-8")
    marker = "\n## Stage 2.1 continuation\n"
    old = old.split(marker)[0]
    old += marker + "\nThe [Stage 2.1 repair report](TANGLISH_ACTIONABILITY_REPAIR.md) compares two shared-representation actionability architectures, adds 10,000 adversarial development examples, and measures a limited typed-slot probe. The outcome remains **RETRAIN AGAIN**. The existing sealed holdout and original test were not used in Stage 2.1.\n"
    training.write_text(old, encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
