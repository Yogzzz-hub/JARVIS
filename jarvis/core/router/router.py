import re
from time import perf_counter_ns
from typing import Any
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.cache import HotRouteCache
from jarvis.core.router.catalog import IntentCatalog
from jarvis.core.router.complexity import check_complexity_gate, check_deterministic_compound
from jarvis.core.router.control import match_control
from jarvis.core.router.disambiguation import disambiguate_app
from jarvis.core.router.fuzzy import match_fuzzy
from jarvis.core.context.entity_extractor import EntityExtractor
from jarvis.core.context.followup_detector import FollowupDetector
from jarvis.core.context.models import FollowupType, ReferenceConfidence
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

KNOWN_SHELL_COMMANDS = frozenset({
    "dir", "ipconfig", "ping", "systeminfo", "tasklist", "netstat", "hostname",
    "whoami", "echo", "curl", "tree", "get-process", "get-service", "python",
    "node", "pip", "npm", "git", "wmic", "cls", "path", "nslookup", "tracert"
})


def _llm_down(decision) -> bool:
    """The classifier failed because Ollama is unreachable (not merely slow or confused)."""
    trace = getattr(decision, "context_trace", None) or {}
    return bool(trace.get("llm_unavailable")) or "AI model unavailable" in (getattr(decision, "clarification", "") or "")

class SmartRouter:
    def __init__(
        self,
        catalog: IntentCatalog | None = None,
        llm_provider: LLMProvider | None = None,
        cache: HotRouteCache | None = None,
        app_resolver: Any = None,
        registry_version: str = "v1.0.0",
        trace_debug: bool = False,
        tool_registry: Any = None,
        working_memory: Any = None,
        reference_resolver: Any = None,
        capability_registry: Any = None,
        capability_retriever: Any = None,
    ):
        self.catalog = catalog or IntentCatalog.get_default()
        self.llm_provider = llm_provider or OllamaProvider()
        self.cache = cache or HotRouteCache(capacity=2048)
        self.app_resolver = app_resolver
        self.registry_version = registry_version
        self.trace_debug = trace_debug
        self.total_routed = 0
        self.lane_counts: dict[str, int] = {lane.value: 0 for lane in RouteLane}
        self.tool_registry = tool_registry
        self.working_memory = working_memory
        self.reference_resolver = reference_resolver
        from jarvis.core.capabilities.registry import get_default_capability_registry
        from jarvis.core.capabilities.retrieval import CapabilityRetriever
        self.capability_registry = capability_registry or get_default_capability_registry(tool_registry)
        self.capability_retriever = capability_retriever or CapabilityRetriever(self.capability_registry)
        if hasattr(self.llm_provider, "capability_retriever"):
            self.llm_provider.capability_retriever = self.capability_retriever
        if hasattr(self.llm_provider, "capability_registry"):
            self.llm_provider.capability_registry = self.capability_registry
        if tool_registry is not None and getattr(self.llm_provider, "tool_registry", False) is None:
            self.llm_provider.tool_registry = tool_registry
        self.last_clarification_candidates: list[str] = []
        self.last_clarification_intent: str = "open_app"

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
            orig_lower = original_text.lower().strip().rstrip(".!,?")
            wake_phrases = {"hey jarvis", "jarvis", "hello", "hi", "wake", "wake up", "are you there", "dashboard"}
            if orig_lower in wake_phrases or any(orig_lower.startswith(wp) for wp in wake_phrases):
                decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent="show_dashboard",
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=original_text,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(decision)
                return decision

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

        # 3a. "Reply to everyone who messaged me ... don't reply in groups": the constraint is part of the
        # request, not a negation of it, so this is decided before the negation guard.
        from jarvis.core.router.extended import match_bulk_reply
        bulk_decision = match_bulk_reply(original_text, request_id)
        if bulk_decision:
            bulk_decision.routing_ms = (perf_counter_ns() - t0) / 1e6
            bulk_decision.breakdown_ms = breakdown
            self._record(bulk_decision)
            return bulk_decision

        # 3. NEGATION CHECK (prevents execution)
        is_negated, constraints = check_negation(routing_text)
        positive_override = next((c["target"] for c in constraints if c.get("type") == "positive_override"), None)
        if is_negated and not positive_override:
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

        if positive_override:
            routing_text = positive_override

        # 3b. DIRECT SYSTEM ACTIONS & DASHBOARD BUTTONS (< 0.5 ms)
        clean_lower = routing_text.strip().lower()

        # Unsupported physical / external / non-desktop domain check
        from jarvis.core.router.unsupported import check_unsupported_external
        unsupported_dec = check_unsupported_external(clean_lower, request_id)
        if unsupported_dec:
            unsupported_dec.routing_ms = (perf_counter_ns() - t0) / 1e6
            unsupported_dec.breakdown_ms = breakdown
            self._record(unsupported_dec)
            return unsupported_dec

        if re.search(r"\b(?:diagnostics?|run diagnostics?|diagnostic check|system diagnostics?|system audit|subsystem audit|subsystem diagnostic check)\b", clean_lower):
            diag_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="system_diagnostics",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, diag_decision, self.registry_version)
            self._record(diag_decision)
            return diag_decision

        # 3a. CONVERSATIONAL CONTINUITY & FOLLOW-UP CHECK (< 0.5 ms)
        working_ctx = getattr(self.working_memory, "context", None) if self.working_memory else None
        followup = FollowupDetector.classify(routing_text, working_ctx)

        # 3a-1. ACTIVE PENDING CONFIRMATION / CANCELLATION (Section 43 & 44)
        if followup.followup_type == FollowupType.CONFIRMATION:
            pending_conf = getattr(self.working_memory, "get_pending_confirmation", lambda: None)()
            if pending_conf:
                self.working_memory.set_pending_confirmation(None)
                conf_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CONTROL,
                    intent="confirm_ticket",
                    slots={"ticket_id": pending_conf.ticket_id},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(conf_decision)
                return conf_decision

        elif followup.followup_type == FollowupType.CANCELLATION:
            pending_conf = getattr(self.working_memory, "get_pending_confirmation", lambda: None)()
            if pending_conf:
                self.working_memory.set_pending_confirmation(None)
                canc_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CONTROL,
                    intent="reject_ticket",
                    slots={"ticket_id": pending_conf.ticket_id},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(canc_decision)
                return canc_decision

        # 3a-2. WHY QUERY / ERROR EXPLANATION (Section 46)
        elif followup.followup_type == FollowupType.WHY_QUERY:
            last_fail = getattr(self.working_memory, "get_last_failure", lambda: None)()
            if last_fail:
                target = last_fail.get("target", "The target")
                reason = last_fail.get("reason", "unknown error")
                if reason in ("APP_NOT_FOUND", "not_found"):
                    msg = f"{target} wasn't present in the current application catalog."
                else:
                    msg = f"{target} failed: {reason}."
                why_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent="system_info",
                    slots={"message": msg},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    clarification=msg,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(why_decision)
                return why_decision

        # 3a-3. TOPIC SWITCH (Section 20)
        elif followup.followup_type == FollowupType.TOPIC_SWITCH and followup.target_hint:
            if self.working_memory:
                restored = getattr(self.working_memory, "restore_topic", lambda x: None)(followup.target_hint)
                if not restored and hasattr(self.working_memory, "push_topic"):
                    from jarvis.core.context.models import TopicRef, EntityType
                    self.working_memory.push_topic(TopicRef(
                        entity_id=f"topic_{followup.target_hint.lower().replace(' ', '_')}",
                        canonical_name=followup.target_hint.lower(),
                        display_name=followup.target_hint.title(),
                        entity_type=EntityType.TOPIC,
                    ))

        # 3a-4. ACTION ON TOPIC / PRONOUN CONTINUITY (Sections 13-16, 24, 36)
        if clean_lower in ("open its folder", "show its folder", "open parent folder"):
            if self.reference_resolver:
                res = self.reference_resolver.resolve("same folder")
                if res.referent and res.confidence == ReferenceConfidence.HIGH:
                    exp_decision = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent="open_app",
                        slots={"name": "explorer", "path": str(res.referent), "referent": "parent_dir"},
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=clean_lower,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(exp_decision)
                    return exp_decision

        elif clean_lower in ("where is it", "where is it stored", "where is it located", "where did it install"):
            if self.reference_resolver:
                res = self.reference_resolver.resolve(clean_lower)
                if res.referent and res.confidence == ReferenceConfidence.HIGH:
                    loc_intent = "file.location" if res.referent_type == "FILE" else "get_app_location"
                    loc_slot = "path" if res.referent_type == "FILE" else "name"
                    loc_decision = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent=loc_intent,
                        slots={loc_slot: str(res.referent)},
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=clean_lower,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(loc_decision)
                    return loc_decision

        elif "send" in clean_lower and any(d in clean_lower for d in ("phone", "mobile", "android")) and any(p in clean_lower for p in ("it", "this", "that")):
            if self.reference_resolver:
                res = self.reference_resolver.resolve_for_slot(clean_lower, expected_slot_type="file")
                if res.referent and res.confidence == ReferenceConfidence.HIGH:
                    phone_decision = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent="phone.send_file",
                        slots={"path": str(res.referent), "destination": "phone"},
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=clean_lower,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(phone_decision)
                    return phone_decision

        elif clean_lower in ("open it", "launch it", "run it"):
            if self.reference_resolver:
                res = self.reference_resolver.resolve(clean_lower)
                if res.referent and res.confidence == ReferenceConfidence.HIGH:
                    open_intent = "open_file" if res.referent_type == "FILE" else "open_app"
                    open_slot = "path" if res.referent_type == "FILE" else "name"
                    open_decision = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent=open_intent,
                        slots={open_slot: str(res.referent)},
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=clean_lower,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(open_decision)
                    return open_decision

        # 3b. CLARIFICATION CANDIDATE ORDINAL SELECTION / RESULT SET ORDINAL
        m_ord = re.match(r"^(?:the\s+)?(?:(1st|first|1|one|1\s*st)(?:\s+(?:1|one|option))?|(2nd|second|2|two|2\s*nd)(?:\s+(?:2|two|option|one))?|(3rd|third|3|three|3\s*rd)(?:\s+(?:3|three|option|one))?|(4th|fourth|4|four|4\s*th)(?:\s+(?:4|four|option|one))?)$", clean_lower, re.I)
        if self.last_clarification_candidates and m_ord:
            idx = 0 if m_ord.group(1) else (1 if m_ord.group(2) else (2 if m_ord.group(3) else 3))
            if idx < len(self.last_clarification_candidates):
                selected = self.last_clarification_candidates[idx]
                self.last_clarification_candidates = []
                intent_target = self.last_clarification_intent if self.last_clarification_intent != "clarify" else "open_app"
                slot_key = "path" if "file" in intent_target else "name"
                ord_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent=intent_target,
                    slots={slot_key: selected},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(ord_decision)
                return ord_decision

        elif (m_ord or followup.followup_type == FollowupType.ORDINAL_REFERENCE) and self.reference_resolver:
            res = self.reference_resolver.resolve(clean_lower)
            if res.referent and res.confidence == ReferenceConfidence.HIGH:
                intent_target = "open_file" if res.referent_type in ("FILE", "SEARCH_RESULT") else "open_app"
                slot_key = "path" if intent_target == "open_file" else "name"
                ord_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent=intent_target,
                    slots={slot_key: str(res.referent)},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(ord_decision)
                return ord_decision

        # 3b-ord. "open the second one" with nothing listed yet: ask, never open an app called "second 1"
        m_ref = re.match(r"^(?:open|pick|take|choose|select|play|show|use)\s+(?:the\s+)?(first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th)"
                         r"(?:\s+(?:one|1|file|result|item|document|option|link|video|song|match))?$", clean_lower)
        if m_ref:
            ordinal = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
                       "fifth": 5, "5th": 5, "last": -1}[m_ref.group(1)]
            ref_decision = RouteDecision(
                request_id=request_id, lane=RouteLane.CLARIFY, intent="open_file", slots={"ordinal": ordinal},
                confidence=0.5, source=RouteSource.EXACT, complexity=ComplexityLevel.SIMPLE, normalized_text=clean_lower,
                clarification="Which list do you mean? Search or list something first, then say 'open the second one'.",
                reason_code=ReasonCode.EXACT_PATTERN, routing_ms=(perf_counter_ns() - t0) / 1e6, breakdown_ms=breakdown)
            self._record(ref_decision)
            return ref_decision

        # 3b-ext. EXTENDED DOMAINS: phone control, messaging, knowledge, web, reminders (< 1 ms)
        from jarvis.core.router.extended import match_extended
        ext_decision = match_extended(routing_text if positive_override else original_text, request_id)
        if ext_decision:
            ext_decision.routing_ms = (perf_counter_ns() - t0) / 1e6
            ext_decision.breakdown_ms = breakdown
            self._record(ext_decision)
            return ext_decision

        # 3c. DIRECT SHELL / TERMINAL COMMAND CHECK (< 0.5 ms)
        orig_stripped = original_text.strip()
        cmd_match = re.match(r"^(?:cmd:|cmd\s+|powershell:|powershell\s+|ps:|ps\s+|run:|exec:|exec\s+|sh:\s*)(.+)$", orig_stripped, re.IGNORECASE)
        shell_cmd = None
        if cmd_match:
            shell_cmd = cmd_match.group(1).strip()
        elif routing_text:
            first_tok = routing_text.split()[0].lower()
            if first_tok in KNOWN_SHELL_COMMANDS:
                shell_cmd = orig_stripped

        if shell_cmd:
            cmd_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="powershell_command",
                slots={"command": shell_cmd},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=shell_cmd,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, cmd_decision, self.registry_version)
            self._record(cmd_decision)
            return cmd_decision

        if re.match(r"^(?:re-pair whatsapp|repair whatsapp|pair whatsapp|whatsapp pairing code)$", clean_lower):
            wa_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="whatsapp_action",
                slots={"action": "pair"},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wa_decision, self.registry_version)
            self._record(wa_decision)
            return wa_decision

        if re.match(r"^(?:connect whatsapp|reconnect whatsapp)$", clean_lower):
            wa_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="whatsapp_action",
                slots={"action": "connect"},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wa_decision, self.registry_version)
            self._record(wa_decision)
            return wa_decision

        if re.match(r"^(?:disconnect whatsapp)$", clean_lower):
            wa_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="whatsapp_action",
                slots={"action": "disconnect"},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wa_decision, self.registry_version)
            self._record(wa_decision)
            return wa_decision

        if re.match(r"^(?:cancel|cancel task|stop task)$", clean_lower):
            cancel_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.CONTROL,
                intent="cancel_task",
                slots={"action": "cancel"},
                confidence=1.0,
                source=RouteSource.CONTROL,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.CONTROL_COMMAND,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, cancel_decision, self.registry_version)
            self._record(cancel_decision)
            return cancel_decision

        if re.match(r"^(?:stop speaking|stop talking|stop speech|stop voice|stop audio|be quiet|silence|shut up)$", clean_lower):
            stop_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.CONTROL,
                intent="stop_speaking",
                slots={},
                confidence=1.0,
                source=RouteSource.CONTROL,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.CONTROL_COMMAND,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, stop_decision, self.registry_version)
            self._record(stop_decision)
            return stop_decision

        if re.match(r"^(?:restore|restore window|unmaximize|unminimize)$", clean_lower):
            restore_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="restore_window",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, restore_dec, self.registry_version)
            self._record(restore_dec)
            return restore_dec

        # Volume Mute / Silence
        if re.search(r"\b(?:silence|mute)\b", clean_lower) and not re.search(r"\b(?:unmute|un[- ]?silence)\b", clean_lower) and any(w in clean_lower for w in ("sound", "audio", "volume", "speakers", "speaker", "completely", "please", "mute")):
            mute_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="volume_mute",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, mute_dec, self.registry_version)
            self._record(mute_dec)
            return mute_dec

        # Volume Unmute / Restore audio
        if re.search(r"\b(?:unmute|un[- ]?silence)\b", clean_lower) or (any(w in clean_lower for w in ("sound", "audio", "speakers", "speaker", "playback")) and "back on" in clean_lower):
            unmute_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="volume_unmute",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, unmute_dec, self.registry_version)
            self._record(unmute_dec)
            return unmute_dec

        # Window management: Close window / Dismiss window / Send to taskbar
        if re.search(r"\b(?:close|dismiss|shut)\s+(?:the\s+)?(?:open\s+)?(?:top\s+|active\s+|current\s+)?window\b", clean_lower):
            win_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="close_window",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, win_dec, self.registry_version)
            self._record(win_dec)
            return win_dec

        if re.search(r"\b(?:send|minimize)(?:\s+(?:the\s+)?active\s+(?:app|window))?\s+to\s+(?:the\s+)?taskbar\b", clean_lower):
            min_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="minimize_window",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, min_dec, self.registry_version)
            self._record(min_dec)
            return min_dec

        # Window management: Maximize window / Fullscreen
        if re.match(
            r"^(?:please\s+)?(?:maximize(?:\s+(?:the\s+)?(?:active\s+|current\s+|this\s+)?window)?|max(?:\s+window)?|ful+[\s-]*screen(?:\s+(?:this\s+|the\s+)?(?:active\s+|current\s+)?window)?|(?:make\s+(?:it\s+|this\s+|the\s+window\s+)?|go\s+|enter\s+|toggle\s+)?ful+[\s-]*screen)$",
            clean_lower,
        ) and not any(w in clean_lower for w in ("grab", "shot", "capture", "take", "save", "record", "snip")):
            max_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="maximize_window",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, max_dec, self.registry_version)
            self._record(max_dec)
            return max_dec

        # Phone screen mirror
        if re.search(r"\b(?:mirror|screen\s+mirror)(?:\s+my)?(?:\s+android)?(?:\s+phone)?\b|\bphone\s+(?:screen\s+)?mirror\b", clean_lower):
            mirror_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="android_open_control",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, mirror_dec, self.registry_version)
            self._record(mirror_dec)
            return mirror_dec

        # WhatsApp Status Check
        if re.search(r"\bwhatsapp\b.+(?:connected|bridge|connector|live|status)\b", clean_lower):
            wa_status_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="whatsapp_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wa_status_dec, self.registry_version)
            self._record(wa_status_dec)
            return wa_status_dec

        # Battery / WiFi / Time
        if re.search(r"\bbattery(?:\s+percentage|\s+health|\s+level|\s+status)?\b", clean_lower):
            if any(p in clean_lower for p in ("phone", "android", "mobile", "cell")):
                bat_intent = "android_status"
            else:
                bat_intent = "battery_status"
            bat_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent=bat_intent,
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, bat_dec, self.registry_version)
            self._record(bat_dec)
            return bat_dec

        if re.search(r"\b(?:wi-?fi|network\s+connection|wi-?fi\s+connection)\b(?!\s+(?:password|passcode|pin|key|name|code))", clean_lower) \
                and not re.search(r"\b(?:password|passcode)\b", clean_lower):
            wifi_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="wifi_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wifi_dec, self.registry_version)
            self._record(wifi_dec)
            return wifi_dec

        if re.search(r"\b(?:system\s+clock|what\s+time\s+is\s+it|current\s+time|get\s+time)\b", clean_lower):
            time_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="get_time",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, time_dec, self.registry_version)
            self._record(time_dec)
            return time_dec


        if re.match(r"^(?:show |check |get )?(?:microphone|mic) status$|^(?:is |check )?(?:the )?mic(?:rophone)? working$|^(?:test |check )?(?:the )?mic(?:rophone)?$", clean_lower):
            mic_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="microphone_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, mic_decision, self.registry_version)
            self._record(mic_decision)
            return mic_decision

        if re.match(r"^(?:show |check |get )?(?:speech recognition|speech to text|stt|whisper) status$|^(?:is |check )?(?:the )?speech recognition (?:working|active|ready)$", clean_lower):
            stt_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="speech_recognition_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, stt_decision, self.registry_version)
            self._record(stt_decision)
            return stt_decision

        if re.match(r"^(?:show |check |get )?(?:wake word|wakeword|openwakeword) status$|^(?:is |check )?(?:the )?wake word (?:active|working|listening|ready)$", clean_lower):
            wake_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="wake_word_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wake_decision, self.registry_version)
            self._record(wake_decision)
            return wake_decision

        if re.match(r"^(?:show |check |get |list )?(?:connected |audio |hardware )?devices$|^(?:show |list )?(?:connected )?hardware$", clean_lower):
            dev_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="connected_devices",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, dev_decision, self.registry_version)
            self._record(dev_decision)
            return dev_decision

        # Screen capture / Screenshot Fast Path
        if re.match(r"^(?:please )?(?:take (?:a )?screenshot|capture (?:my |the )?screen(?: right now)?|screenshot(?: right now)?|screen grab|screen capture)$", clean_lower):
            shot_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="take_screenshot",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, shot_decision, self.registry_version)
            self._record(shot_decision)
            return shot_decision

        # Brightness Fast Paths
        m_bright = re.match(
            r"^(?:turn |set )?(?:the )?(?:screen |display )?brightness (?:level )?(?:down to |up to |to |at )?(?P<pct>\d+)(?:%| percent)?$"
            r"|^dim (?:the )?(?:screen |display )?(?:brightness )?(?:to |down to )?(?P<pct2>\d+)(?:%| percent)?$",
            clean_lower,
        )
        if m_bright:
            val = int(m_bright.group("pct") or m_bright.group("pct2"))
            bright_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="brightness_set",
                slots={"percent": val},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, bright_dec, self.registry_version)
            self._record(bright_dec)
            return bright_dec

        if re.match(r"^(?:what is |check |show |get )?(?:the )?(?:screen |display )?brightness(?: level)?$|^brightness$", clean_lower):
            bright_get_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="brightness_get",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, bright_get_dec, self.registry_version)
            self._record(bright_get_dec)
            return bright_get_dec

        # Top Memory Consuming Processes
        if re.match(r"^(?:please )?(?:which (?:programs?|apps?|applications?|processes?) (?:are using|use|consume|take) the most (?:memory|ram)|what (?:programs?|apps?|processes?) (?:are using|use) the most (?:memory|ram)|what is using the most (?:memory|ram)|top (?:memory|ram) (?:processes|programs|apps|applications)|memory hogs)$", clean_lower):
            top_mem_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="top_memory_processes",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, top_mem_dec, self.registry_version)
            self._record(top_mem_dec)
            return top_mem_dec

        if re.match(r"^(?:please )?(?:memory status|working memory|check (?:the )?(?:memory|ram)|(?:how much )?(?:memory|ram)(?: is)? (?:currently )?(?:available|free|used)(?: on this pc)?)$", clean_lower):
            mem_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="system_info",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, mem_decision, self.registry_version)
            self._record(mem_decision)
            return mem_decision

        m_see_folder = re.match(r"^(?:can i |could i |let me )?(?:see|view|check|look at)(?: my| the)? (downloads|desktop|documents|pictures|videos)(?: folder)?$|^(?:show )(?:my |the )?(downloads|documents|pictures|videos)(?: folder)?$|^(?:show )(?:my |the )?desktop folder$", clean_lower)
        if m_see_folder:
            f_name = (m_see_folder.group(1) or m_see_folder.group(2) or "desktop").lower()
            from jarvis.core.router.slots import FOLDER_ALIASES
            resolved_path = FOLDER_ALIASES.get(f_name, f"~/{f_name.capitalize()}")
            from pathlib import Path
            actual_path = str(Path(resolved_path).expanduser().resolve())
            see_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="list_directory",
                slots={"path": actual_path, "limit": 100},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, see_dec, self.registry_version)
            self._record(see_dec)
            return see_dec

        # Application Discovery & Management Fast Paths
        if re.match(r"^(?:please )?(?:refresh|rescan|reload|update) (?:my )?(?:installed )?(?:applications|apps|software)$|^(?:refresh|rescan|reload) (?:apps|applications)$", clean_lower):
            ref_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="refresh_applications",
                slots={"force": True},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, ref_decision, self.registry_version)
            self._record(ref_decision)
            return ref_decision

        if re.match(r"^(?:please )?(?:show|list|display|get) (?:all |my )?(?:installed )?(?:applications|apps|programs|software)$|^what (?:applications|apps|software|programs) (?:are|do i have) installed$|^(?:show |list )?(?:installed )?(?:applications|apps)$", clean_lower):
            list_app_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="list_installed_applications",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, list_app_decision, self.registry_version)
            self._record(list_app_decision)
            return list_app_decision

        m_is_inst = re.match(r"^(?:is|check if) (.+?) (?:is )?installed(?: on (?:my|this) (?:pc|computer))?$|^do i have (.+?) installed(?: on (?:my|this) (?:pc|computer))?$", clean_lower)
        if m_is_inst:
            target_app = (m_is_inst.group(1) or m_is_inst.group(2)).strip()
            check_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="check_app_installed",
                slots={"name": target_app},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, check_decision, self.registry_version)
            self._record(check_decision)
            return check_decision

        m_where_inst = re.match(
            r"^where (?:is|did|was) (.+?) (?:get )?installed(?: at)?$"
            r"|^(?:what is the |show me the |get )?(?:path|location|directory) (?:for|of) (.+?)$"
            r"|^where is the (.+?) executable(?: located)?$"
            r"|^give me the (?:file system )?location of (.+?)$"
            r"|^where on disk (?:can i find|is) (.+?)$",
            clean_lower,
        )
        if m_where_inst:
            target_app = (
                m_where_inst.group(1)
                or m_where_inst.group(2)
                or m_where_inst.group(3)
                or m_where_inst.group(4)
                or m_where_inst.group(5)
            ).strip()
            loc_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="get_app_location",
                slots={"name": target_app},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, loc_decision, self.registry_version)
            self._record(loc_decision)
            return loc_decision

        m_install = re.match(r"^(?:please )?(?:install|setup|download and install) ([a-zA-Z0-9_\-\.\s]+?)(?: using winget| via winget)?$", clean_lower)
        if m_install:
            app_to_install = m_install.group(1).strip()
            # If app_to_install is pronoun or reference, resolve through reference resolver
            if app_to_install in ("it", "that", "this", "that one", "this one", "them", "the app", "the software", "the first one", "the second one") and self.reference_resolver:
                res = self.reference_resolver.resolve_for_slot(clean_lower, expected_slot_type="package", intent="app.install_software")
                if res.confidence == ReferenceConfidence.AMBIGUOUS:
                    ambig_dec = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.CLARIFY,
                        intent="clarify",
                        slots={},
                        confidence=0.5,
                        clarification=res.clarification_prompt or "Which application do you want me to install?",
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=clean_lower,
                        reason_code=ReasonCode.AMBIGUOUS_TOP_TWO,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(ambig_dec)
                    return ambig_dec
                elif res.referent and res.confidence == ReferenceConfidence.HIGH:
                    app_to_install = str(res.referent)

            install_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="install_software",
                slots={"name": app_to_install},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, install_decision, self.registry_version)
            self._record(install_decision)
            return install_decision

        # 4. QUESTION / INFORMATIONAL GUARD
        if is_informational_or_question(original_text, routing_text):
            # Extract entities from question and track active topic (Sections 5, 6, 14, 16)
            ents = EntityExtractor.extract_from_utterance(original_text)
            if ents and self.working_memory:
                for ent in ents:
                    self.working_memory.record_entity(ent)
                if len(ents) == 1:
                    self.working_memory.push_topic(ents[0])
                else:
                    if hasattr(self.working_memory, "clear_active_topic"):
                        self.working_memory.clear_active_topic()
                    elif hasattr(self.working_memory, "context"):
                        self.working_memory.context.active_topic = None

            # Check if this is an informational query on an active document ("What is it about?", "Summarize it")
            if any(q in clean_lower for q in ("what's it about", "what is it about", "what does it talk about", "summarize it")):
                if self.reference_resolver:
                    res = self.reference_resolver.resolve("what is it about")
                    if res.referent and res.confidence == ReferenceConfidence.HIGH:
                        doc_qa_dec = RouteDecision(
                            request_id=request_id,
                            lane=RouteLane.LANE_0,
                            intent="document_qa",
                            slots={"path": str(res.referent), "query": original_text},
                            confidence=1.0,
                            source=RouteSource.EXACT,
                            complexity=ComplexityLevel.SIMPLE,
                            normalized_text=clean_lower,
                            reason_code=ReasonCode.EXACT_PATTERN,
                            routing_ms=(perf_counter_ns() - t0) / 1e6,
                            breakdown_ms=breakdown,
                        )
                        self._record(doc_qa_dec)
                        return doc_qa_dec

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
        candidate_names = self.catalog.retrieve_candidate_intents(tokens, max_candidates=16)
        breakdown["candidate_generation_ms"] = (perf_counter_ns() - t_cand_0) / 1e6

        # 6a. AMBIGUITY & GENERIC ENTITY CHECK
        from jarvis.core.router.disambiguation import disambiguate_generic_request
        generic_ambig = disambiguate_generic_request(routing_text, self.working_memory, request_id)
        if generic_ambig:
            generic_ambig.routing_ms = (perf_counter_ns() - t0) / 1e6
            generic_ambig.breakdown_ms = breakdown
            self._record(generic_ambig)
            return generic_ambig

        # 6b. COMPLEXITY GATE (Phase 4 / Lane 2 Escalation)
        t_gate_0 = perf_counter_ns()
        gate_dec = check_complexity_gate(routing_text, request_id)
        breakdown["complexity_gate_ms"] = (perf_counter_ns() - t_gate_0) / 1e6
        if gate_dec:
            gate_dec.routing_ms = (perf_counter_ns() - t0) / 1e6
            gate_dec.breakdown_ms = breakdown
            self._record(gate_dec)
            return gate_dec

        # 7. DETERMINISTIC COMPOUND COMMAND CHECK (e.g. "open chrome and calculator" or multi-action clauses)
        if any(sep in routing_text for sep in (" and ", " & ", ",", ";", " then ")):

            compound = check_deterministic_compound(routing_text, self.catalog, request_id)
            if compound:
                compound.routing_ms = (perf_counter_ns() - t0) / 1e6
                compound.breakdown_ms = breakdown
                self.cache.put(routing_text, compound, self.registry_version)
                self._record(compound)
                return compound

        # 7b. CONTEXTUAL PRONOUN & REFERENT RESOLUTION (< 0.2 ms)
        if self.reference_resolver and any(p in routing_text for p in ("open it", "open that", "close it", "close that", "run it")):
            res = self.reference_resolver.resolve(routing_text)
            if res and res.confidence.value in ("HIGH", "high") and res.referent:
                intent_target = "open_file" if res.referent_type == "FILE" else "open_app"
                slot_key = "path" if res.referent_type == "FILE" else "name"
                if "close" in routing_text:
                    intent_target = "close_app"
                    slot_key = "name"
                ref_dec = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent=intent_target,
                    slots={slot_key: str(res.referent)},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=routing_text,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(ref_dec)
                return ref_dec

        # 8. EXACT & GRAMMAR PATTERN MATCH
        t_pat_0 = perf_counter_ns()
        pattern_match = match_patterns(routing_text, candidate_names, self.catalog, request_id)
        breakdown["pattern_match_ms"] = (perf_counter_ns() - t_pat_0) / 1e6
        if pattern_match:
            # Resolve relative folder references if list_directory
            if pattern_match.intent == "list_directory" and pattern_match.slots.get("path") in ("that folder", "the folder", "same folder", "that directory", "same directory") and self.reference_resolver:
                res = self.reference_resolver.resolve(str(pattern_match.slots["path"]))
                if res and res.referent:
                    pattern_match.slots["path"] = str(res.referent)

            # Check app disambiguation if open_app
            if pattern_match.intent == "open_app" and "name" in pattern_match.slots:
                ambig = disambiguate_app(pattern_match.slots["name"], self.app_resolver, request_id, routing_text)
                if ambig:
                    ambig.routing_ms = (perf_counter_ns() - t0) / 1e6
                    ambig.breakdown_ms = breakdown
                    self._record(ambig)
                    return ambig

            # Check generic file deletion/opening safety
            if pattern_match.intent in ("delete_file", "open_file") and pattern_match.slots.get("path") in ("the file", "the document", "the pdf", "the spreadsheet", "the report", "file", "document"):
                ambig_file = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CLARIFY,
                    intent="clarify",
                    slots={},
                    confidence=0.5,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    clarification=f"Which file would you like me to {pattern_match.intent.split('_')[0]}?",
                    normalized_text=routing_text,
                    reason_code=ReasonCode.LOW_CONFIDENCE,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(ambig_file)
                return ambig_file

            # Check send_whatsapp_message without message body
            if pattern_match.intent == "send_whatsapp_message" and not pattern_match.slots.get("message"):
                ambig_msg = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CLARIFY,
                    intent="clarify",
                    slots=pattern_match.slots,
                    confidence=0.5,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    clarification=f"What message would you like to send to {pattern_match.slots.get('recipient', 'the recipient')}?",
                    normalized_text=routing_text,
                    reason_code=ReasonCode.LOW_CONFIDENCE,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(ambig_msg)
                return ambig_msg

            pattern_match.routing_ms = (perf_counter_ns() - t0) / 1e6
            pattern_match.breakdown_ms = breakdown
            if pattern_match.lane == RouteLane.LANE_0:
                self.cache.put(routing_text, pattern_match, self.registry_version)
            self._record(pattern_match)
            return pattern_match

        # 8b. DIRECT APP / TARGET RESOLUTION (e.g. "chrome", "notepad", "calc", "youtube", Start menu apps)
        if len(tokens) <= 4:
            from jarvis.tools.system.app_resolver import ALIASES, SYNONYMS, WEB_SERVICES
            direct_name = None
            if routing_text in ALIASES or routing_text in SYNONYMS or routing_text in WEB_SERVICES:
                direct_name = routing_text
            elif self.app_resolver:
                try:
                    if routing_text in getattr(self.app_resolver, "cache", {}):
                        direct_name = routing_text
                    elif hasattr(self.app_resolver, "resolve"):
                        target = self.app_resolver.resolve(routing_text)
                        if target:
                            direct_name = routing_text
                except Exception:
                    pass

            if direct_name:
                app_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent="open_app",
                    slots={"name": direct_name},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=routing_text,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self.cache.put(routing_text, app_decision, self.registry_version)
                self._record(app_decision)
                return app_decision

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

        # 10.5. LANE 0.75: SEMANTIC CAPABILITY RETRIEVAL & SLOT EXTRACTION (< 1 ms)
        t_cap_0 = perf_counter_ns()
        from jarvis.core.capabilities.slot_extractor import extract_slots
        top_caps = self.capability_retriever.retrieve(routing_text, top_k=3, min_score=6.0)
        breakdown["capability_retrieval_ms"] = (perf_counter_ns() - t_cap_0) / 1e6
        if top_caps:
            best_cap, score = top_caps[0]
            second_score = top_caps[1][1] if len(top_caps) > 1 else 0.0
            if score >= 8.5 or (score >= 6.0 and (score - second_score) >= 2.5):
                slots, missing = extract_slots(best_cap, routing_text, self.working_memory, self.reference_resolver)
                if not missing:
                    cap_dec = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent=best_cap.target_tool,
                        slots=slots,
                        confidence=min(1.0, score / 20.0),
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=routing_text,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self.cache.put(routing_text, cap_dec, self.registry_version)
                    self._record(cap_dec)
                    return cap_dec
                elif score >= 12.0:
                    from jarvis.core.router.ollama import DisabledProvider
                    if isinstance(self.llm_provider, DisabledProvider):
                        slot_names = ", ".join(missing)
                        clarification = f"Could you please specify the {slot_names} to {best_cap.description.lower().rstrip('.')}?"
                        clarify_dec = RouteDecision(
                            request_id=request_id,
                            lane=RouteLane.CLARIFY,
                            intent=best_cap.target_tool,
                            slots=slots,
                            confidence=0.5,
                            source=RouteSource.EXACT,
                            complexity=ComplexityLevel.SIMPLE,
                            clarification=clarification,
                            normalized_text=routing_text,
                            reason_code=ReasonCode.LOW_CONFIDENCE,
                            candidate_count=len(top_caps),
                            routing_ms=(perf_counter_ns() - t0) / 1e6,
                            breakdown_ms=breakdown,
                        )
                        self._record(clarify_dec)
                        return clarify_dec

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
                clarification=f"classifier_error: {type(exc).__name__}",
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

        # If unclassified by tiny model, escalate to Lane 0 or Lane 2 if capabilities match
        if llm_decision.lane == RouteLane.CLARIFY and not llm_decision.intent:
            sem_caps = self.capability_retriever.retrieve(routing_text, top_k=2, min_score=6.0)
            if sem_caps:
                best_cap, score = sem_caps[0]
                if score >= 6.0:
                    from jarvis.core.capabilities.slot_extractor import extract_slots
                    slots, missing = extract_slots(best_cap, routing_text, self.working_memory, self.reference_resolver)
                    if not missing:
                        llm_decision = RouteDecision(
                            request_id=request_id,
                            lane=RouteLane.LANE_0,
                            intent=best_cap.target_tool,
                            slots=slots,
                            confidence=min(1.0, score / 20.0),
                            source=RouteSource.EXACT,
                            complexity=ComplexityLevel.SIMPLE,
                            normalized_text=routing_text,
                            reason_code=ReasonCode.EXACT_PATTERN,
                            routing_ms=(perf_counter_ns() - t0) / 1e6,
                            breakdown_ms=breakdown,
                        )
                        self.cache.put(routing_text, llm_decision, self.registry_version)
                        self._record(llm_decision)
                        return llm_decision

            # If multi-step or planner required
            if not _llm_down(llm_decision):
                sem_caps_low = self.capability_retriever.retrieve(routing_text, top_k=1, min_score=4.0)
                if sem_caps_low:
                    llm_decision = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_2,
                        intent=None,
                        slots={},
                        confidence=0.85,
                        source=RouteSource.COMPLEXITY_GATE,
                        complexity=ComplexityLevel.COMPLEX,
                        needs_planner=True,
                        normalized_text=routing_text,
                        reason_code=ReasonCode.MULTI_STEP,
                    )

        # If LLM classified as unknown or clarify, route to dynamic Ollama chat unless model is unavailable or disabled!
        from jarvis.core.router.ollama import DisabledProvider
        if not isinstance(self.llm_provider, DisabledProvider) and llm_decision.lane == RouteLane.CLARIFY and not llm_decision.intent and not _llm_down(llm_decision):
            llm_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="ollama_chat",
                slots={"query": original_text},
                confidence=0.95,
                source=RouteSource.TINY_MODEL,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=routing_text,
                reason_code=ReasonCode.LLM_CLASSIFIED,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
                # Not a question and no single tool matched: the service hands this to the tool-using agent.
                context_trace={"fallback": "unknown_command"},
            )

        self._record(llm_decision)
        return llm_decision

    def _record(self, decision: RouteDecision):
        self.total_routed += 1
        if decision.lane.value in self.lane_counts:
            self.lane_counts[decision.lane.value] += 1
        if decision.lane == RouteLane.CLARIFY and "candidates" in decision.slots:
            self.last_clarification_candidates = list(decision.slots["candidates"])
            self.last_clarification_intent = str(decision.intent or "open_app")
        if self.trace_debug:
            print(
                f"[ROUTER TRACE] text='{decision.normalized_text}' lane={decision.lane} "
                f"intent={decision.intent} src={decision.source} ms={decision.routing_ms:.3f}ms",
                flush=True,
            )
