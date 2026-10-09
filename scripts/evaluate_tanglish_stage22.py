"""Development-only tri-state actionability experiment; no tools are invoked."""
from __future__ import annotations

import hashlib
import json
import pickle
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from scipy.sparse import hstack

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.build_tanglish_stage21_repair import HIGH_RISK, OUT as S21
from scripts.evaluate_tanglish_stage21 import input_text, legacy, read

ROOT = Path(__file__).resolve().parents[1]
OUT = BASE / "generated/stage22"
MODEL = ROOT / "models/tanglish_stage21/candidate_dev_only.pkl"


def dev_partition(row):
    key = row.get("pair_family", row.get("id", input_text(row)))
    return int(hashlib.sha256(key.encode()).hexdigest(), 16) % 2


def rates(y, decision):
    y = np.asarray(y, dtype=bool)
    decision = np.asarray(decision)
    act = decision == "EXECUTE_CANDIDATE"
    no = decision == "NO_ACTION"
    uncertain = decision == "UNCERTAIN"
    tp = int(np.sum(act & y)); fp = int(np.sum(act & ~y))
    return {"rows": len(y), "tp": tp, "fp": fp, "fn": int(np.sum(~act & y)),
            "tn": int(np.sum(~act & ~y)),
            "action_trigger_precision": tp / (tp + fp) if tp + fp else None,
            "candidate_command_recall": tp / max(1, int(np.sum(y))),
            "false_action_rate": fp / max(1, int(np.sum(~y))),
            "false_no_action_rate_on_commands": float(np.mean(no[y])) if np.any(y) else None,
            "uncertain_rate": float(np.mean(uncertain)),
            "fast_coverage": float(np.mean(~uncertain))}


def fast_thresholds(y, p):
    # Select two boundaries on calibration only; commands sent to UNCERTAIN remain recoverable.
    no_candidates = np.unique(np.quantile(p, np.linspace(0, .6, 301)))
    safe_no = [t for t in no_candidates if np.mean(p[y] <= t) <= .005]
    t_no = float(max(safe_no)) if safe_no else 0.0
    ex_candidates = np.unique(np.quantile(p, np.linspace(.4, 1, 501)))
    safe_ex = []
    for t in ex_candidates:
        m = p >= t
        if not np.any(m):
            continue
        precision = np.mean(y[m])
        far = np.mean(m[~y])
        if precision >= .995 and far < .002:
            safe_ex.append(t)
    t_ex = float(min(safe_ex)) if safe_ex else 1.0
    return t_no, t_ex


def route(fast, semantic, t_no, t_ex, t_sem_no, t_sem_ex):
    state = np.full(len(fast), "UNCERTAIN", dtype="<U18")
    state[fast <= t_no] = "NO_ACTION"
    state[fast >= t_ex] = "EXECUTE_CANDIDATE"
    uncertain = state == "UNCERTAIN"
    state[uncertain & (semantic <= t_sem_no)] = "NO_ACTION"
    state[uncertain & (semantic >= t_sem_ex)] = "EXECUTE_CANDIDATE"
    return state


def command_negated(text):
    """Conservative full-action prohibition cue; object exclusions stay in the frame."""
    low = text.casefold()
    return bool(re.search(r"\b(?:panna\s+venam|panna\s+venda|pannadha|pannadhinga|don't\s+\w+|do\s+not\s+\w+)\b", low))


def apply_negation_guard(state, rows):
    guarded = state.copy()
    for index, row in enumerate(rows):
        if command_negated(row["text"]):
            guarded[index] = "NO_ACTION"
    return guarded


def select_semantic_thresholds(y, fast, semantic, t_no, t_ex, rows):
    uncertain = (fast > t_no) & (fast < t_ex)
    # Avoid silently turning real commands into NO_ACTION. Remaining cases clarify.
    vals = semantic[uncertain]
    labels = y[uncertain]
    q_no = np.unique(np.quantile(vals, np.linspace(0, .5, 201)))
    safe_no = [t for t in q_no if np.mean(vals[labels] <= t) <= .005]
    t_sem_no = float(max(safe_no)) if safe_no else 0.0
    q_ex = np.unique(np.quantile(vals, np.linspace(.3, 1, 501)))
    best = None
    for t in q_ex:
        state = apply_negation_guard(route(fast, semantic, t_no, t_ex, t_sem_no, float(t)), rows)
        metric = rates(y, state)
        if metric["action_trigger_precision"] is not None and metric["action_trigger_precision"] >= .99 and metric["false_action_rate"] < .005:
            if best is None or metric["candidate_command_recall"] > best[1]:
                best = (float(t), metric["candidate_command_recall"])
    return t_sem_no, best[0] if best else 1.0


def sample_latency(rows, word, gate, char, semantic, action, thresholds):
    phases = defaultdict(list)
    for row in rows[:250]:
        a = time.perf_counter()
        value = input_text(row)
        b = time.perf_counter()
        word_x = word.transform([value]); c = time.perf_counter()
        fast_p = gate.predict_proba(word_x)[0, 1]; d = time.perf_counter()
        char_p = None
        if thresholds[0] < fast_p < thresholds[1]:
            char_x = char.transform([value]); char_p = semantic.predict_proba(hstack((word_x, char_x), format="csr"))[0, 1]
        e = time.perf_counter()
        if fast_p >= thresholds[1] or char_p is not None and char_p >= thresholds[3]:
            action.predict(word_x)
        f = time.perf_counter()
        for key, start, end in (("input",a,b),("word_encoder",b,c),("fast_gate",c,d),
                                ("semantic_fallback",d,e),("action_head",e,f),("total",a,f)):
            phases[key].append((end-start)*1000)
    return {key: {label: float(np.percentile(values, q)) for label, q in (("p50",50),("p95",95),("p99",99))}
            for key, values in phases.items()}


def main():
    started = time.perf_counter()
    with MODEL.open("rb") as stream:
        old = pickle.load(stream)
    train = [legacy(r) for r in read(BASE / "generated/semantic_stage2/train.jsonl.gz")]
    train += read(S21 / "train.jsonl.gz")
    dev = [legacy(r) for r in read(BASE / "generated/semantic_stage2/dev.jsonl.gz")]
    dev += read(S21 / "dev_no_action.jsonl.gz") + read(S21 / "dev_command.jsonl.gz")
    cal = [r for r in dev if dev_partition(r) == 0]
    evaluation = [r for r in dev if dev_partition(r) == 1]
    char = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), min_df=3,
                           max_features=100000, sublinear_tf=True)
    train_text = [input_text(r) for r in train]
    cal_text = [input_text(r) for r in cal]
    eval_text = [input_text(r) for r in evaluation]
    train_char = char.fit_transform(train_text)
    model = SGDClassifier(loss="log_loss", alpha=0.00001, max_iter=25,
                          class_weight="balanced", random_state=2210)
    model.fit(hstack((old["vectorizer"].transform(train_text), train_char), format="csr"),
              np.array([int(r["should_act"]) for r in train]))
    word_cal = old["vectorizer"].transform(cal_text)
    word_eval = old["vectorizer"].transform(eval_text)
    fast_cal = old["gate"].predict_proba(word_cal)[:,1]
    fast_eval = old["gate"].predict_proba(word_eval)[:,1]
    speech_pred = old["speech"].predict(word_eval)
    action_pred = old["action"].predict(word_eval)
    speech_gold = np.array([r["speech_act"] for r in evaluation])
    action_gold = np.array([r["action_concept"] for r in evaluation])
    sem_cal = model.predict_proba(hstack((word_cal, char.transform(cal_text)), format="csr"))[:,1]
    sem_eval = model.predict_proba(hstack((word_eval, char.transform(eval_text)), format="csr"))[:,1]
    y_cal = np.array([r["should_act"] for r in cal], dtype=bool)
    y_eval = np.array([r["should_act"] for r in evaluation], dtype=bool)
    t_no, t_ex = fast_thresholds(y_cal, fast_cal)
    t_sem_no, t_sem_ex = select_semantic_thresholds(y_cal, fast_cal, sem_cal, t_no, t_ex, cal)
    fast_state = apply_negation_guard(route(fast_eval, sem_eval, t_no, t_ex, -1, 2), evaluation)
    final_state = apply_negation_guard(route(fast_eval, sem_eval, t_no, t_ex, t_sem_no, t_sem_ex), evaluation)
    result = {"calibration_rows": len(cal), "evaluation_rows": len(evaluation),
              "thresholds": {"t_no_action": t_no, "t_execute": t_ex,
                             "t_semantic_no_action": t_sem_no, "t_semantic_execute": t_sem_ex},
              "fast": rates(y_eval, fast_state), "final": rates(y_eval, final_state),
              "semantic_escalation_rate": float(np.mean(fast_state == "UNCERTAIN")),
              "planner_or_clarification_rate": float(np.mean(final_state == "UNCERTAIN")),
              "speech_act_accuracy": float(np.mean(speech_pred == speech_gold)),
              "action_concept_accuracy": float(np.mean(action_pred == action_gold)),
              "negated_command_recognition": float(np.mean(speech_pred[speech_gold == "NEGATED_COMMAND"] == "NEGATED_COMMAND")),
              "calibration": rates(y_cal, apply_negation_guard(route(fast_cal, sem_cal, t_no, t_ex, t_sem_no, t_sem_ex), cal)),
              "explicit_negation_guard_accuracy": float(np.mean(final_state[[i for i,r in enumerate(evaluation) if r["speech_act"] == "NEGATED_COMMAND"]] == "NO_ACTION")),
              "risk_false_action": {}, "language": {}, "category": {},
              "latency_ms": sample_latency(evaluation, old["vectorizer"], old["gate"], char, model, old["action"],
                                           (t_no,t_ex,t_sem_no,t_sem_ex)),
              "training_seconds": time.perf_counter()-started,
              "test_opened": False, "sealed_holdout_opened": False, "production_connected": False}
    def risk_class(action):
        if action in {"DELETE", "UNINSTALL"}:
            return "DESTRUCTIVE"
        if action in {"INSTALL", "ENTER"}:
            return "PRIVILEGED"
        if action in {"SEND", "SHARE", "FORWARD", "REPLY", "CALL", "SUBMIT", "UPLOAD", "PAY"}:
            return "EXTERNAL_EFFECT"
        if action in {"READ", "SHOW", "LIST", "SEARCH", "FIND", "INSPECT", "CHECK", "VERIFY", "SUMMARIZE", "EXPLAIN"}:
            return "READ_ONLY"
        return "REVERSIBLE"
    risk = np.array([risk_class(r["action_concept"]) for r in evaluation])
    for name in sorted(set(risk)):
        mask = risk == name
        r = rates(y_eval[mask], final_state[mask])
        result["risk_false_action"][name] = {"rows": r["rows"], "false_action_rate":r["false_action_rate"],
                                               "tp":r["tp"],"fp":r["fp"]}
    for name in sorted(set(r.get("language", "unknown") for r in evaluation)):
        mask = np.array([r.get("language", "unknown") == name for r in evaluation])
        result["language"][name] = rates(y_eval[mask], final_state[mask])
        result["language"][name]["speech_act_accuracy"] = float(np.mean(speech_pred[mask] == speech_gold[mask]))
        result["language"][name]["action_concept_accuracy"] = float(np.mean(action_pred[mask] == action_gold[mask]))
    for name in sorted(set(r.get("category", "repair") for r in evaluation)):
        mask = np.array([r.get("category", "repair") == name for r in evaluation])
        result["category"][name] = rates(y_eval[mask], final_state[mask])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tri_state_dev.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with (OUT / "semantic_fallback.pkl").open("wb") as stream:
        pickle.dump({"encoder": char, "head": model, "thresholds": result["thresholds"]}, stream)
    print(json.dumps({k: result[k] for k in ("thresholds","fast","final","semantic_escalation_rate","planner_or_clarification_rate")}, indent=2))


if __name__ == "__main__":
    main()
