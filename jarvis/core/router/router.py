from time import perf_counter_ns
from typing import Any
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.cache import HotRouteCache
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
from jarvis.core.router.ollama import LLMProvider, OllamaProvider

class SmartRouter:
    def __init__(
        self,
        catalog: IntentCatalog | None = None,
        llm_provider: LLMProvider | None = None,
        cache: HotRouteCache | None = None,
        app_resolver: Any = None,
        registry_version: str = "v1.0.0",
        trace_debug: bool = False,
    ):
        self.catalog = catalog or IntentCatalog.get_default()
        self.llm_provider = llm_provider or OllamaProvider()
        self.cache = cache or HotRouteCache(capacity=2048)
        self.app_resolver = app_resolver
        self.registry_version = registry_version
        self.trace_debug = trace_debug
        self.total_routed = 0
        self.lane_counts: dict[str, int] = {lane.value: 0 for lane in RouteLane}

    async def route(self, request: CommandRequest | str) -> RouteDecision:
        t0 = perf_counter_ns()
        if isinstance(request, str):
            request = CommandRequest(text=request)
        original_text = request.text
        request_id = request.request_id
        breakdown: dict[str, float] = {}

        # 1. CONTROL COMMAND CHECK (< 1 ms)
        t_ctrl_0 = perf_counter_ns()
        control_decision = match_control(original_text, request_id)
        breakdown["control_match_ms"] = (perf_counter_ns() - t_ctrl_0) / 1e6
        if control_decision:
            control_decision.routing_ms = (perf_counter_ns() - t0) / 1e6
            control_decision.breakdown_ms = breakdown
            self._record(control_decision)
            return control_decision

        # 2. NORMALIZATION
        t_norm_0 = perf_counter_ns()
        _, routing_text = normalize_text(original_text)
        breakdown["normalization_ms"] = (perf_counter_ns() - t_norm_0) / 1e6

        if not routing_text:
            decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.CLARIFY,
                intent=None,
                confidence=0.0,
                source=RouteSource.EXACT,
                normalized_text="",
                clarification="I didn't hear a command. How can I help you?",
                reason_code=ReasonCode.UNKNOWN_INTENT,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self._record(decision)
            return decision

        # 3. NEGATION CHECK (prevents execution)
        is_negated, constraints = check_negation(routing_text)
        if is_negated:
            decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.REJECT,
                intent=None,
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=routing_text,
                clarification="Command was negated. No action taken.",
                reason_code=ReasonCode.NEGATED_ACTION,
                constraints=constraints,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self._record(decision)
            return decision

        # 4. QUESTION / INFORMATIONAL GUARD
        if is_informational_or_question(original_text, routing_text):
            decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_2,
                intent=None,
                confidence=0.9,
                source=RouteSource.COMPLEXITY_GATE,
                complexity=ComplexityLevel.COMPLEX,
                needs_planner=True,
                normalized_text=routing_text,
                clarification="This request asks for information or planning. Forwarding to planner.",
                reason_code=ReasonCode.QUESTION_NOT_COMMAND,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self._record(decision)
            return decision

        # 5. HOT ROUTE CACHE LOOKUP (< 0.5 ms)
        t_cache_0 = perf_counter_ns()
        cached = self.cache.get(routing_text, self.registry_version, request_id)
        breakdown["cache_lookup_ms"] = (perf_counter_ns() - t_cache_0) / 1e6
        if cached:
            cached.routing_ms = (perf_counter_ns() - t0) / 1e6
            cached.breakdown_ms = breakdown
            self._record(cached)
            return cached

        # 6. CANDIDATE INTENT RETRIEVAL
        t_cand_0 = perf_counter_ns()
        tokens = routing_text.split()
        candidate_names = self.catalog.retrieve_candidate_intents(tokens, max_candidates=8)
        breakdown["candidate_generation_ms"] = (perf_counter_ns() - t_cand_0) / 1e6

        # 7. DETERMINISTIC COMPOUND COMMAND CHECK (e.g. "open chrome and calculator")
        if " and " in routing_text or " & " in routing_text:
            compound = check_deterministic_compound(routing_text, self.catalog, request_id)
            if compound:
                compound.routing_ms = (perf_counter_ns() - t0) / 1e6
                compound.breakdown_ms = breakdown
                self.cache.put(routing_text, compound, self.registry_version)
                self._record(compound)
                return compound

        # 8. EXACT & GRAMMAR PATTERN MATCH
        t_pat_0 = perf_counter_ns()
        pattern_match = match_patterns(routing_text, candidate_names, self.catalog, request_id)
        breakdown["pattern_match_ms"] = (perf_counter_ns() - t_pat_0) / 1e6
        if pattern_match:
            # Check app disambiguation if open_app
            if pattern_match.intent == "open_app" and "name" in pattern_match.slots:
                ambig = disambiguate_app(pattern_match.slots["name"], self.app_resolver, request_id, routing_text)
                if ambig:
                    ambig.routing_ms = (perf_counter_ns() - t0) / 1e6
                    ambig.breakdown_ms = breakdown
                    self._record(ambig)
                    return ambig

            pattern_match.routing_ms = (perf_counter_ns() - t0) / 1e6
            pattern_match.breakdown_ms = breakdown
            if pattern_match.lane == RouteLane.LANE_0:
                self.cache.put(routing_text, pattern_match, self.registry_version)
            self._record(pattern_match)
            return pattern_match

        # 9. PREFILTERED FUZZY MATCH
        t_fuzz_0 = perf_counter_ns()
        fuzzy = match_fuzzy(routing_text, candidate_names, self.catalog, request_id)
        breakdown["fuzzy_ms"] = (perf_counter_ns() - t_fuzz_0) / 1e6
        if fuzzy:
            if fuzzy.intent == "open_app" and "name" in fuzzy.slots:
                ambig = disambiguate_app(fuzzy.slots["name"], self.app_resolver, request_id, routing_text)
                if ambig:
                    ambig.routing_ms = (perf_counter_ns() - t0) / 1e6
                    ambig.breakdown_ms = breakdown
                    self._record(ambig)
                    return ambig

            fuzzy.routing_ms = (perf_counter_ns() - t0) / 1e6
            fuzzy.breakdown_ms = breakdown
            if fuzzy.lane == RouteLane.LANE_0:
                self.cache.put(routing_text, fuzzy, self.registry_version)
            self._record(fuzzy)
            return fuzzy

        # 10. COMPLEXITY GATE
        t_cplx_0 = perf_counter_ns()
        complexity = check_complexity_gate(routing_text, request_id)
        breakdown["complexity_ms"] = (perf_counter_ns() - t_cplx_0) / 1e6
        if complexity:
            complexity.routing_ms = (perf_counter_ns() - t0) / 1e6
            complexity.breakdown_ms = breakdown
            self._record(complexity)
            return complexity

        # 11. LANE 1: TINY LOCAL MODEL (Ollama)
        candidate_defns = [self.catalog.intents[c] for c in candidate_names if c in self.catalog.intents]
        try:
            llm_decision = await self.llm_provider.classify(routing_text, candidate_defns, request_id)
        except Exception as exc:
            llm_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.CLARIFY,
                intent=None,
                slots={},
                confidence=0.0,
                source=RouteSource.TINY_MODEL,
                complexity=ComplexityLevel.SIMPLE,
                clarification=f"AI model unavailable ({type(exc).__name__}). Please use standard deterministic commands.",
                normalized_text=routing_text,
                reason_code=ReasonCode.UNKNOWN_INTENT,
            )

        llm_decision.routing_ms = (perf_counter_ns() - t0) / 1e6
        breakdown.update(llm_decision.breakdown_ms)
        llm_decision.breakdown_ms = breakdown

        # Verify app disambiguation if Lane 1 chose open_app
        if llm_decision.intent == "open_app" and "name" in llm_decision.slots:
            ambig = disambiguate_app(str(llm_decision.slots["name"]), self.app_resolver, request_id, routing_text)
            if ambig:
                ambig.routing_ms = (perf_counter_ns() - t0) / 1e6
                ambig.breakdown_ms = breakdown
                self._record(ambig)
                return ambig

        self._record(llm_decision)
        return llm_decision

    def _record(self, decision: RouteDecision):
        self.total_routed += 1
        if decision.lane.value in self.lane_counts:
            self.lane_counts[decision.lane.value] += 1
        if self.trace_debug:
            print(
                f"[ROUTER TRACE] text='{decision.normalized_text}' lane={decision.lane} "
                f"intent={decision.intent} src={decision.source} ms={decision.routing_ms:.3f}ms",
                flush=True,
            )
