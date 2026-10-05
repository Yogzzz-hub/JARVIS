"""Read-only semantic-frame evaluation; never executes a capability."""
from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from jarvis.core.general_language import GeneralLanguageUnderstandingEngine


def evaluate(path: Path) -> dict:
    engine = GeneralLanguageUnderstandingEngine()
    counts = Counter()
    confusions = Counter()
    by_action = defaultdict(Counter)
    examples = []
    polysemous = re.compile(r"\b(?:maathu|mathu|matu|kudu|kodu|eduthu|edu|podu|paaru|paru|sollu|vai|vaangu)\b", re.I)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            gold = row["frame"]
            pred = engine.understand(row["text"], row.get("context"))
            got_action = pred.action if pred.speech_act == "COMMAND" else None
            expected_action = gold["action"]
            counts["total"] += 1
            counts["speech_correct"] += pred.speech_act == gold["speech_act"]
            counts["action_correct"] += got_action == expected_action
            counts["target_correct"] += pred.target_type == gold["target_type"]
            counts["recipient_correct"] += (pred.recipient or None) == (gold["recipient"] or None)
            counts["channel_correct"] += (pred.channel or None) == (gold["channel"] or None)
            if gold["speech_act"] == "PROHIBITION":
                counts["prohibition_cases"] += 1
                counts["prohibition_correct"] += pred.speech_act == "PROHIBITION"
            if row.get("previous_turns"):
                counts["context_cases"] += 1
                counts["context_target_correct"] += pred.target_type == gold["target_type"]
            if polysemous.search(row["text"]):
                counts["polysemous_cases"] += 1
                counts["polysemous_action_correct"] += got_action == expected_action
            expected_exclusions = ["screenshot"] if "screenshot venam" in row["text"].casefold() else []
            if expected_exclusions:
                counts["exclusion_cases"] += 1
                counts["exclusion_correct"] += set(expected_exclusions) <= set(pred.exclusions)
            for slot in ("target_type", "recipient", "channel", "selector"):
                truth = gold.get(slot)
                guess = getattr(pred, slot)
                if truth is not None:
                    counts["gold_slots"] += 1
                if guess is not None:
                    counts["predicted_slots"] += 1
                if truth is not None and guess is not None and str(truth).casefold() == str(guess).casefold():
                    counts["correct_slots"] += 1
            if expected_action is None:
                counts["no_action"] += 1
                counts["false_action"] += got_action is not None
            else:
                counts["action_cases"] += 1
                counts["triggered"] += got_action is not None
                counts["action_true_positive"] += got_action == expected_action
            by_action[expected_action or "NO_ACTION"]["total"] += 1
            by_action[expected_action or "NO_ACTION"]["correct"] += got_action == expected_action
            if got_action != expected_action:
                confusions[f"{expected_action or 'NO_ACTION'} -> {got_action or 'NO_ACTION'}"] += 1
                if len(examples) < 100:
                    examples.append({"text": row["text"], "previous_turns": row.get("previous_turns", []),
                                     "expected": gold, "predicted": pred.asdict()})
    total = counts["total"] or 1
    precision = counts["correct_slots"] / max(1, counts["predicted_slots"])
    recall = counts["correct_slots"] / max(1, counts["gold_slots"])
    report = {"file": str(path), "counts": dict(counts),
              "metrics": {"speech_accuracy": counts["speech_correct"] / total,
                          "semantic_action_accuracy": counts["action_correct"] / total,
                          "target_accuracy": counts["target_correct"] / total,
                          "recipient_accuracy": counts["recipient_correct"] / total,
                          "channel_accuracy": counts["channel_correct"] / total,
                          "no_action_specificity": 1 - counts["false_action"] / max(1, counts["no_action"]),
                          "false_action_rate": counts["false_action"] / max(1, counts["no_action"]),
                          "slot_precision": precision, "slot_recall": recall,
                          "slot_f1": 2 * precision * recall / max(1e-9, precision + recall),
                          "prohibition_accuracy": counts["prohibition_correct"] / max(1, counts["prohibition_cases"]),
                          "context_target_accuracy": counts["context_target_correct"] / max(1, counts["context_cases"]),
                          "verb_sense_accuracy": counts["polysemous_action_correct"] / max(1, counts["polysemous_cases"]),
                          "explicit_exclusion_accuracy": counts["exclusion_correct"] / max(1, counts["exclusion_cases"]),
                          "action_trigger_precision": counts["action_true_positive"] /
                            max(1, counts["triggered"] + counts["false_action"])},
              "by_action": {k: dict(v) for k, v in by_action.items()},
              "top_confusions": confusions.most_common(30), "failure_examples": examples,
              "limitations": "Synthetic grammar benchmark; no end-to-end capability, policy, execution or human-label accuracy claim."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("jarvis/tests/fixtures/tanglish_corpus/locked_holdout_v6.jsonl.gz"))
    parser.add_argument("--output", type=Path, default=Path("reports/tanglish_holdout_results.json"))
    args = parser.parse_args()
    report = evaluate(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "metrics": report["metrics"],
                      "top_confusions": report["top_confusions"][:10]}, indent=2))
