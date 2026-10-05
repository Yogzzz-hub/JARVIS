"""Evaluate the selected Stage-2 action/speech model on test, never locked holdout."""

import json
import pickle

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.train_tanglish_semantic_stage2 import MODEL_DIR, evaluate, read


with (MODEL_DIR / "model.pkl").open("rb") as stream:
    model = pickle.load(stream)
result = evaluate(model["vectorizer"], model["action_head"], model["speech_head"], list(read("test")))
(BASE / "manifests/semantic_stage2_raw_test.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print({key: value for key, value in result.items() if key not in ("by_category", "by_language")})
