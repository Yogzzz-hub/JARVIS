"""Acquire pinned, licensed Tanglish source artifacts without altering raw bytes.

Run: python scripts/acquire_tanglish_data.py
The resulting audit is deliberately separate from SemanticFrame training labels.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import requests
import truststore
from huggingface_hub import HfApi, hf_hub_download


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "tanglish"
for part in ("raw", "interim", "processed", "generated", "splits", "manifests"):
    (BASE / part).mkdir(parents=True, exist_ok=True)

SOURCES = [
    {
        "name": "Aksharantar Tamil",
        "id": "aksharantar_tamil",
        "source": "https://huggingface.co/datasets/ai4bharat/Aksharantar",
        "repo": "ai4bharat/Aksharantar",
        "revision": "e418c1fc928d9f5393af33268472cf20c1891be8",
        "files": ["tam.zip", "README.md"],
        "license": "CC BY 4.0 (manual); CC0 1.0 (mined/existing packaging only); CC BY-SA 4.0 (Dakshina-origin rows)",
        "license_source": "https://indicnlp.ai4bharat.org/aksharantar/",
        "license_card": "cc",
        "purpose": "Tamil word transliteration and spelling normalization; no intent labels",
        "decision": "USE",
    },
    {
        "name": "DravidianCodeMix 2020",
        "id": "dravidiancodemix",
        "source": "https://zenodo.org/records/4750858",
        "revision": "Zenodo record 4750858, version 1.0, DOI 10.5281/zenodo.4750858",
        "files": ["DravidianCodeMix-2020.zip"],
        "license": "CC BY 4.0",
        "license_source": "https://zenodo.org/records/4750858",
        "purpose": "Natural public Tamil-English code-mixed text distribution; sentiment/offense labels kept separate",
        "decision": "AUXILIARY",
    },
    {
        "name": "TanglishSTS",
        "id": "tanglish_sts",
        "source": "https://huggingface.co/datasets/vishnu-n/TanglishSTS",
        "repo": "vishnu-n/TanglishSTS",
        "revision": "e25f8884a306ecb39dce27b62ab42efa334fe6ad",
        "files": ["tanglish_sts.jsonl", "README.md"],
        "license": "CC BY 4.0",
        "license_card": "cc-by-4.0",
        "license_source": "https://huggingface.co/datasets/vishnu-n/TanglishSTS",
        "purpose": "Held-out Tanglish sentence similarity evaluation only",
        "decision": "EVALUATION_ONLY",
    },
    {
        "name": "TamilTech-QA",
        "id": "tamiltech_qa",
        "source": "https://huggingface.co/datasets/dheepakkaran/TamilTech-QA",
        "repo": "dheepakkaran/TamilTech-QA",
        "revision": "a73e451b2e58bcae7ce0d2c553392ff84b6738ce",
        "files": [
            "data/train-00000-of-00001.parquet",
            "data/validation-00000-of-00001.parquet",
            "data/test-00000-of-00001.parquet",
            "README.md",
        ],
        "license": "CC BY 4.0 (publisher label; underlying public-comment rights not independently established)",
        "license_card": "cc-by-4.0",
        "license_source": "https://huggingface.co/datasets/dheepakkaran/TamilTech-QA",
        "purpose": "Audit Tamil technical QA register; quarantined from training pending provenance review",
        "decision": "EVALUATION_ONLY",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_zenodo(source: dict, dest: Path) -> None:
    record = requests.get("https://zenodo.org/api/records/4750858", timeout=60).json()
    if record["metadata"]["license"]["id"] != "cc-by-4.0":
        raise RuntimeError("Zenodo license changed; refusing download")
    file = next(item for item in record["files"] if item["key"] == dest.name)
    if dest.exists() and hashlib.md5(dest.read_bytes()).hexdigest() == file["checksum"].split(":")[-1]:
        return
    url = file["links"]["self"]
    temp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with temp.open("wb") as out:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    out.write(chunk)
    if hashlib.md5(temp.read_bytes()).hexdigest() != file["checksum"].split(":")[-1]:
        raise RuntimeError("Zenodo MD5 mismatch")
    temp.replace(dest)


def main() -> None:
    truststore.inject_into_ssl()
    api = HfApi()
    manifest = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "sources": []}
    for source in SOURCES:
        item = {key: value for key, value in source.items() if key not in {"repo", "license_card"}}
        item["download_timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        item["original_rows"] = None
        item["usable_rows"] = None
        item["transformations"] = []
        item["artifacts"] = []
        if "repo" in source:
            remote = api.dataset_info(source["repo"])
            if remote.sha != source["revision"] or remote.gated:
                raise RuntimeError(f"Revision changed or gated: {source['repo']}")
            if remote.cardData.get("license") != source["license_card"]:
                raise RuntimeError(f"License card changed: {source['repo']}")
        for filename in source["files"]:
            dest = BASE / "raw" / source["id"] / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            if "repo" in source:
                cached = Path(hf_hub_download(repo_id=source["repo"], filename=filename, repo_type="dataset", revision=source["revision"]))
                if not dest.exists() or sha256(dest) != sha256(cached):
                    shutil.copyfile(cached, dest)
            else:
                download_zenodo(source, dest)
            item["artifacts"].append({"path": str(dest.relative_to(ROOT)).replace("\\", "/"), "bytes": dest.stat().st_size, "sha256": sha256(dest)})
        manifest["sources"].append(item)
        print(f"Acquired {source['id']}: {len(item['artifacts'])} files", flush=True)
    (BASE / "dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
