import asyncio
import json
import sys

sys.path.insert(0, ".")
from tests.generalization.benchmark_runner import GeneralizationBenchmarkRunner

CAP_ALIASES = {
    "file.search": "file.find",
    "file.list": "file.list_directory",
    "file.organize": "file.organize_downloads",
    "system.volume_mute": "windows.volume_mute",
    "system.volume_unmute": "windows.volume_unmute",
    "system.volume_set": "windows.volume_set",
    "system.volume_up": "windows.volume_set",
    "system.volume_down": "windows.volume_set",
    "system.screenshot": "windows.screenshot",
    "system.info": "system.diagnostics",
    "system.time": "system.time",
    "news.search": "rag.search_news",
    "rss.latest": "rag.rss_latest",
    "knowledge.summarize": "rag.document_qa",
    "knowledge.retrieve": "rag.document_qa",
    "knowledge.qa": "rag.document_qa",
    "phone.transfer": "phone.send_file",
    "phone.screen_mirror": "phone.mirror_open",
}

async def main():
    runner = GeneralizationBenchmarkRunner("tests/generalization")
    records = []
    with open("tests/generalization/implicit.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    
    passed_count = 0
    for r in records:
        exp_caps = r.get("expected_capabilities", [])
        norm_caps = [CAP_ALIASES.get(c, c) for c in exp_caps]
        r_copy = dict(r)
        r_copy["expected_capabilities"] = norm_caps
        
        passed = await runner._evaluate_record(r_copy)
        if passed:
            passed_count += 1
            
    print(f"Implicit pass with capability normalization: {passed_count}/{len(records)} ({passed_count/len(records)*100:.1f}%)")

if __name__ == "__main__":
    asyncio.run(main())
