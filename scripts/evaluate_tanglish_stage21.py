"""Offline Stage 2.1 comparison on train/dev only; never opens test or holdout."""
from __future__ import annotations

import gzip
import json
import pickle
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import confusion_matrix, precision_recall_curve

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.build_tanglish_stage21_repair import ELIGIBLE, HIGH_RISK, OUT
from scripts.tanglish_stage21_slots import SLOT_NAMES, extract_slots

MODEL = Path("models/tanglish_stage21")
LEGACY_SPEECH = {"PROHIBITION": "NEGATED_COMMAND", "DEFINITION": "CHAT",
                 "UNCERTAIN_ASR": "AMBIGUOUS"}


def read(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def legacy(row):
    frame = row["semantic_frame"]
    return {"text": row["text"], "previous_turns": row["previous_turns"],
            "speech_act": LEGACY_SPEECH.get(frame["speech_act"], frame["speech_act"]),
            "action_concept": frame["action_concept"], "should_act": frame["should_act"],
            "slots": {}, "category": row["category"], "language": row["language"],
            "id": row.get("id")}


def input_text(row):
    return " [TURN] ".join(row["previous_turns"][-2:] + [row["text"]])


def metric(y, predicted, speech_true, speech_pred, action_true, action_pred, probability):
    y = np.asarray(y, dtype=bool)
    predicted = np.asarray(predicted, dtype=bool)
    tp = int(np.sum(predicted & y)); fp = int(np.sum(predicted & ~y))
    fn = int(np.sum(~predicted & y)); tn = int(np.sum(~predicted & ~y))
    high = np.array([a in HIGH_RISK for a in action_true])
    costs = np.where(high, 20, 10)
    safety_error = float((np.sum(costs[predicted & ~y]) + 2 * fn) / len(y))
    brier = float(np.mean((probability - y.astype(float)) ** 2))
    bins = np.linspace(0, 1, 11)
    ece = 0.0
    histogram = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (probability >= lo) & (probability < hi if hi < 1 else probability <= hi)
        if np.any(mask):
            observed = float(np.mean(y[mask])); confidence = float(np.mean(probability[mask]))
            ece += float(np.mean(mask)) * abs(observed - confidence)
            histogram.append({"range": [float(lo), float(hi)], "n": int(np.sum(mask)),
                              "mean_confidence": confidence, "observed_action_rate": observed})
    classes = sorted(set(speech_true) | set(speech_pred))
    return {"rows": len(y), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "action_trigger_precision": tp / (tp + fp) if tp + fp else None,
            "command_recall": tp / (tp + fn) if tp + fn else None,
            "false_action_rate": fp / (fp + tn) if fp + tn else None,
            "no_action_specificity": tn / (fp + tn) if fp + tn else None,
            "speech_act_accuracy": float(np.mean(np.array(speech_true) == np.array(speech_pred))),
            "action_concept_accuracy": float(np.mean(np.array(action_true) == np.array(action_pred))),
            "negated_command_recognition": float(np.mean(np.array(speech_pred)[np.array(speech_true) == "NEGATED_COMMAND"] == "NEGATED_COMMAND"))
                if "NEGATED_COMMAND" in speech_true else None,
            "safety_weighted_error_per_row": safety_error, "brier": brier,
            "ece_10_bins": ece, "confidence_histogram": histogram,
            "speech_classes": classes,
            "speech_confusion": confusion_matrix(speech_true, speech_pred, labels=classes).tolist()}


def threshold_table(y, p):
    precision, recall, cutoffs = precision_recall_curve(y, p)
    result = []
    for t in sorted(set([.3, .5, .7, .8, .9, .95, .98] + [float(x) for x in np.quantile(p, [.1, .25, .5, .75, .9])])):
        pred = p >= t
        tp = int(np.sum(pred & y)); fp = int(np.sum(pred & ~y)); fn = int(np.sum(~pred & y)); tn = int(np.sum(~pred & ~y))
        result.append({"threshold": t, "precision": tp / max(1, tp + fp),
                       "recall": tp / max(1, tp + fn), "false_action_rate": fp / max(1, fp + tn)})
    # Search every observed operating point; coarse display thresholds are not used for selection.
    order = np.argsort(-p)
    sorted_y = y[order]
    tp = np.cumsum(sorted_y)
    fp = np.cumsum(~sorted_y)
    recall_all = tp / max(1, int(np.sum(y)))
    precision_all = tp / np.maximum(1, tp + fp)
    far_all = fp / max(1, int(np.sum(~y)))
    valid = np.where((precision_all >= .99) & (far_all < .005))[0]
    if len(valid):
        best = valid[np.argmax(recall_all[valid])]
        chosen = float(p[order[best]])
    else:
        chosen = 1.0
    return chosen, result, {"precision": precision.tolist(), "recall": recall.tolist(), "thresholds": cutoffs.tolist()}


def main():
    began = time.perf_counter()
    old_train = [legacy(x) for x in read(BASE / "generated/semantic_stage2/train.jsonl.gz")]
    old_dev = [legacy(x) for x in read(BASE / "generated/semantic_stage2/dev.jsonl.gz")]
    repair_train = read(OUT / "train.jsonl.gz")
    adv_no = read(OUT / "dev_no_action.jsonl.gz")
    adv_yes = read(OUT / "dev_command.jsonl.gz")
    train = old_train + repair_train
    # Separate calibration and evaluation halves before selecting threshold.
    calibration = old_dev[::2] + adv_no[::2] + adv_yes[::2]
    evaluation = old_dev[1::2] + adv_no[1::2] + adv_yes[1::2]
    vectorizer = TfidfVectorizer(ngram_range=(1, 3), analyzer="word", min_df=2,
                                max_features=120000, sublinear_tf=True,
                                token_pattern=r"(?u)\b\w+\b")
    x = vectorizer.fit_transform(input_text(row) for row in train)
    x_cal = vectorizer.transform(input_text(row) for row in calibration)
    x_eval = vectorizer.transform(input_text(row) for row in evaluation)
    speech_y = np.array([r["speech_act"] for r in train])
    action_y = np.array([r["action_concept"] for r in train])
    gate_y = np.array([r["should_act"] for r in train], dtype=int)
    class_counts = Counter(speech_y)
    action = SGDClassifier(loss="log_loss", alpha=0.00002, max_iter=20, random_state=21)
    action.fit(x, action_y)
    speech = SGDClassifier(loss="log_loss", alpha=0.00002, max_iter=20, class_weight="balanced", random_state=22)
    speech.fit(x, speech_y)
    gate = SGDClassifier(loss="log_loss", alpha=0.00002, max_iter=20, class_weight="balanced", random_state=23)
    gate.fit(x, gate_y)
    speech_idx = [int(np.where(speech.classes_ == c)[0][0]) for c in ELIGIBLE]
    p_a = np.sum(speech.predict_proba(x_cal)[:, speech_idx], axis=1)
    p_b = gate.predict_proba(x_cal)[:, 1]
    y_cal = np.array([r["should_act"] for r in calibration], dtype=bool)
    reports = {}
    action_true = [r["action_concept"] for r in evaluation]
    action_pred = action.predict(x_eval)
    speech_true = [r["speech_act"] for r in evaluation]
    speech_pred = speech.predict(x_eval)
    verb_families = {"maathu": ("maathu", "mathu"), "kudu": ("kudu", "kodu"),
                     "eduthu": ("eduthu", "edthu"), "podu": ("podu", "potu"),
                     "paaru": ("paaru", "paru"), "sollu": ("sollu", "solu"),
                     "pannu": ("pannu", "panu"), "anupu": ("anupu", "anuppu", "annupu")}
    verb_sense = {}
    for family, forms in verb_families.items():
        indices = [i for i, row in enumerate(evaluation) if any(re.search(rf"\b{re.escape(form)}\b", row["text"].casefold()) for form in forms)]
        verb_sense[family] = {"rows": len(indices), "action_accuracy": float(np.mean(action_pred[indices] == np.array(action_true)[indices])) if indices else None}
    for name, cal_p, eval_p in (("shared_multitask", p_a, np.sum(speech.predict_proba(x_eval)[:, speech_idx], axis=1)),
                                ("hierarchical_gate", p_b, gate.predict_proba(x_eval)[:, 1])):
        threshold, table, curve = threshold_table(y_cal, cal_p)
        decision = eval_p >= threshold
        # Both architectures use the speech subtype head; hierarchy gates expensive downstream work.
        reports[name] = {"threshold": threshold, "threshold_options_calibration": table,
                         "precision_recall_curve_calibration": curve,
                         "evaluation": metric([r["should_act"] for r in evaluation], decision,
                                              speech_true, speech_pred, action_true, action_pred, eval_p)}
    # Synthetic slot labels cover only seven slot families; report coverage rather than fabricating all requested scores.
    slot_counts = Counter(k for row in adv_no + adv_yes for k, v in row["slots"].items() if v is not None)
    slot_tp = Counter(); slot_fp = Counter(); slot_fn = Counter()
    exact = 0
    slot_rows = adv_no[1::2] + adv_yes[1::2]
    for row in slot_rows:
        gold = row["slots"]
        predicted = extract_slots(row["text"], row["previous_turns"])
        exact += all(predicted.get(k) == v for k, v in gold.items())
        for key, value in gold.items():
            guess = predicted.get(key)
            if guess == value and value is not None:
                slot_tp[key] += 1
            elif guess != value:
                if guess is not None:
                    slot_fp[key] += 1
                if value is not None:
                    slot_fn[key] += 1
    slot_scores = {}
    for key in SLOT_NAMES:
        support = slot_tp[key] + slot_fn[key]
        if not support:
            slot_scores[key] = {"gold_positive": 0, "precision": None, "recall": None, "f1": None}
            continue
        precision = slot_tp[key] / max(1, slot_tp[key] + slot_fp[key])
        recall = slot_tp[key] / support
        slot_scores[key] = {"gold_positive": support, "precision": precision, "recall": recall,
                            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    total_tp = sum(slot_tp.values()); total_fp = sum(slot_fp.values()); total_fn = sum(slot_fn.values())
    slot_precision = total_tp / max(1, total_tp + total_fp)
    slot_recall = total_tp / max(1, total_tp + total_fn)
    reference_rows = [row for row in slot_rows if row["slots"]["target"] == "context.selected_resource"]
    reference_accuracy = (sum(extract_slots(row["text"], row["previous_turns"])["target"] == "context.selected_resource" for row in reference_rows)
                          / len(reference_rows)) if reference_rows else None
    correction_rows = [row for row in slot_rows if row["speech_act"] == "CORRECTION"]
    correction_recipient_accuracy = (sum(extract_slots(row["text"], row["previous_turns"])["recipient"] == row["slots"]["recipient"] for row in correction_rows)
                                     / len(correction_rows)) if correction_rows else None
    # One representative of each split is used for per-request latency; no external capability is invoked.
    latency = []
    for row in evaluation[:300]:
        start = time.perf_counter()
        one = vectorizer.transform([input_text(row)])
        p = speech.predict_proba(one)
        if np.sum(p[:, speech_idx]) >= reports["shared_multitask"]["threshold"]:
            action.predict(one)
        latency.append((time.perf_counter() - start) * 1000)
    result = {"model": "word 1-3 gram shared TF-IDF; logistic heads", "train_rows": len(train),
              "calibration_rows": len(calibration), "evaluation_rows": len(evaluation),
              "train_speech_distribution": dict(class_counts), "speech_training_rows": len(train),
              "class_weights": "balanced speech and gate heads; action unweighted",
              "models": reports, "verb_sense": verb_sense,
              "reference_accuracy_on_synthetic_context": reference_accuracy,
              "correction_recipient_accuracy_on_synthetic_dev": correction_recipient_accuracy,
              "slot_gold_support": dict(slot_counts),
              "slot_probe": {"kind": "deterministic typed baseline, no learned slot model",
                             "evaluated_rows": len(slot_rows), "micro_precision": slot_precision,
                             "micro_recall": slot_recall,
                             "micro_f1": 2 * slot_precision * slot_recall / (slot_precision + slot_recall) if slot_precision + slot_recall else 0.0,
                             "exact_match": exact / len(slot_rows), "per_slot": slot_scores},
              "latency_ms": {k: float(np.percentile(latency, q)) for k, q in (("p50",50),("p95",95),("p99",99))},
              "training_seconds": time.perf_counter()-began, "test_used": False, "locked_holdout_used": False}
    MODEL.mkdir(parents=True, exist_ok=True)
    with (MODEL / "candidate_dev_only.pkl").open("wb") as stream:
        pickle.dump({"vectorizer": vectorizer, "speech": speech, "gate": gate, "action": action,
                     "thresholds": {k:v["threshold"] for k,v in reports.items()}}, stream)
    (OUT / "evaluation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"models": {k:v["evaluation"] for k,v in reports.items()},
                      "seconds": result["training_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
