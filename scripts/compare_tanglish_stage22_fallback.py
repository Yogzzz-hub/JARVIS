"""One controlled word+character fallback comparison on Stage 2.2 dev only."""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.build_tanglish_stage21_repair import OUT as S21
from scripts.evaluate_tanglish_stage21 import input_text, legacy, read
from scripts.evaluate_tanglish_stage22 import (dev_partition, fast_thresholds, rates,
                                                route, select_semantic_thresholds, apply_negation_guard)

ROOT = Path(__file__).resolve().parents[1]
OUT = BASE / "generated/stage22"


def main():
    with (ROOT / "models/tanglish_stage21/candidate_dev_only.pkl").open("rb") as stream:
        old = pickle.load(stream)
    train = [legacy(r) for r in read(BASE / "generated/semantic_stage2/train.jsonl.gz")]
    train += read(S21 / "train.jsonl.gz")
    dev = [legacy(r) for r in read(BASE / "generated/semantic_stage2/dev.jsonl.gz")]
    dev += read(S21 / "dev_no_action.jsonl.gz") + read(S21 / "dev_command.jsonl.gz")
    cal = [r for r in dev if dev_partition(r) == 0]
    evaluation = [r for r in dev if dev_partition(r) == 1]
    char = TfidfVectorizer(analyzer="char", ngram_range=(2,4), min_df=3,
                           max_features=100000, sublinear_tf=True)
    train_text = [input_text(r) for r in train]
    cal_text = [input_text(r) for r in cal]
    eval_text = [input_text(r) for r in evaluation]
    x_char = char.fit_transform(train_text)
    x = hstack((old["vectorizer"].transform(train_text), x_char), format="csr")
    xc = hstack((old["vectorizer"].transform(cal_text), char.transform(cal_text)), format="csr")
    xe = hstack((old["vectorizer"].transform(eval_text), char.transform(eval_text)), format="csr")
    model = SGDClassifier(loss="log_loss", alpha=0.00001, max_iter=25,
                          class_weight="balanced", random_state=2210)
    model.fit(x, np.array([int(r["should_act"]) for r in train]))
    fast_cal = old["gate"].predict_proba(old["vectorizer"].transform(cal_text))[:,1]
    fast_eval = old["gate"].predict_proba(old["vectorizer"].transform(eval_text))[:,1]
    sem_cal = model.predict_proba(xc)[:,1]
    sem_eval = model.predict_proba(xe)[:,1]
    yc = np.array([r["should_act"] for r in cal], dtype=bool)
    ye = np.array([r["should_act"] for r in evaluation], dtype=bool)
    t_no, t_ex = fast_thresholds(yc, fast_cal)
    t_sem_no, t_sem_ex = select_semantic_thresholds(yc, fast_cal, sem_cal, t_no, t_ex, cal)
    report = {"representation":"shared word 1-3 gram plus char 2-4 gram TF-IDF; linear fallback head",
              "train_rows":len(train),"dev_calibration":len(cal),"dev_evaluation":len(evaluation),
              "thresholds":{"t_no_action":t_no,"t_execute":t_ex,
                            "t_semantic_no_action":t_sem_no,"t_semantic_execute":t_sem_ex},
              "calibration":rates(yc,apply_negation_guard(route(fast_cal,sem_cal,t_no,t_ex,t_sem_no,t_sem_ex),cal)),
              "evaluation":rates(ye,apply_negation_guard(route(fast_eval,sem_eval,t_no,t_ex,t_sem_no,t_sem_ex),evaluation)),
              "test_opened":False,"sealed_holdout_opened":False}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"fallback_comparison.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["evaluation"],indent=2))


if __name__ == "__main__":
    main()
