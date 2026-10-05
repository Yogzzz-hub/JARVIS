"""Read-only actual-model holdout evaluation. No capability is executed."""
import asyncio
import json
import time
from pathlib import Path
import sys
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.core.capabilities.registry import CapabilityRegistry
from jarvis.core.context.models import BaseResourceRef, DraftResourceRef, ResultSet
from jarvis.core.llm.client import get_llm
from jarvis.core.router.ollama import OllamaProvider
from jarvis.memory.working_memory import WorkingMemory
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.whatsapp_intelligence import create_intelligence_tools


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default="jarvis/tests/fixtures/whatsapp_semantic_holdout.json")
    parser.add_argument("--output", default="reports/whatsapp_semantic_holdout_results.json")
    arguments = parser.parse_args()
    cases = json.loads((ROOT / arguments.fixture).read_text(encoding="utf-8"))
    registry = ToolRegistry()
    registry.discover(create_intelligence_tools())
    catalog = CapabilityRegistry(registry)
    from jarvis.core.capabilities.retrieval import CapabilityRetriever
    provider = OllamaProvider(tool_registry=registry, capability_registry=catalog,
        capability_retriever=CapabilityRetriever(catalog), client=get_llm(), timeout=12)
    output = {"evaluation":"actual configured fast model; no tools executed; first-run holdout",
        "fixture_size":len(cases), "representative_production_accuracy":False, "results":[]}
    destination = ROOT / arguments.output
    for number, case in enumerate(cases):
        memory = WorkingMemory()
        memory.context.whatsapp_thread = "919000000001@s.whatsapp.net"
        if case.get("draft"):
            memory.context.pending_draft = DraftResourceRef(draft_id="wa_holdout_draft", recipient=memory.context.whatsapp_thread,
                content="Could you clarify that?", metadata={"revision":2})
        if case.get("results"):
            memory.record_result_set(ResultSet(result_set_id="holdout", query="attachments", item_type="WHATSAPP_ATTACHMENT",
                resources=[BaseResourceRef(resource_id=f"att{n}", canonical_identifier=f"att{n}", resource_type="WHATSAPP_ATTACHMENT",
                    metadata={"thread_id":memory.context.whatsapp_thread, "kind":"ATTACHMENT"}) for n in (1, 2)]))
        provider.working_memory = memory
        started = time.perf_counter()
        decision = await provider.classify(case["text"], [], f"holdout{number}")
        row = {**case, "actual":decision.intent, "lane":decision.lane.value, "slots":decision.slots,
            "model":decision.model_used, "latency_ms":round((time.perf_counter()-started)*1000, 2),
            "correct":decision.intent is not None and decision.intent in {case["expected"], case.get("alternate")}}
        output["results"].append(row)
        destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(json.dumps({"case":number+1,"correct":row["correct"],"actual":row["actual"],"ms":row["latency_ms"]}), flush=True)
    output["accuracy"] = sum(row["correct"] for row in output["results"]) / len(cases)
    output["language_accuracy"] = {lang: sum(row["correct"] for row in output["results"] if row["language"]==lang)/sum(row["language"]==lang for row in output["results"]) for lang in ("ENGLISH","TANGLISH")}
    destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"accuracy":output["accuracy"],"language_accuracy":output["language_accuracy"]}), flush=True)
    await get_llm().aclose()


if __name__ == "__main__":
    asyncio.run(main())
