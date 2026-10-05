"""Audit and deduplicate acquired Tanglish data after license/source review."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "tanglish"
MANIFEST = BASE / "dataset_manifest.json"
TAMIL = re.compile(r"[\u0b80-\u0bff]")
LATIN = re.compile(r"[A-Za-z]")


def norm(value: str) -> str:
    return " ".join(value.casefold().split())


def file_record(path: Path) -> dict:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": h.hexdigest()}


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def aksharantar(item: dict) -> None:
    path = BASE / "raw/aksharantar_tamil/tam.zip"
    seen = set()
    stats = Counter()
    outputs = []
    with ZipFile(path) as archive:
        # Preserve publisher test/validation before train; prevent pair overlap leaking into train.
        for split in ("test", "valid", "train"):
            output = BASE / "processed" / "aksharantar_tamil" / f"{split}.jsonl"
            def rows():
                with archive.open(f"tam_{split}.json") as stream:
                    for line in stream:
                        stats["original"] += 1
                        stats[f"{split}_original"] += 1
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            stats["invalid_json"] += 1
                            continue
                        native, roman = str(row.get("native word") or "").strip(), str(row.get("english word") or "").strip()
                        if not native or not roman or not TAMIL.search(native) or not LATIN.search(roman):
                            stats["invalid_pair"] += 1
                            continue
                        key = (norm(native), norm(roman))
                        if key in seen:
                            stats["duplicates"] += 1
                            continue
                        seen.add(key)
                        origin = str(row.get("source") or "unknown")
                        stats[f"origin_{origin}"] += 1
                        license_permits_training = origin.casefold() == "dakshina" or origin.casefold().startswith("ak-")
                        license_tag = "CC BY-SA 4.0" if origin.casefold() == "dakshina" else ("CC BY 4.0" if origin.casefold().startswith("ak-") else "CC0 packaging only; underlying text rights unverified")
                        eligible = license_permits_training and split == "train"
                        if license_permits_training:
                            stats["license_permitted_rows"] += 1
                        if eligible:
                            stats["training_eligible"] += 1
                        yield {"native": native, "roman": roman, "source": origin, "source_id": row.get("unique_identifier"), "source_score": row.get("score"), "source_license": license_tag, "training_eligible": eligible, "publisher_split": split}
            n = write_jsonl(output, rows())
            stats[f"{split}_usable"] = n
            outputs.append(file_record(output) | {"rows": n})
    item["original_rows"] = stats["original"]
    item["usable_rows"] = sum(stats[f"{x}_usable"] for x in ("train", "valid", "test"))
    item["duplicate_rows"] = stats["duplicates"]
    item["duplicate_rate"] = round(stats["duplicates"] / stats["original"], 6)
    item["quality_counts"] = dict(stats)
    item["processed_artifacts"] = outputs
    item["transformations"] = ["Stream Tamil JSONL members from unchanged zip", "Validate nonempty Tamil-script native and Latin-script Roman form", "Deduplicate normalized native/Roman pairs across publisher splits, prioritizing test then valid then train", "Retain source, score, publisher split, and source-specific license tag", "Mark only publisher train rows from AK-* and Dakshina origins as training eligible; hold out publisher validation/test and quarantine mined sources because CC0 packaging does not prove upstream text rights"]


def dravidian(item: dict) -> None:
    path = BASE / "raw/dravidiancodemix/DravidianCodeMix-2020.zip"
    stats = Counter()
    by_text = {}
    with ZipFile(path) as archive:
        for name, task in (("tamil_sentiment_full.csv", "sentiment"), ("tamil_offensive_full.csv", "offensive")):
            with archive.open("DravidianCodeMix/" + name) as member:
                for row in csv.reader(io.TextIOWrapper(member, encoding="utf-8-sig", errors="replace"), delimiter="\t"):
                    stats["original"] += 1
                    if len(row) < 2:
                        stats["malformed"] += 1
                        continue
                    label, text = row[0].strip(), "\t".join(row[1:]).strip()
                    if not text or not LATIN.search(text) and not TAMIL.search(text):
                        stats["empty_or_nontext"] += 1
                        continue
                    key = norm(text)
                    if key in by_text:
                        stats["duplicates"] += 1
                        by_text[key]["source_labels"].append({"task": task, "label": label})
                    else:
                        by_text[key] = {"text": text, "source_labels": [{"task": task, "label": label}], "source_license": "CC BY 4.0", "source_id": "DravidianCodeMix-2020"}
                    stats[f"{task}_rows"] += 1
    output = BASE / "processed/dravidiancodemix/tamil_unique.jsonl"
    item["usable_rows"] = write_jsonl(output, by_text.values())
    item["original_rows"] = stats["original"]
    item["duplicate_rows"] = stats["duplicates"]
    item["duplicate_rate"] = round(stats["duplicates"] / stats["original"], 6)
    item["quality_counts"] = dict(stats)
    item["processed_artifacts"] = [file_record(output) | {"rows": item["usable_rows"]}]
    item["transformations"] = ["Read canonical full Tamil sentiment and offensive TSV members only; ignore split copies and other languages", "Validate nonempty text", "Deduplicate casefolded whitespace-normalized text across tasks", "Retain all source annotations as non-action labels"]


def sts(item: dict) -> None:
    path = BASE / "raw/tanglish_sts/tanglish_sts.jsonl"
    stats = Counter()
    seen = set()
    def rows():
        for line in path.open(encoding="utf-8"):
            stats["original"] += 1
            row = json.loads(line)
            a, b = str(row.get("s1") or "").strip(), str(row.get("s2") or "").strip()
            if not a or not b or not isinstance(row.get("human_score"), (int, float)):
                stats["invalid"] += 1
                continue
            key = tuple(sorted((norm(a), norm(b))))
            if key in seen:
                stats["duplicates"] += 1
                continue
            seen.add(key)
            yield {"text_a": a, "text_b": b, "human_score": row["human_score"], "source_license": "CC BY 4.0", "use": "evaluation_only"}
    output = BASE / "processed/tanglish_sts/pairs.jsonl"
    item["usable_rows"] = write_jsonl(output, rows())
    item["original_rows"] = stats["original"]
    item["duplicate_rows"] = stats["duplicates"]
    item["duplicate_rate"] = round(stats["duplicates"] / stats["original"], 6)
    item["quality_counts"] = dict(stats)
    item["processed_artifacts"] = [file_record(output) | {"rows": item["usable_rows"]}]
    item["transformations"] = ["Validate paired sentences and human score", "Deduplicate order-invariant normalized sentence pairs", "Retain only human score; mark evaluation only"]


def tamiltech(item: dict) -> None:
    stats = Counter()
    seen = set()
    outputs = []
    for split in ("test", "validation", "train"):
        path = BASE / "raw/tamiltech_qa/data" / f"{split}-00000-of-00001.parquet"
        table = pq.ParquetFile(path)
        output = BASE / "processed/tamiltech_qa" / f"{split}.jsonl"
        def rows():
            for batch in table.iter_batches(batch_size=2048):
                for row in batch.to_pylist():
                    stats["original"] += 1
                    q, a = str(row.get("question") or "").strip(), str(row.get("answer") or "").strip()
                    if not q or not a:
                        stats["invalid"] += 1
                        continue
                    key = (norm(q), norm(a))
                    if key in seen:
                        stats["duplicates"] += 1
                        continue
                    seen.add(key)
                    yield {"question": q, "answer": a, "topic": row.get("topic"), "source": row.get("source"), "publisher_split": split, "source_license": "CC BY 4.0 publisher label; upstream rights unverified", "use": "evaluation_only_quarantine"}
        n = write_jsonl(output, rows())
        stats[f"{split}_usable"] = n
        outputs.append(file_record(output) | {"rows": n})
    item["original_rows"] = stats["original"]
    item["usable_rows"] = sum(stats[f"{s}_usable"] for s in ("test", "validation", "train"))
    item["duplicate_rows"] = stats["duplicates"]
    item["duplicate_rate"] = round(stats["duplicates"] / stats["original"], 6)
    item["quality_counts"] = dict(stats)
    item["processed_artifacts"] = outputs
    item["transformations"] = ["Read publisher Parquet splits without modifying raw files", "Validate nonempty question and answer", "Deduplicate normalized QA pairs across splits, prioritizing test then validation then train", "Drop raw_text and chatml; retain only QA/topic/source in quarantined evaluation copies"]


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    handlers = {"aksharantar_tamil": aksharantar, "dravidiancodemix": dravidian, "tanglish_sts": sts, "tamiltech_qa": tamiltech}
    for item in manifest["sources"]:
        handlers[item["id"]](item)
        print(item["id"], item["original_rows"], item["usable_rows"], item["duplicate_rate"], flush=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Tanglish dataset manifest", "", "Acquired files are preserved byte-for-byte in `raw/`; processed copies are separate. No source labels are JARVIS SemanticFrame actions.", ""]
    for item in manifest["sources"]:
        lines += [f"## {item['name']}", "", f"- Source: {item['source']}", f"- Revision: `{item['revision']}`", f"- License: {item['license']} ([license evidence]({item['license_source']}))", f"- Downloaded UTC: {item['download_timestamp_utc']}", f"- Original rows: {item['original_rows']:,}; usable rows: {item['usable_rows']:,}; duplicate rate: {item['duplicate_rate']:.2%}", f"- Purpose: {item['purpose']}", f"- Decision: {item['decision']}", "- Raw SHA256:"]
        lines += [f"  - `{file['path']}` `{file['sha256']}`" for file in item["artifacts"]]
        lines += ["- Transformations:"] + [f"  - {change}" for change in item["transformations"]] + [""]
    (BASE / "DATASET_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
