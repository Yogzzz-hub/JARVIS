"""Download pinned, public MIT-licensed E5-small files for offline experiments."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import truststore
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "models/tanglish_stage24/encoders/multilingual-e5-small"
REPO = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


def main():
    truststore.inject_into_ssl()
    OUT.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=REPO, revision=REVISION, local_dir=OUT,
                      allow_patterns=["config.json", "model.safetensors", "tokenizer.json",
                                      "tokenizer_config.json", "special_tokens_map.json",
                                      "sentencepiece.bpe.model", "modules.json", "1_Pooling/*",
                                      "README.md"], max_workers=4)
    manifest={"repo":REPO,"revision":REVISION,"license":"MIT",
              "downloaded_utc":datetime.now(timezone.utc).isoformat(),"files":{}}
    for file in sorted(OUT.rglob("*")):
        if not file.is_file() or ".cache" in file.parts:
            continue
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        manifest["files"][file.relative_to(OUT).as_posix()]={"bytes":file.stat().st_size,"sha256":digest}
    (OUT/"stage24_model_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"files":len(manifest["files"]),"bytes":sum(x["bytes"] for x in manifest["files"].values())}))


if __name__ == "__main__":
    main()
