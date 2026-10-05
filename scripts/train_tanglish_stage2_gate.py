"""Fit a conservative action gate and evaluate on the untouched test split.

The locked holdout is never opened. No external capability can be invoked here.
"""

import json
import pickle
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import SGDClassifier

from scripts.build_tanglish_semantic_stage2 import BASE, ONTOLOGY
from scripts.train_tanglish_semantic_stage2 import MODEL_DIR, input_text, read


def measure(split, vectorizer, action_head, speech_head, gate, threshold):
    rows = list(read(split))
    matrix = vectorizer.transform(input_text(r) for r in rows)
    scores = gate.decision_function(matrix)
    act = scores > threshold
    truth_act = np.array([r["semantic_frame"]["should_act"] for r in rows])
    actions = action_head.predict(matrix)
    truth_action = np.array([r["semantic_frame"]["action_concept"] for r in rows])
    speech_scores = speech_head.decision_function(matrix)
    speech_classes = speech_head.classes_
    command = int(np.where(speech_classes == "COMMAND")[0][0])
    speech_scores[~act, command] = -np.inf
    speeches = speech_classes[np.argmax(speech_scores, axis=1)]
    speeches[act] = "COMMAND"
    truth_speech = np.array([r["semantic_frame"]["speech_act"] for r in rows])
    by_category = {}
    for category in sorted(set(r["category"] for r in rows)):
        idx = np.array([i for i, row in enumerate(rows) if row["category"] == category])
        by_category[category] = {"n": len(idx), "action_accuracy": float(np.mean(actions[idx] == truth_action[idx])),
                                 "gate_accuracy": float(np.mean(act[idx] == truth_act[idx])),
                                 "speech_accuracy": float(np.mean(speeches[idx] == truth_speech[idx]))}
    by_language = {}
    for language in sorted(set(r["language"] for r in rows)):
        idx = np.array([i for i, row in enumerate(rows) if row["language"] == language])
        by_language[language] = {"n": len(idx), "action_accuracy": float(np.mean(actions[idx] == truth_action[idx])),
                                 "gate_accuracy": float(np.mean(act[idx] == truth_act[idx])),
                                 "speech_accuracy": float(np.mean(speeches[idx] == truth_speech[idx]))}
    ambiguous = ("anupu", "maathu", "kudu", "kaatu", "eduthu", "podu", "paaru")
    verb_idx = np.array([i for i, row in enumerate(rows) if any(v in row["text"].casefold() for v in ambiguous)])
    action_scores = action_head.decision_function(matrix)
    ranks = np.argsort(-action_scores, axis=1)
    class_index = {name: i for i, name in enumerate(action_head.classes_)}
    correct = np.array([class_index[name] for name in truth_action])
    return {"rows": len(rows), "threshold": float(threshold),
            "no_action_specificity": float(np.mean(~act[~truth_act])),
            "false_action_rate": float(np.mean(act[~truth_act])),
            "action_request_recall": float(np.mean(act[truth_act])),
            "speech_act_accuracy": float(np.mean(speeches == truth_speech)),
            "action_concept_accuracy": float(np.mean(actions == truth_action)),
            "domain_accuracy_from_action": float(np.mean([ONTOLOGY[name][0] == row["semantic_frame"]["domain"] for name, row in zip(actions, rows)])),
            "ambiguous_verb_action_accuracy": float(np.mean(actions[verb_idx] == truth_action[verb_idx])) if len(verb_idx) else None,
            "ambiguous_verb_examples": len(verb_idx),
            "action_retrieval_recall_at_1": float(np.mean(ranks[:, :1] == correct[:, None])),
            "action_retrieval_recall_at_3": float(np.mean(np.any(ranks[:, :3] == correct[:, None], axis=1))),
            "action_retrieval_recall_at_5": float(np.mean(np.any(ranks[:, :5] == correct[:, None], axis=1))),
            "action_retrieval_mrr": float(np.mean(1 / ((ranks == correct[:, None]).argmax(axis=1) + 1))),
            "exact_action_speech_gate": float(np.mean((actions == truth_action) & (speeches == truth_speech) & (act == truth_act))),
            "by_category": by_category, "by_language": by_language}


def main():
    with (MODEL_DIR / "model.pkl").open("rb") as stream:
        model = pickle.load(stream)
    vectorizer = model["vectorizer"]
    gate = SGDClassifier(loss="modified_huber", alpha=2e-5, random_state=844, average=True)
    batch = []
    started = time.perf_counter()
    for row in read("train"):
        batch.append(row)
        if len(batch) < 1000:
            continue
        matrix = vectorizer.transform(input_text(r) for r in batch)
        labels = np.array([int(r["semantic_frame"]["should_act"]) for r in batch])
        weights = np.where(labels == 0, 5.0, 1.0)
        gate.partial_fit(matrix, labels, classes=np.array([0, 1]), sample_weight=weights)
        batch.clear()
    dev = list(read("dev"))
    dev_matrix = vectorizer.transform(input_text(r) for r in dev)
    dev_scores = gate.decision_function(dev_matrix)
    neg = np.array([not r["semantic_frame"]["should_act"] for r in dev])
    # Select a conservative threshold using dev only. 99% specificity is the
    # minimum allowed here; this is then measured independently on test.
    threshold = float(np.quantile(dev_scores[neg], .99))
    results = {"architecture": "Shared character encoder plus weighted binary action gate; subtype speech head used only after gate",
               "hyperparameters": {"loss": "modified_huber", "alpha": 2e-5, "negative_sample_weight": 5.0,
                                    "threshold_selection": "dev negative-score p99"},
               "training_seconds": time.perf_counter()-started,
               "dev": measure("dev", vectorizer, model["action_head"], model["speech_head"], gate, threshold),
               "test": measure("test", vectorizer, model["action_head"], model["speech_head"], gate, threshold),
               "locked_holdout_used": False}
    with (MODEL_DIR / "action_gate.pkl").open("wb") as stream:
        pickle.dump({"gate": gate, "threshold": threshold}, stream)
    (BASE / "manifests/semantic_stage2_gate.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dev": {k: v for k, v in results["dev"].items() if k != "by_category"},
                      "test": {k: v for k, v in results["test"].items() if k != "by_category"}}, indent=2))


if __name__ == "__main__":
    main()
