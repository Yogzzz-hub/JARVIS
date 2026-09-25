import asyncio
import json
from pathlib import Path
import pytest
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.cache import HotRouteCache, RouteTemplate
from jarvis.core.router.catalog import IntentCatalog
from jarvis.core.router.complexity import check_complexity_gate, check_deterministic_compound
from jarvis.core.router.control import match_control
from jarvis.core.router.disambiguation import disambiguate_app
from jarvis.core.router.fuzzy import match_fuzzy
from jarvis.core.router.guards import check_negation, is_informational_or_question
from jarvis.core.router.matcher import match_patterns
from jarvis.core.router.models import (
    ComplexityLevel,
    ReasonCode,
    RouteDecision,
    RouteLane,
    RouteSource,
)
from jarvis.core.router.normalize import normalize_text
from jarvis.core.router.ollama import OllamaProvider
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.slots import (
    parse_app_name,
    parse_duration_seconds,
    parse_folder_path,
    parse_integer,
    parse_percentage,
    parse_slot_value,
)

# 1. Normalization & Wake-word tests
def test_normalization_and_wake_words():
    orig, routing = normalize_text("Hey Jarvis, please open Chrome")
    assert routing == "open chrome"
    assert orig == "Hey Jarvis, please open Chrome"

    _, routing = normalize_text("Jarvis bro open VS Code da")
    assert routing == "open vscode"

    _, routing = normalize_text("Ok Jarvis, launch calculator please")
    assert routing == "launch calculator"

def test_normalization_meaning_preservation():
    # Protected words must NOT be removed
    _, routing = normalize_text("just show the files, don't delete anything")
    assert "just" in routing
    assert "don't" in routing or "dont" in routing
    assert "delete" in routing

def test_negation_detection():
    is_neg, constraints = check_negation("don't open chrome")
    assert is_neg is True
    assert len(constraints) == 1
    assert constraints[0]["target"] == "chrome"

    is_neg, constraints = check_negation("do not launch vscode")
    assert is_neg is True

    is_neg, constraints = check_negation("open chrome but don't send anything")
    assert is_neg is False
    assert len(constraints) == 1
    assert "send" in constraints[0]["target"]

def test_question_vs_command():
    # Questions and state queries must return True
    assert is_informational_or_question("Can Chrome open PDF files?", "can chrome open pdf files") is True
    assert is_informational_or_question("How do I open Chrome?", "how do i open chrome") is True
    assert is_informational_or_question("Is Chrome open?", "is chrome open") is True
    assert is_informational_or_question("Is notepad installed?", "is notepad installed") is True
    assert is_informational_or_question("Why did Chrome close?", "why did chrome close") is True
    assert is_informational_or_question("What is quantum computing?", "what is quantum computing") is True

    # Imperative commands must return False
    assert is_informational_or_question("Open Chrome", "open chrome") is False
    assert is_informational_or_question("Hey Jarvis, can you open Chrome?", "open chrome") is False
    assert is_informational_or_question("Please launch calculator", "launch calculator") is False

# 2. Slot Parsing tests
def test_slot_parsers():
    assert parse_percentage("30") == 30
    assert parse_percentage("30%") == 30
    assert parse_percentage("thirty percent") == 30
    assert parse_percentage("hundred") == 100
    assert parse_percentage("150") is None  # out of range

    assert parse_duration_seconds("600 seconds") == 600
    assert parse_duration_seconds("10 minutes") == 600
    assert parse_duration_seconds("twenty minutes") == 1200
    assert parse_duration_seconds("1 hour") == 3600

    assert parse_app_name("Google Chrome") == "chrome"
    assert parse_app_name("Visual Studio Code") == "vscode"
    assert parse_app_name("Calc") == "calculator"

    desktop = parse_folder_path("desktop")
    assert "Desktop" in desktop

def test_slot_schema_validation():
    assert parse_slot_value("percent", "50") == 50
    assert parse_slot_value("seconds", "5 mins") == 300
    assert parse_slot_value("name", "vs code") == "vscode"

# 3. Control Command tests
def test_control_commands():
    for cmd in ("stop", "cancel", "cancel that", "stop everything", "never mind", "abort", "stop now"):
        dec = match_control(cmd, "req1")
        assert dec is not None
        assert dec.lane == RouteLane.CONTROL
        assert dec.confidence == 1.0
        assert dec.source == RouteSource.CONTROL

    assert match_control("open chrome", "req2") is None

# 4. Catalog & Precompiled Index tests
def test_intent_catalog_startup_compilation():
    catalog = IntentCatalog.get_default()
    assert "open_app" in catalog.intents
    assert "volume_set" in catalog.intents
    assert len(catalog.token_index) > 0

    candidates = catalog.retrieve_candidate_intents(["open", "chrome"])
    assert "open_app" in candidates

    candidates = catalog.retrieve_candidate_intents(["volume", "30"])
    assert "volume_set" in candidates or "volume_down" in candidates or "volume_up" in candidates

# 5. Exact & Grammar Route tests
def test_exact_and_grammar_matching():
    catalog = IntentCatalog.get_default()
    # Exact / Grammar
    dec = match_patterns("open chrome", ["open_app"], catalog, "req1")
    assert dec is not None
    assert dec.lane == RouteLane.LANE_0
    assert dec.intent == "open_app"
    assert dec.slots == {"name": "chrome"}

    # Time exact
    dec = match_patterns("time", ["get_time"], catalog, "req2")
    assert dec is not None
    assert dec.lane == RouteLane.LANE_0
    assert dec.intent == "get_time"

    # Volume set grammar
    dec = match_patterns("volume 40", ["volume_set"], catalog, "req3")
    assert dec is not None
    assert dec.lane == RouteLane.LANE_0
    assert dec.intent == "volume_set"
    assert dec.slots == {"percent": 40}

# 6. Prefiltered Fuzzy Matching & Ambiguity Margin
def test_fuzzy_matching():
    catalog = IntentCatalog.get_default()
    # Casual / slight variation
    dec = match_fuzzy("make it a little quieter", ["volume_down", "volume_up"], catalog, "req1")
    assert dec is not None
    assert dec.lane == RouteLane.LANE_0
    assert dec.intent == "volume_down"

def test_fuzzy_ambiguity_rejection():
    catalog = IntentCatalog.get_default()
    # Artificial ambiguity between similar candidates
    dec = match_fuzzy("turn sound", ["volume_down", "volume_up", "volume_set"], catalog, "req1")
    # Low margin / score should not blindly execute
    assert dec is None

# 7. App Disambiguation & Clarification
def test_app_disambiguation():
    dec = disambiguate_app("studio", None, "req1", "open studio")
    assert dec is not None
    assert dec.lane == RouteLane.CLARIFY
    assert "Android Studio" in dec.clarification
    assert dec.reason_code == ReasonCode.LOW_CONFIDENCE

# 8. Deterministic Compound Commands
def test_deterministic_compound_command():
    catalog = IntentCatalog.get_default()
    dec = check_deterministic_compound("open chrome and calculator", catalog, "req1")
    assert dec is not None
    assert dec.lane == RouteLane.LANE_0
    assert dec.complexity == ComplexityLevel.COMPOUND
    assert len(dec.subcommands) == 2
    assert dec.subcommands[0].arguments["name"] == "chrome"
    assert dec.subcommands[1].arguments["name"] == "calculator"

    # Max bounded: 4 subcommands should fail compound check and defer
    dec_too_many = check_deterministic_compound("open a and b and c and d", catalog, "req2")
    assert dec_too_many is None

# 9. Complexity Gate tests (Lane 2)
def test_complexity_gate():
    dec = check_complexity_gate("find tomorrow ML material and put everything into one folder", "req1")
    assert dec is not None
    assert dec.lane == RouteLane.LANE_2
    assert dec.needs_planner is True

    dec = check_complexity_gate("find my notes and email them to santosh", "req2")
    assert dec is not None
    assert dec.lane == RouteLane.LANE_2

    dec = check_complexity_gate("open chrome", "req3")
    assert dec is None

# 10. Cache tests (LRU, Promotion, Invalidation)
def test_hot_route_cache():
    cache = HotRouteCache(capacity=3)
    dec = RouteDecision(
        request_id="1", lane=RouteLane.LANE_0, intent="open_app", slots={"name": "chrome"},
        confidence=1.0, source=RouteSource.EXACT, normalized_text="open chrome", reason_code=ReasonCode.EXACT_PATTERN
    )
    cache.put("open chrome", dec, "v1")
    assert cache.get("open chrome", "v1", "2") is not None
    assert cache.hits == 1

    # Invalidation on registry version mismatch
    assert cache.get("open chrome", "v2", "3") is None
    assert cache.misses == 1

    # Capacity eviction
    cache.put("a", dec, "v1")
    cache.put("b", dec, "v1")
    cache.put("c", dec, "v1")
    cache.put("d", dec, "v1")
    assert cache.evictions >= 1

def test_cache_promotion():
    cache = HotRouteCache(capacity=10)
    dec = RouteDecision(
        request_id="1", lane=RouteLane.LANE_1, intent="open_app", slots={"name": "chrome"},
        confidence=0.95, source=RouteSource.TINY_MODEL, normalized_text="bro chrome open pannu",
        reason_code=ReasonCode.LLM_CLASSIFIED
    )
    promoted = cache.record_success_for_promotion("bro chrome open pannu", dec, "v1", threshold=3)
    assert promoted is True
    assert cache.get("bro chrome open pannu", "v1", "2") is not None

# 11. Mock LLM Provider & Failure Resilience
class MockFailingProvider:
    async def classify(self, text, candidates, request_id):
        raise ConnectionRefusedError("Ollama stopped")

class MockStructuredProvider:
    async def classify(self, text, candidates, request_id):
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.LANE_1,
            intent="volume_down",
            slots={},
            confidence=0.92,
            source=RouteSource.TINY_MODEL,
            normalized_text=text,
            reason_code=ReasonCode.LLM_CLASSIFIED,
        )

@pytest.mark.asyncio
async def test_ollama_unavailable_graceful_fallback():
    router = SmartRouter(llm_provider=MockFailingProvider())
    # Unmatched text falls back gracefully to clarify without crashing
    dec = await router.route(CommandRequest(text="unusual phrase that fails matching"))
    # A classifier failure is not a refusal: the request goes on to the assistant / tool agent.
    assert dec.intent == "ollama_chat" and dec.context_trace == {"fallback": "unknown_command"}
    assert "unavailable" not in (dec.clarification or "").lower()

    # Deterministic commands MUST still work even when model provider fails!
    dec_det = await router.route(CommandRequest(text="open chrome"))
    assert dec_det.lane == RouteLane.LANE_0
    assert dec_det.intent == "open_app"

@pytest.mark.asyncio
async def test_lane_1_classification():
    router = SmartRouter(llm_provider=MockStructuredProvider())
    # An unusual phrasing not in regex
    dec = await router.route(CommandRequest(text="please decrease sound a tiny bit"))
    assert dec.lane in (RouteLane.LANE_0, RouteLane.LANE_1)
    assert dec.intent == "volume_down"

# 12. Golden & Adversarial Dataset Tests
@pytest.mark.asyncio
async def test_adversarial_false_actions_zero():
    router = SmartRouter()
    adv_path = Path(__file__).parent / "data/router_adversarial.jsonl"
    assert adv_path.exists()

    with adv_path.open(encoding="utf-8") as f:
        traps = [json.loads(line) for line in f]

    wrong_executions = 0
    for trap in traps:
        dec = await router.route(CommandRequest(text=trap["text"]))
        # Under NO circumstance should a trap question/negation execute the forbidden tool!
        forbidden = trap.get("forbidden_intent")
        if forbidden == "any_tool" and dec.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and dec.intent is not None:
            wrong_executions += 1
        elif dec.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and dec.intent == forbidden:
            wrong_executions += 1

    assert wrong_executions == 0, f"Expected 0 wrong executions on adversarial dataset, got {wrong_executions}"

@pytest.mark.asyncio
async def test_golden_dataset_evaluation():
    router = SmartRouter(llm_provider=MockStructuredProvider())
    golden_path = Path(__file__).parent / "data/router_golden.jsonl"
    assert golden_path.exists()

    with golden_path.open(encoding="utf-8") as f:
        items = [json.loads(line) for line in f]

    assert len(items) >= 300

    correct_lane = 0
    correct_intent = 0
    total = len(items)

    for item in items:
        dec = await router.route(CommandRequest(text=item["text"]))
        expected_lane = item.get("expected_lane")
        expected_intent = item.get("expected_intent")

        if expected_lane and dec.lane.value == expected_lane:
            correct_lane += 1
        elif not expected_lane:
            correct_lane += 1

        if expected_intent and dec.intent == expected_intent:
            correct_intent += 1
        elif not expected_intent:
            correct_intent += 1

    lane_acc = (correct_lane / total) * 100
    intent_acc = (correct_intent / total) * 100
    assert lane_acc >= 90.0, f"Lane accuracy {lane_acc:.2f}% below target"
    assert intent_acc >= 85.0, f"Intent accuracy {intent_acc:.2f}% below target"

@pytest.mark.asyncio
async def test_direct_app_name_typing():
    router = SmartRouter()
    for app in ("chrome", "notepad", "calculator", "calc", "youtube", "whatsapp", "spotify"):
        dec = await router.route(CommandRequest(text=app))
        assert dec.lane == RouteLane.LANE_0, f"Failed for {app}: lane is {dec.lane}"
        assert dec.intent == "open_app", f"Failed for {app}: intent is {dec.intent}"
        assert dec.slots.get("name") in (app, "calculator"), f"Failed slot for {app}: {dec.slots}"

@pytest.mark.asyncio
async def test_conversational_affirmation_leading_commands():
    router = SmartRouter()
    dec = await router.route(CommandRequest(text="yes, open chrome"))
    assert dec.lane == RouteLane.LANE_0
    assert dec.intent == "open_app"

    dec2 = await router.route(CommandRequest(text="yeah launch notepad"))
    assert dec2.lane == RouteLane.LANE_0
    assert dec2.intent == "open_app"

@pytest.mark.asyncio
async def test_dictation_typing_commands():
    router = SmartRouter()
    dec = await router.route(CommandRequest(text="type hello world"))
    assert dec.lane == RouteLane.LANE_0
    assert dec.intent == "dictate_text"
    assert dec.slots.get("text") == "hello world"

    dec2 = await router.route(CommandRequest(text="dictate meeting notes for today"))
    assert dec2.lane == RouteLane.LANE_0
    assert dec2.intent == "dictate_text"
    assert dec2.slots.get("text") == "meeting notes for today"

def test_voice_pipeline_strip_wake_phrases():
    from jarvis.core.audio.pipeline import VoicePipeline
    assert VoicePipeline._strip_wake_phrase("Hey Jarvis, open Chrome") == "open Chrome"
    assert VoicePipeline._strip_wake_phrase("Hey Jarvis open Chrome") == "open Chrome"
    assert VoicePipeline._strip_wake_phrase("Yes, open Chrome") == "open Chrome"
    assert VoicePipeline._strip_wake_phrase("Yes open Chrome") == "open Chrome"
    assert VoicePipeline._strip_wake_phrase("Yeah launch notepad") == "launch notepad"
    assert VoicePipeline._strip_wake_phrase("Hey Jarvis") == ""
    assert VoicePipeline._strip_wake_phrase("Yes") == "Yes"

@pytest.mark.asyncio
async def test_advanced_multimedia_and_window_commands():
    router = SmartRouter()

    # 1. YouTube play command
    dec = await router.route(CommandRequest(text="open youtube and play believer"))
    assert dec.lane == RouteLane.LANE_0
    assert dec.intent in ("play_youtube", "compound")
    if dec.intent == "play_youtube":
        assert "believer" in dec.slots.get("query", "").lower()
    else:
        assert any(sub.tool == "play_youtube" for sub in dec.subcommands)

    # 2. Live news search command
    dec_news = await router.route(CommandRequest(text="search news in india"))
    assert dec_news.lane == RouteLane.LANE_0
    assert dec_news.intent in ("search_news", "compound")
    if dec_news.intent == "search_news":
        assert "india" in dec_news.slots.get("query", "").lower()

    # 3. Window control commands
    dec_max = await router.route(CommandRequest(text="maximize window"))
    assert dec_max.lane == RouteLane.LANE_0
    assert dec_max.intent == "maximize_window"

    for phrase in ("fulll screen", "full screen", "fullscreen", "make it full screen"):
        dec_fs = await router.route(CommandRequest(text=phrase))
        assert dec_fs.lane == RouteLane.LANE_0
        assert dec_fs.intent == "maximize_window"

    dec_min = await router.route(CommandRequest(text="minimize window"))
    assert dec_min.lane == RouteLane.LANE_0
    assert dec_min.intent == "minimize_window"

    dec_desk = await router.route(CommandRequest(text="show desktop"))
    assert dec_desk.lane == RouteLane.LANE_0
    assert dec_desk.intent == "show_desktop"

    # 4. Hardware media controls
    dec_media = await router.route(CommandRequest(text="next track"))
    assert dec_media.lane == RouteLane.LANE_0
    assert dec_media.intent == "media_control"
    assert dec_media.slots.get("action") in ("next track", "next_track")

    # 5. Compound heterogeneous command
    dec_compound = await router.route(CommandRequest(text="maximize window and play believer on youtube"))
    assert dec_compound.lane == RouteLane.LANE_0
    assert dec_compound.complexity == ComplexityLevel.COMPOUND
    assert len(dec_compound.subcommands) == 2
    assert dec_compound.subcommands[0].tool == "maximize_window"
    assert dec_compound.subcommands[1].tool == "play_youtube"

