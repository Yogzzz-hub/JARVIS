"""Alternative compact speech-act and action-gate baseline; no locked-set access."""

import json
import pickle
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.train_tanglish_semantic_stage2 import MODEL_DIR, input_text, read


def metrics(rows, vectorizer, gate, speech, threshold):
    x = vectorizer.transform(input_text(r) for r in rows)
    prob = gate.predict_proba(x)[:, 1]
    act = prob > threshold
    true = np.array([r["semantic_frame"]["should_act"] for r in rows])
    speech_scores = speech.predict_proba(x)
    classes = speech.classes_
    command_index = int(np.where(classes == "COMMAND")[0][0])
    speech_scores[~act, command_index] = -1
    predicted = classes[np.argmax(speech_scores, axis=1)]
    predicted[act] = "COMMAND"
    expected = np.array([r["semantic_frame"]["speech_act"] for r in rows])
    by_category = {}
    for category in sorted({r["category"] for r in rows}):
        idx = np.array([i for i, row in enumerate(rows) if row["category"] == category])
        by_category[category] = {"n": len(idx), "gate_accuracy": float(np.mean(act[idx] == true[idx])),
                                 "speech_accuracy": float(np.mean(predicted[idx] == expected[idx]))}
    by_language = {}
    for language in sorted({r["language"] for r in rows}):
        idx = np.array([i for i, row in enumerate(rows) if row["language"] == language])
        by_language[language] = {"n": len(idx), "gate_accuracy": float(np.mean(act[idx] == true[idx])),
                                 "speech_accuracy": float(np.mean(predicted[idx] == expected[idx]))}
    return {"rows": len(rows), "no_action_specificity": float(np.mean(~act[~true])),
            "false_action_rate": float(np.mean(act[~true])),
            "command_recall": float(np.mean(act[true])),
            "speech_act_accuracy": float(np.mean(predicted == expected)),
            "gate_accuracy": float(np.mean(act == true)),
            "negation_accuracy": float(np.mean(~act[[i for i,r in enumerate(rows) if r["category"] == "negation"]])),
            "correction_action_recall": float(np.mean(act[[i for i,r in enumerate(rows) if r["category"] == "correction"]])),
            "by_category": by_category, "by_language": by_language}


def main():
    started = time.perf_counter()
    train = list(read("train"))
    dev = list(read("dev"))
    test = list(read("test"))
    vectorizer = TfidfVectorizer(ngram_range=(1,3), min_df=2, max_features=100000,
                                sublinear_tf=True, token_pattern=r"(?u)\b\w+\b")
    x = vectorizer.fit_transform(input_text(r) for r in train)
    y_gate = np.array([int(r["semantic_frame"]["should_act"]) for r in train])
    y_speech = np.array([r["semantic_frame"]["speech_act"] for r in train])
    gate = LogisticRegression(C=2.0, class_weight="balanced", max_iter=250, solver="liblinear")
    gate.fit(x, y_gate)
    speech = LogisticRegression(C=2.0, class_weight="balanced", max_iter=250)
    speech.fit(x, y_speech)
    dev_x = vectorizer.transform(input_text(r) for r in dev)
    dev_prob = gate.predict_proba(dev_x)[:,1]
    negative = np.array([not r["semantic_frame"]["should_act"] for r in dev])
    threshold = float(np.quantile(dev_prob[negative], .99))
    result = {"architecture": "Word 1–3 gram TF-IDF with balanced logistic action gate and speech subtype head",
              "hyperparameters": {"max_features": 100000, "min_df": 2, "ngram_range": [1,3], "C": 2.0,
                                   "threshold_selection": "dev negative probability p99"},
              "vocabulary_size": len(vectorizer.vocabulary_), "threshold": threshold,
              "dev": metrics(dev, vectorizer, gate, speech, threshold),
              "test": metrics(test, vectorizer, gate, speech, threshold),
              "training_seconds_including_evaluation": time.perf_counter()-started,
              "locked_holdout_used": False}
    (BASE / "manifests/semantic_stage2_speech_alternative.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with (MODEL_DIR / "speech_alternative.pkl").open("wb") as stream:
        pickle.dump({"vectorizer": vectorizer, "gate": gate, "speech": speech, "threshold": threshold}, stream)
    print(json.dumps({"dev": {k:v for k,v in result["dev"].items() if k not in ("by_category","by_language")},
                      "test": {k:v for k,v in result["test"].items() if k not in ("by_category","by_language")},
                      "seconds": result["training_seconds_including_evaluation"]}, indent=2))


if __name__ == "__main__":
    main()
