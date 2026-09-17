import asyncio
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.models import RouteLane, ReasonCode
from jarvis.core.router.ollama import MockStructuredProvider
from jarvis.tools.registry import ToolRegistry

async def run_demonstrations():
    print("============================================================")
    print("             JARVIS EDGE -- PHASE 2 DEMONSTRATIONS          ")
    print("============================================================")

    mock_provider = MockStructuredProvider(responses={
        "bring chrome up for me": {
            "intent": "open_app",
            "slots": {"name": "chrome", "app": "chrome"},
            "missing_slots": [],
            "confidence": 0.95,
            "is_multi_step": False,
            "is_command": True,
            "unknown": False,
        }
    })
    router = SmartRouter(llm_provider=mock_provider)

    # Demo 1: "open chrome"
    d1 = await router.route("open chrome")
    print("\n[Demo 1] 'open chrome'")
    print(f"  Lane:        {d1.lane.value}")
    print(f"  Intent:      {d1.intent}")
    print(f"  Slots:       {d1.slots}")
    print(f"  Model Used:  {d1.model_used}")
    print(f"  Routing ms:  {d1.routing_ms:.3f} ms")
    assert d1.lane == RouteLane.LANE_0, f"Expected LANE_0, got {d1.lane}"
    assert d1.model_used is None, "Expected NO model used"
    app_val = d1.slots.get("name") or d1.slots.get("app")
    assert d1.intent == "open_app" and app_val == "chrome"
    print("  --> PASS: Lane 0, zero LLM, instant dispatch.")

    # Demo 2: "bro can you bring chrome up for me"
    d2 = await router.route("bro can you bring chrome up for me")
    print("\n[Demo 2] 'bro can you bring chrome up for me'")
    print(f"  Lane:        {d2.lane.value}")
    print(f"  Intent:      {d2.intent}")
    print(f"  Slots:       {d2.slots}")
    print(f"  Source:      {d2.source.value}")
    print(f"  Routing ms:  {d2.routing_ms:.3f} ms")
    app_val2 = d2.slots.get("name") or d2.slots.get("app")
    assert d2.intent == "open_app" and app_val2 == "chrome"
    print("  --> PASS: Correctly resolved to open_app(chrome).")

    # Demo 3: "don't open chrome"
    d3 = await router.route("don't open chrome")
    r3 = getattr(d3.reason_code, "value", d3.reason_code)
    print("\n[Demo 3] 'don't open chrome'")
    print(f"  Lane:        {d3.lane.value}")
    print(f"  Reason:      {r3}")
    print(f"  Intent:      {d3.intent}")
    assert d3.lane == RouteLane.REJECT
    assert r3 == ReasonCode.NEGATED_ACTION.value
    assert d3.intent is None
    print("  --> PASS: Negation detected, NO execution.")

    # Demo 4: "can chrome open pdf files?"
    d4 = await router.route("can chrome open pdf files?")
    r4 = getattr(d4.reason_code, "value", d4.reason_code)
    print("\n[Demo 4] 'can chrome open pdf files?'")
    print(f"  Lane:        {d4.lane.value}")
    print(f"  Reason:      {r4}")
    print(f"  Intent:      {d4.intent}")
    assert d4.intent is None
    assert r4 == ReasonCode.QUESTION_NOT_COMMAND.value
    print("  --> PASS: Question detected, NO fake execution.")

    # Demo 5: "make the sound a little quieter"
    d5 = await router.route("make the sound a little quieter")
    print("\n[Demo 5] 'make the sound a little quieter'")
    print(f"  Lane:        {d5.lane.value}")
    print(f"  Intent:      {d5.intent}")
    print(f"  Source:      {d5.source.value}")
    assert d5.intent == "volume_down"
    print("  --> PASS: Correctly resolved to volume_down.")

    # Demo 6: "open studio"
    d6 = await router.route("open studio")
    r6 = getattr(d6.reason_code, "value", d6.reason_code)
    print("\n[Demo 6] 'open studio'")
    print(f"  Lane:        {d6.lane.value}")
    print(f"  Reason:      {r6}")
    print(f"  Clarify:     {d6.clarification}")
    assert d6.lane == RouteLane.CLARIFY
    assert "Which one do you mean" in (d6.clarification or "")
    print("  --> PASS: Ambiguous app prompts clarification, no guess.")

    # Demo 7: "open chrome and calculator"
    d7 = await router.route("open chrome and calculator")
    print("\n[Demo 7] 'open chrome and calculator'")
    print(f"  Lane:        {d7.lane.value}")
    print(f"  Complexity:  {d7.complexity.value}")
    print(f"  Subcommands: {[(sc.intent, sc.arguments) for sc in (d7.subcommands or [])]}")
    assert d7.lane == RouteLane.LANE_0
    assert len(d7.subcommands) == 2
    sc0_app = d7.subcommands[0].arguments.get("name") or d7.subcommands[0].arguments.get("app")
    sc1_app = d7.subcommands[1].arguments.get("name") or d7.subcommands[1].arguments.get("app")
    assert sc0_app == "chrome"
    assert sc1_app == "calculator"
    print("  --> PASS: Safe deterministic compound command parsed.")

    # Demo 8: "find tomorrow's ML material and put everything into one folder"
    d8 = await router.route("find tomorrow's ML material and put everything into one folder")
    r8 = getattr(d8.reason_code, "value", d8.reason_code)
    print("\n[Demo 8] 'find tomorrow\\'s ML material and put everything into one folder'")
    print(f"  Lane:        {d8.lane.value}")
    print(f"  Needs Plan:  {d8.needs_planner}")
    print(f"  Reason:      {r8}")
    assert d8.lane == RouteLane.LANE_2
    assert d8.needs_planner is True
    print("  --> PASS: Complex request routed to Lane 2, no fake execution.")

    # Demo 9: Ollama stopped. "open calculator"
    router_offline = SmartRouter(llm_provider=None)
    d9 = await router_offline.route("open calculator")
    print("\n[Demo 9] Ollama completely stopped -> 'open calculator'")
    print(f"  Lane:        {d9.lane.value}")
    print(f"  Intent:      {d9.intent}")
    print(f"  Slots:       {d9.slots}")
    print(f"  Routing ms:  {d9.routing_ms:.3f} ms")
    assert d9.lane == RouteLane.LANE_0
    assert d9.intent == "open_app"
    app_val9 = d9.slots.get("name") or d9.slots.get("app")
    assert app_val9 == "calculator"
    print("  --> PASS: Lane 0 works instantly even with Ollama completely absent.")

    print("\n============================================================")
    print("         ALL 9 REQUIRED DEMONSTRATIONS PASSED               ")
    print("============================================================")

if __name__ == "__main__":
    asyncio.run(run_demonstrations())
