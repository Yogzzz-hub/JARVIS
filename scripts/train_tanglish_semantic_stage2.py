"""Train and measure a compact shared-feature Stage-2 semantic baseline.

Only train/dev are opened. The locked holdout is never read here.
"""

from __future__ import annotations

import gzip
import json
import pickle
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier

from scripts.build_tanglish_semantic_stage2 import BASE, ONTOLOGY, OUT


MODEL_DIR = Path("models/tanglish_stage2")
CHECKPOINTS = (10000, 25000, 50000, 80000)


def read(split):
    with gzip.open(OUT / f"{split}.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def input_text(row):
    return " [TURN] ".join(row["previous_turns"][-2:] + [row["text"]])


def evaluate(vectorizer, action_head, speech_head, dev):
    start = time.perf_counter()
    matrix = vectorizer.transform(input_text(r) for r in dev)
    encode_seconds = time.perf_counter() - start
    start = time.perf_counter()
    actions = action_head.predict(matrix)
    speeches = speech_head.predict(matrix)
    decode_seconds = time.perf_counter() - start
    truth_action = np.array([r["semantic_frame"]["action_concept"] for r in dev])
    truth_speech = np.array([r["semantic_frame"]["speech_act"] for r in dev])
    no_action_true = np.array([not r["semantic_frame"]["should_act"] for r in dev])
    no_action_pred = speeches != "COMMAND"
    results = {"speech_act_accuracy": float(np.mean(speeches == truth_speech)),
               "action_concept_accuracy": float(np.mean(actions == truth_action)),
               "domain_accuracy_from_action": float(np.mean([ONTOLOGY[p][0] == r["semantic_frame"]["domain"] for p, r in zip(actions, dev)])),
               "no_action_specificity": float(np.mean(no_action_pred[no_action_true])),
               "false_action_rate": float(np.mean(~no_action_pred[no_action_true])),
               "exact_action_and_speech": float(np.mean((actions == truth_action) & (speeches == truth_speech))),
               "encode_ms_per_row_bulk": 1000 * encode_seconds / len(dev),
               "heads_ms_per_row_bulk": 1000 * decode_seconds / len(dev)}
    by_category = {}
    for category in sorted(set(r["category"] for r in dev)):
        idx = [i for i, row in enumerate(dev) if row["category"] == category]
        by_category[category] = {"n": len(idx), "action_accuracy": float(np.mean(actions[idx] == truth_action[idx])),
                                 "speech_accuracy": float(np.mean(speeches[idx] == truth_speech[idx]))}
    results["by_category"] = by_category
    by_language = {}
    for language in sorted(set(r["language"] for r in dev)):
        idx = [i for i, row in enumerate(dev) if row["language"] == language]
        by_language[language] = {"n": len(idx), "action_accuracy": float(np.mean(actions[idx] == truth_action[idx])),
                                 "speech_accuracy": float(np.mean(speeches[idx] == truth_speech[idx]))}
    results["by_language"] = by_language
    # Action-class retrieval over one shared representation, not capability-schema retrieval.
    decision = action_head.decision_function(matrix)
    class_idx = {name: i for i, name in enumerate(action_head.classes_)}
    ranks = np.argsort(-decision, axis=1)
    correct = np.array([class_idx[x] for x in truth_action])
    results["action_retrieval_recall_at_1"] = float(np.mean(ranks[:, :1] == correct[:, None]))
    results["action_retrieval_recall_at_3"] = float(np.mean(np.any(ranks[:, :3] == correct[:, None], axis=1)))
    results["action_retrieval_recall_at_5"] = float(np.mean(np.any(ranks[:, :5] == correct[:, None], axis=1)))
    positions = (ranks == correct[:, None]).argmax(axis=1) + 1
    results["action_retrieval_mrr"] = float(np.mean(1 / positions))
    ambiguous = ("anupu", "maathu", "kudu", "kaatu", "eduthu", "podu", "paaru")
    idx = [i for i, row in enumerate(dev) if any(v in row["text"].casefold() for v in ambiguous)]
    results["ambiguous_verb_action_accuracy"] = float(np.mean(actions[idx] == truth_action[idx])) if idx else None
    results["ambiguous_verb_examples"] = len(idx)
    return results


def latency(vectorizer, action_head, speech_head, dev):
    phases = defaultdict(list)
    for row in dev[:300]:
        t = time.perf_counter()
        value = input_text(row)
        phases["input"].append((time.perf_counter()-t)*1000)
        t = time.perf_counter()
        matrix = vectorizer.transform([value])
        phases["encoder"].append((time.perf_counter()-t)*1000)
        t = time.perf_counter()
        action_head.predict(matrix)
        speech_head.predict(matrix)
        phases["frame_decode"].append((time.perf_counter()-t)*1000)
    total = [sum(phases[k][i] for k in phases) for i in range(len(phases["input"]))]
    phases["total_semantic_only"] = total
    return {key: {"p50_ms": float(np.quantile(values, .5)), "p95_ms": float(np.quantile(values, .95)),
                  "p99_ms": float(np.quantile(values, .99))} for key, values in phases.items()}


def current_adapter_baseline(dev):
    from jarvis.core.general_language import GeneralLanguageUnderstandingEngine
    engine = GeneralLanguageUnderstandingEngine()
    mapped = {"CONVERT_FORMAT": "CONVERT", "REPLACE_ENTITY": "REPLACE", "SWITCH_RESOURCE": "SWITCH",
              "SET_VALUE": "SET", "CHECK_STATUS": "CHECK", "DRAFT_REPLY": "REPLY", "DISPLAY": "SHOW",
              "CAPTURE": "CREATE", "RETRIEVE": "FIND", "PROVIDE": "EXPLAIN"}
    action = speech = 0
    no_action = false_action = 0
    times = []
    for row in dev:
        context = row.get("context") or {}
        start = time.perf_counter()
        result = engine.understand(row["text"], context=context)
        times.append((time.perf_counter() - start) * 1000)
        target = row["semantic_frame"]
        action += mapped.get(result.action, result.action) == target["action_concept"]
        speech += result.speech_act == target["speech_act"]
        if not target["should_act"]:
            no_action += 1
            false_action += bool(result.actionable)
    return {"action_accuracy": action / len(dev), "speech_accuracy": speech / len(dev),
            "no_action_specificity": 1 - false_action / max(1, no_action),
            "p50_ms": float(np.quantile(times, .5)), "p95_ms": float(np.quantile(times, .95)),
            "note": "Adapter has a narrower action vocabulary and no supplied typed context; comparison is directional only."}


def main():
    start = time.perf_counter()
    dev = list(read("dev"))
    vectorizer = HashingVectorizer(analyzer="char", ngram_range=(2, 4), n_features=2**16,
                                  alternate_sign=False, norm="l2", lowercase=True)
    action_head = SGDClassifier(loss="modified_huber", alpha=2e-5, random_state=842, average=True)
    speech_head = SGDClassifier(loss="modified_huber", alpha=2e-5, random_state=843, average=True)
    action_classes = np.array(sorted(ONTOLOGY))
    speech_classes = np.array(sorted({"COMMAND", "PROHIBITION", "QUESTION", "STATEMENT", "HYPOTHETICAL", "DEFINITION", "AMBIGUOUS", "UNCERTAIN_ASR"}))
    report = {"architecture": "Shared 65,536-dimensional character 2–4 gram hashing encoder with two incremental linear heads; domain derived from ActionConcept",
              "hyperparameters": {"features": 65536, "ngram_range": [2,4], "loss": "modified_huber", "alpha": 2e-5, "average": True, "batch_size": 1000, "seed": 842},
              "train_rows": 80000, "dev_rows": len(dev), "checkpoints": {},
              "public_data_sampling_weight": 0.0, "semantic_generated_weight": 1.0,
              "limitations": ["No neural semantic embedding", "No learned slot head", "No capability retrieval, policy, or verified execution in this benchmark", "Synthetic labels are programmatic and not human adjudicated"]}
    report["current_adapter_baseline_dev"] = current_adapter_baseline(dev)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    batch = []
    trained = 0
    next_at = iter(CHECKPOINTS)
    checkpoint = next(next_at)
    for row in read("train"):
        batch.append(row)
        if len(batch) < 1000:
            continue
        matrix = vectorizer.transform(input_text(x) for x in batch)
        action_head.partial_fit(matrix, [x["semantic_frame"]["action_concept"] for x in batch], classes=action_classes)
        speech_head.partial_fit(matrix, [x["semantic_frame"]["speech_act"] for x in batch], classes=speech_classes)
        trained += len(batch)
        batch.clear()
        if trained == checkpoint:
            report["checkpoints"][str(trained)] = evaluate(vectorizer, action_head, speech_head, dev)
            print("checkpoint", trained, "action", report["checkpoints"][str(trained)]["action_concept_accuracy"], flush=True)
            checkpoint = next(next_at, -1)
    report["latency"] = latency(vectorizer, action_head, speech_head, dev)
    report["training_seconds_including_dev_evaluations"] = time.perf_counter()-start
    best = max(CHECKPOINTS, key=lambda n: report["checkpoints"][str(n)]["exact_action_and_speech"])
    report["best_dev_checkpoint"] = best
    report["selected_model_note"] = "Final 80k weights saved only if 80k is best; otherwise no selected checkpoint artifact."
    if best == 80000:
        with (MODEL_DIR / "model.pkl").open("wb") as stream:
            pickle.dump({"vectorizer": vectorizer, "action_head": action_head, "speech_head": speech_head}, stream)
    path = BASE / "manifests/semantic_stage2_training.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"best_dev_checkpoint": best, "training_seconds": report["training_seconds_including_dev_evaluations"]}, indent=2))


if __name__ == "__main__":
    main()
