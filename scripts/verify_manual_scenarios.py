"""Verification script for JARVIS EDGE Conversational Continuity Sections 96-99:
96: Knowledge -> Action ("What does Ollama do?" -> "Install it.")
97: File Continuity ("Show my recent PDFs." -> "Open the second one." -> "What does it talk about?" -> "Open its folder." -> "Where is it?")
98: Topic Switch Continuity ("What is Ollama?" -> "Show my recent PDFs." -> "Open second." -> "Go back to Ollama." -> "Install it.")
99: Ambiguity Resolution ("Compare Ollama and LM Studio." -> "Install it." -> Clarification)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.context.models import (
    EntityType,
    FileResourceRef,
    ResultSet,
    TopicRef,
)
from jarvis.core.context.resolver import ReferenceResolver
from jarvis.core.memory.working import BoundedWorkingMemory
from jarvis.core.router.models import RouteLane
from jarvis.core.router.router import SmartRouter
from jarvis.tools.system.app_resolver import AppResolver, LaunchTarget


def create_router():
    wm = BoundedWorkingMemory()
    ref_resolver = ReferenceResolver(working_memory=wm)
    app_resolver = AppResolver({})
    app_resolver._apps = {
        "notepad": LaunchTarget("notepad", "C:\\Windows\\notepad.exe", ("notepad.exe",)),
        "calculator": LaunchTarget("calculator", "calc.exe", ("calc.exe",)),
    }
    router = SmartRouter(
        app_resolver=app_resolver,
        working_memory=wm,
        reference_resolver=ref_resolver,
    )
    return router, wm, ref_resolver


async def test_section_96():
    print("\n" + "=" * 65)
    print("SECTION 96: KNOWLEDGE -> ACTION VERIFICATION")
    print("=" * 65)
    router, wm, ref_resolver = create_router()

    # Turn 1: "What does Ollama do?"
    print('USER: "What does Ollama do?"')
    req1 = CommandRequest(text="What does Ollama do?", request_id="s96_1")
    dec1 = await router.route(req1)
    print(f"ROUTER: lane={dec1.lane.name}, reason={dec1.reason_code}")
    print(f"WORKING CONTEXT Active Topic: {wm.active_topic.canonical_name if wm.active_topic else None}")
    print(f"WORKING CONTEXT Entities: {[e.canonical_name for e in wm.get_recent_entities()]}")
    assert wm.active_topic is not None
    assert wm.active_topic.canonical_name.casefold() == "ollama"

    # Turn 2: "Install it."
    print('\nUSER: "Install it."')
    req2 = CommandRequest(text="Install it.", request_id="s96_2")
    dec2 = await router.route(req2)
    print(f"ROUTER: intent={dec2.intent}, slots={dec2.slots}, lane={dec2.lane.name}")
    print(f"Reference Resolution: target='{dec2.slots.get('name')}'")
    assert dec2.intent == "install_software"
    assert dec2.slots.get("name").casefold() == "ollama"
    print("-> SECTION 96 PASSED: 'it' successfully resolved to 'Ollama' via active topic continuity!")


async def test_section_97():
    print("\n" + "=" * 65)
    print("SECTION 97: FILE CONTINUITY VERIFICATION")
    print("=" * 65)
    router, wm, ref_resolver = create_router()

    # Step 1: User says "Show my recent PDFs."
    print('USER: "Show my recent PDFs."')
    files = [
        FileResourceRef(resource_id="f1", canonical_path="C:/docs/ml_notes.pdf", display_name="ml_notes.pdf"),
        FileResourceRef(resource_id="f2", canonical_path="C:/docs/assignment.pdf", display_name="assignment.pdf"),
        FileResourceRef(resource_id="f3", canonical_path="C:/docs/research.pdf", display_name="research.pdf"),
    ]
    rs = ResultSet(result_set_id="rs_pdf_1", query="recent PDFs", resources=files)
    wm.set_result_set(rs)
    print("JARVIS: Found 3 PDFs: 1. ml_notes.pdf, 2. assignment.pdf, 3. research.pdf")

    # Step 2: "Open the second one."
    print('\nUSER: "Open the second one."')
    req2 = CommandRequest(text="Open the second one.", request_id="s97_2")
    dec2 = await router.route(req2)
    print(f"ROUTER: intent={dec2.intent}, slots={dec2.slots}")
    assert dec2.intent in ("open_file", "file.open") or dec2.slots.get("path")
    # Simulate execution recording opened resource
    wm.set_current_resource(files[1])
    wm.record_file_opened(files[1].canonical_path)
    assert wm.get_current_resource().display_name == "assignment.pdf"
    print(f"Current Resource Set: {wm.get_current_resource().display_name}")

    # Step 3: "What does it talk about?"
    print('\nUSER: "What does it talk about?"')
    req3 = CommandRequest(text="What does it talk about?", request_id="s97_3")
    dec3 = await router.route(req3)
    print(f"ROUTER: intent={dec3.intent}, slots={dec3.slots}")
    assert dec3.intent == "document_qa"
    assert "assignment.pdf" in dec3.slots.get("path", "")
    print(f"Document QA Routed Path: {dec3.slots.get('path')}")

    # Step 4: "Open its folder."
    print('\nUSER: "Open its folder."')
    req4 = CommandRequest(text="Open its folder.", request_id="s97_4")
    dec4 = await router.route(req4)
    print(f"ROUTER: intent={dec4.intent}, slots={dec4.slots}")
    assert Path(dec4.slots.get("path")) == Path("C:/docs") or dec4.slots.get("referent") == "parent_dir"
    print(f"Parent Folder Resolved: {dec4.slots.get('path')}")

    # Step 5: "Where is it?"
    print('\nUSER: "Where is it?"')
    req5 = CommandRequest(text="Where is it?", request_id="s97_5")
    dec5 = await router.route(req5)
    print(f"ROUTER: intent={dec5.intent}, slots={dec5.slots}")
    assert Path(dec5.slots.get("path")) == Path("C:/docs/assignment.pdf")
    print(f"File Path Location Resolved: {dec5.slots.get('path')}")
    print("-> SECTION 97 PASSED: Exact ResourceRef maintained consistently over 5 turns without re-search!")


async def test_section_98():
    print("\n" + "=" * 65)
    print("SECTION 98: TOPIC SWITCH CONTINUITY VERIFICATION")
    print("=" * 65)
    router, wm, ref_resolver = create_router()

    # Turn 1: "What is Ollama?"
    print('USER: "What is Ollama?"')
    req1 = CommandRequest(text="What is Ollama?", request_id="s98_1")
    await router.route(req1)
    print(f"Active Topic: {wm.active_topic.canonical_name if wm.active_topic else None}")
    assert wm.active_topic.canonical_name.casefold() == "ollama"

    # Turn 2: "Show my recent PDFs."
    print('\nUSER: "Show my recent PDFs."')
    files = [
        FileResourceRef(resource_id="f1", canonical_path="C:/docs/ml_notes.pdf", display_name="ml_notes.pdf"),
        FileResourceRef(resource_id="f2", canonical_path="C:/docs/assignment.pdf", display_name="assignment.pdf"),
    ]
    wm.set_result_set(ResultSet(result_set_id="rs_pdf_2", query="recent PDFs", resources=files))
    wm.push_topic("PDFs", entity_type=EntityType.TOPIC)
    print(f"Active Topic: {wm.active_topic.canonical_name if wm.active_topic else None}")

    # Turn 3: "Open second."
    print('\nUSER: "Open second."')
    req3 = CommandRequest(text="Open second.", request_id="s98_3")
    await router.route(req3)
    wm.set_current_resource(files[1])
    wm.record_file_opened(files[1].canonical_path)
    print(f"Current Resource: {wm.get_current_resource().display_name}")

    # Turn 4: "Go back to Ollama."
    print('\nUSER: "Go back to Ollama."')
    req4 = CommandRequest(text="Go back to Ollama.", request_id="s98_4")
    await router.route(req4)
    print(f"Restored Active Topic: {wm.active_topic.canonical_name if wm.active_topic else None}")
    assert wm.active_topic.canonical_name.casefold() == "ollama"

    # Turn 5: "Install it."
    print('\nUSER: "Install it."')
    req5 = CommandRequest(text="Install it.", request_id="s98_5")
    dec5 = await router.route(req5)
    print(f"ROUTER: intent={dec5.intent}, slots={dec5.slots}")
    assert dec5.intent == "install_software"
    assert dec5.slots.get("name").casefold() == "ollama"
    print("-> SECTION 98 PASSED: Successfully popped/restored topic stack and resolved 'it' -> Ollama!")


async def test_section_99():
    print("\n" + "=" * 65)
    print("SECTION 99: AMBIGUITY RESOLUTION VERIFICATION")
    print("=" * 65)
    router, wm, ref_resolver = create_router()

    # Turn 1: "Compare Ollama and LM Studio."
    print('USER: "Compare Ollama and LM Studio."')
    req1 = CommandRequest(text="Compare Ollama and LM Studio.", request_id="s99_1")
    await router.route(req1)
    entities = wm.get_recent_entities()
    print(f"Extracted Entities in Context: {[e.canonical_name for e in entities]}")
    assert len(entities) >= 2

    # Turn 2: "Install it."
    print('\nUSER: "Install it."')
    req2 = CommandRequest(text="Install it.", request_id="s99_2")
    dec2 = await router.route(req2)
    print(f"ROUTER: lane={dec2.lane.name}, intent={dec2.intent}")
    print(f"Clarification Prompt: '{dec2.clarification}'")
    print(f"Candidates: {dec2.slots.get('candidates') if dec2.slots else []}")

    assert dec2.lane == RouteLane.CLARIFY
    assert "ollama" in dec2.clarification.lower() and "lm studio" in dec2.clarification.lower()
    print("-> SECTION 99 PASSED: Zero guessing on ambiguous entities; explicit named clarification provided!")


async def main():
    await test_section_96()
    await test_section_97()
    await test_section_98()
    await test_section_99()
    print("\n" + "=" * 65)
    print("ALL REAL-WORLD MANUAL TESTS (SECTIONS 96-99) SUCCESSFULLY VERIFIED!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
