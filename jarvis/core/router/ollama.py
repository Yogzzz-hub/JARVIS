import copy
import json
import time
from collections import OrderedDict
from typing import Any, Protocol
from jarvis.core.router.catalog import IntentDefinition
from jarvis.core.router.models import (
    RouteDecision,
    RouteLane,
    RouteSource,
    ComplexityLevel,
    ReasonCode,
)

CLASSIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": ["string", "null"]},
        "slots": {"type": "object"},
        "missing_slots": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "is_multi_step": {"type": "boolean"},
        "is_command": {"type": "boolean"},
        "unknown": {"type": "boolean"},
    },
    "required": [
        "intent",
        "slots",
        "missing_slots",
        "confidence",
        "is_multi_step",
        "is_command",
        "unknown",
    ],
}

class LLMProvider(Protocol):
    async def classify(
        self,
        text: str,
        candidate_intents: list[IntentDefinition],
        request_id: str,
    ) -> RouteDecision:
        ...

CLASSIFIER_SYSTEM_PROMPT = (
    "You are the intent classifier of JARVIS, a voice assistant that controls a Windows PC, "
    "an Android phone and WhatsApp. Map the user's utterance to exactly ONE tool from the list, "
    "and extract its arguments using the exact argument names shown. Rules:\n"
    "- Choose intent \"none\" and unknown=true for questions, chit-chat, or anything no tool does.\n"
    "- Set is_multi_step=true when the request needs two or more different actions in sequence.\n"
    "- Never invent argument values; list required arguments you could not find in missing_slots.\n"
    "- Speech-recognition errors are common: interpret misheard words by meaning (\"crome\" = chrome).\n"
    "- confidence is your probability (0-1) that the chosen tool and arguments are correct.\n"
    "- Only use tool names from the list you are given; the examples below only show the format.\n"
    "Examples:\n"
    "\"could you fire up crome\" -> {\"intent\": \"open_app\", \"slots\": {\"name\": \"chrome\"}, \"missing_slots\": [], "
    "\"confidence\": 0.93, \"is_multi_step\": false, \"is_command\": true, \"unknown\": false}\n"
    "\"message priya that I'm running late\" -> {\"intent\": \"send_whatsapp_message\", \"slots\": {\"recipient\": \"priya\", "
    "\"message\": \"I'm running late\"}, \"missing_slots\": [], \"confidence\": 0.9, \"is_multi_step\": false, "
    "\"is_command\": true, \"unknown\": false}\n"
    "\"why is the sky blue\" -> {\"intent\": \"none\", \"slots\": {}, \"missing_slots\": [], \"confidence\": 0.95, "
    "\"is_multi_step\": false, \"is_command\": false, \"unknown\": true}\n"
    "\"download the report and email it to my boss\" -> {\"intent\": \"none\", \"slots\": {}, \"missing_slots\": [], "
    "\"confidence\": 0.8, \"is_multi_step\": true, \"is_command\": true, \"unknown\": false}"
)


class OllamaProvider:
    """Lane 1 classifier: a small local model picks one registered tool and fills its arguments.

    The JSON schema constrains ``intent`` to the retrieved candidate tools, so the model cannot
    hallucinate a capability; arguments are then validated against the tool's real input model.
    """

    MIN_CONFIDENCE = 0.45

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 20.0,
        capability_retriever: Any = None,
        capability_registry: Any = None,
        client: Any = None,
        tool_registry: Any = None,
        role: str = "fast",
    ):
        from jarvis.core.llm.client import LLMSettings, OllamaClient, get_llm, normalize_base_url

        if client is None and base_url:
            client = OllamaClient(LLMSettings(base_url=normalize_base_url(base_url), fast_model=model or ""))
        self._client = client
        self._get_llm = get_llm
        self.model = model
        self.role = role
        self.timeout = timeout
        self.capability_retriever = capability_retriever
        self.capability_registry = capability_registry
        self.tool_registry = tool_registry
        self._cache: "OrderedDict[tuple, tuple[float, Any]]" = OrderedDict()

    @property
    def client(self):
        return self._client or self._get_llm()

    # ------------------------------------------------------------------ result cache
    # Repeated phrasings ("open my mail", "pause music") are classified once; temperature is 0,
    # so the answer for the same text and candidate set is deterministic anyway.
    CACHE_SIZE = 256
    CACHE_TTL_S = 900.0

    def _cache_get(self, key):
        entry = self._cache.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > self.CACHE_TTL_S:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return copy.deepcopy(value)

    def _cache_put(self, key, value) -> None:
        self._cache[key] = (time.monotonic(), copy.deepcopy(value))
        self._cache.move_to_end(key)
        while len(self._cache) > self.CACHE_SIZE:
            self._cache.popitem(last=False)

    @property
    def base_url(self) -> str:
        return self.client.base_url

    # ------------------------------------------------------------------ candidates
    def _candidates(self, text: str, catalog_candidates: list[IntentDefinition]) -> list[dict[str, Any]]:
        """Merge catalog intents, capability retrieval and tool retrieval into described candidates."""
        from jarvis.core.llm.tool_catalog import argument_spec, select_tools

        out: dict[str, dict[str, Any]] = {}

        def add_tool(tool_name: str, examples: tuple[str, ...] = ()) -> None:
            if not tool_name or tool_name in out:
                return
            if self.tool_registry is not None and not self.tool_registry.contains(tool_name):
                return
            entry: dict[str, Any] = {"name": tool_name, "description": tool_name.replace("_", " "), "args": {}, "required": [], "examples": list(examples[:2])}
            if self.tool_registry is not None:
                tool = self.tool_registry.get(tool_name)
                fields, required = argument_spec(tool.definition.input_model)
                entry.update(description=tool.definition.description.split("\n")[0][:160], args=fields, required=required)
            out[tool_name] = entry

        for cand in catalog_candidates[:8]:
            add_tool(getattr(cand, "tool", "") or cand.name, tuple(getattr(cand, "examples", ()) or ()))
        if self.capability_retriever is not None:
            try:
                for cap, _score in self.capability_retriever.retrieve(text, top_k=6, min_score=2.0):
                    add_tool(cap.target_tool, tuple(cap.examples or ()))
            except Exception:
                pass
        if self.tool_registry is not None:
            for tool in select_tools(text, self.tool_registry, top_k=8):
                add_tool(tool.definition.name)
        if not out and self.tool_registry is None:
            for cand in catalog_candidates:
                out[cand.name] = {"name": cand.name, "description": cand.name.replace("_", " "), "args": {s: "string" for s in cand.required_slots}, "required": list(cand.required_slots), "examples": list(cand.examples[:2])}
        return list(out.values())[:14]

    def _build_prompt(self, text: str, candidates: list[IntentDefinition]) -> str:
        """Backwards-compatible single-string prompt (used by diagnostics and older tests)."""
        described = self._candidates(text, candidates)
        return self._render(text, described)

    @staticmethod
    def _render(text: str, described: list[dict[str, Any]]) -> str:
        lines = []
        for c in described:
            args = "; ".join(f"{k}{'*' if k in c['required'] else ''}: {v}" for k, v in c["args"].items()) or "none"
            ex = f" e.g. {c['examples'][0]!r}" if c.get("examples") else ""
            lines.append(f"- {c['name']}: {c['description']} | args: {args}{ex}")
        tools_block = "\n".join(lines) if lines else "- (no tools matched)"
        return f"Tools (* = required argument):\n{tools_block}\n\nUser utterance: \"{text}\""

    @staticmethod
    def _schema(names: list[str]) -> dict[str, Any]:
        schema = json.loads(json.dumps(CLASSIFIER_SCHEMA))
        schema["properties"]["intent"] = {"type": "string", "enum": names + ["none"]}
        return schema

    # ------------------------------------------------------------------ fallbacks
    def _semantic_rescue(self, request_id: str, text: str, total_ms: float, breakdown: dict[str, float]) -> RouteDecision | None:
        if not self.capability_retriever:
            return None
        try:
            from jarvis.core.capabilities.slot_extractor import extract_slots
            sem_caps = self.capability_retriever.retrieve(text, top_k=2, min_score=6.0)
            if sem_caps:
                best_cap, score = sem_caps[0]
                slots, missing = extract_slots(best_cap, text)
                if not missing:
                    return RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent=best_cap.target_tool,
                        slots=slots,
                        confidence=min(1.0, score / 20.0),
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=text,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=total_ms,
                        breakdown_ms=breakdown,
                    )
        except Exception:
            pass
        return None

    def _map_intent(self, intent: str) -> str:
        from jarvis.core.capabilities.canonical import to_canonical
        if self.tool_registry is not None and self.tool_registry.contains(intent):
            return intent
        canon = to_canonical(intent)
        if self.capability_registry:
            cap_def = self.capability_registry.get(canon)
            if cap_def and cap_def.target_tool:
                return cap_def.target_tool
        legacy = {
            "whatsapp.send": "send_whatsapp_message",
            "phone.mirror_open": "android_open_control",
            "phone.mirror_close": "android_close_control",
            "phone.status": "android_status",
        }
        return legacy.get(canon, intent)

    # ------------------------------------------------------------------ classify
    async def classify(
        self,
        text: str,
        candidate_intents: list[IntentDefinition],
        request_id: str,
    ) -> RouteDecision:
        from jarvis.core.llm.client import LLMUnavailable
        from jarvis.core.llm.tool_catalog import filter_arguments

        t0 = time.perf_counter_ns()
        breakdown: dict[str, float] = {}
        described = self._candidates(text, candidate_intents)
        names = [c["name"] for c in described]
        messages = [
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": self._render(text, described)},
        ]
        model_used = self.model
        cache_key = (" ".join(text.lower().split()), tuple(names))
        try:
            cached = self._cache_get(cache_key)
            if cached is not None:
                parsed, model_used = cached
                breakdown["classifier_cache_hit"] = 1.0
            else:
                result = await self.client.chat(
                    messages,
                    role=self.role,
                    model=self.model,
                    schema=self._schema(names),
                    temperature=0.0,
                    max_tokens=220,
                    timeout=self.timeout,
                )
                model_used = result.model
                breakdown.update({f"model_{k}": v for k, v in result.timings_ms.items()})
                parsed = result.data if isinstance(result.data, dict) else {}
                if parsed:
                    self._cache_put(cache_key, (parsed, model_used))

            intent = parsed.get("intent")
            if intent in ("none", "null", ""):
                intent = None
            slots = parsed.get("slots") or {}
            if not isinstance(slots, dict):
                slots = {}
            try:
                confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.7))))
            except (TypeError, ValueError):
                confidence = 0.5
            is_multi_step = bool(parsed.get("is_multi_step", False))
            is_command = bool(parsed.get("is_command", True))
            unknown = bool(parsed.get("unknown", False))
            missing_slots = [m for m in (parsed.get("missing_slots") or []) if isinstance(m, str)]

            if intent:
                intent = self._map_intent(intent)
                if self.tool_registry is not None and self.tool_registry.contains(intent):
                    tool = self.tool_registry.get(intent)
                    slots, missing_required = filter_arguments(tool, slots)
                    missing_slots = sorted(set(missing_required))
            total_ms = (time.perf_counter_ns() - t0) / 1e6

            # 1. Multi-step request detected
            if is_multi_step:
                return RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_2,
                    intent=None,
                    slots={},
                    confidence=confidence,
                    source=RouteSource.TINY_MODEL,
                    complexity=ComplexityLevel.COMPLEX,
                    needs_planner=True,
                    normalized_text=text,
                    model_used=model_used,
                    routing_ms=total_ms,
                    reason_code=ReasonCode.MULTI_STEP,
                    breakdown_ms=breakdown,
                )

            # 2. Unknown, not a command, or too uncertain to act on
            if unknown or not is_command or intent is None or confidence < self.MIN_CONFIDENCE:
                rescued = self._semantic_rescue(request_id, text, total_ms, breakdown)
                if rescued:
                    return rescued
                return RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CLARIFY,
                    intent=None,
                    slots={},
                    confidence=confidence,
                    source=RouteSource.TINY_MODEL,
                    complexity=ComplexityLevel.SIMPLE,
                    clarification="I'm not sure how to handle that request. Could you rephrase it?",
                    normalized_text=text,
                    model_used=model_used,
                    routing_ms=total_ms,
                    reason_code=ReasonCode.UNKNOWN_INTENT,
                    breakdown_ms=breakdown,
                )

            # 3. Missing required arguments
            if missing_slots:
                pretty = missing_slots[0].replace("_", " ")
                return RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CLARIFY,
                    intent=intent,
                    slots=slots,
                    confidence=confidence,
                    source=RouteSource.TINY_MODEL,
                    complexity=ComplexityLevel.SIMPLE,
                    missing_slots=missing_slots,
                    clarification=f"Please tell me the {pretty} for that.",
                    normalized_text=text,
                    model_used=model_used,
                    routing_ms=total_ms,
                    reason_code=ReasonCode.MISSING_REQUIRED_SLOT,
                    breakdown_ms=breakdown,
                )

            # 4. Valid Lane 1 classification
            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_1,
                intent=intent,
                slots=slots,
                confidence=confidence,
                source=RouteSource.TINY_MODEL,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=text,
                model_used=model_used,
                routing_ms=total_ms,
                reason_code=ReasonCode.LLM_CLASSIFIED,
                breakdown_ms=breakdown,
            )

        except Exception as exc:
            total_ms = (time.perf_counter_ns() - t0) / 1e6
            rescued = self._semantic_rescue(request_id, text, total_ms, breakdown)
            if rescued:
                return rescued
            if isinstance(exc, LLMUnavailable):
                # Ollama really is down (or has no model): say so plainly, and what happens next.
                no_model = "No installed Ollama model" in str(exc)
                message = (
                    "No AI model is installed yet, so I can only run direct commands. Run "
                    "\"python scripts\\setup_models.py\" (or \"ollama pull llama3.2\") and ask me again."
                    if no_model else
                    "I can't reach my local AI (Ollama) right now, so I couldn't understand that one. I'm starting it - "
                    "ask me again in a few seconds. Direct commands like \"open chrome\" still work."
                )
                return RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CLARIFY,
                    intent=None,
                    slots={},
                    confidence=0.0,
                    source=RouteSource.TINY_MODEL,
                    complexity=ComplexityLevel.SIMPLE,
                    clarification=message,
                    normalized_text=text,
                    model_used=model_used,
                    routing_ms=total_ms,
                    reason_code=ReasonCode.UNKNOWN_INTENT,
                    breakdown_ms=breakdown,
                    context_trace={"llm_unavailable": True},
                )
            # Any other hiccup (slow first load, malformed JSON, model error): the classifier is only a
            # shortcut, so hand the request to the assistant / tool agent instead of refusing it.
            breakdown["classifier_error"] = 1.0
            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.CLARIFY,
                intent=None,
                slots={},
                confidence=0.0,
                source=RouteSource.TINY_MODEL,
                complexity=ComplexityLevel.SIMPLE,
                clarification=f"classifier_error: {type(exc).__name__}",
                normalized_text=text,
                model_used=model_used,
                routing_ms=total_ms,
                reason_code=ReasonCode.UNKNOWN_INTENT,
                breakdown_ms=breakdown,
                context_trace={"classifier_error": type(exc).__name__},
            )

    async def close(self):
        if self._client is not None:
            await self._client.aclose()


class DisabledProvider:
    """Explicit offline configuration: never contact a model server."""
    async def classify(self, text, candidates, request_id):
        return RouteDecision(
            request_id=request_id, lane=RouteLane.CLARIFY, confidence=0.0,
            source=RouteSource.EXACT, normalized_text=text,
            clarification="I didn't quite catch that. How can I help you?",
            reason_code=ReasonCode.UNKNOWN_INTENT,
        )

    async def close(self):
        pass


class MockFailingProvider:
    """Mock provider that simulates Ollama being stopped or unavailable."""
    async def classify(self, text: str, candidates: list[str], request_id: str) -> RouteDecision:
        raise ConnectionRefusedError("Ollama stopped")

    async def close(self):
        pass


class MockStructuredProvider:
    """Mock provider for deterministic testing of Lane 1 structured responses."""
    def __init__(self, responses: dict | None = None):
        self.responses = responses or {}

    async def classify(self, text: str, candidates: list[str], request_id: str) -> RouteDecision:
        custom = self.responses.get(text)
        if custom:
            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_1 if not custom.get("is_multi_step") else RouteLane.LANE_2,
                intent=custom.get("intent"),
                slots=custom.get("slots", {}),
                confidence=float(custom.get("confidence", 0.9)),
                source=RouteSource.TINY_MODEL,
                complexity=ComplexityLevel.SIMPLE if not custom.get("is_multi_step") else ComplexityLevel.COMPLEX,
                needs_planner=bool(custom.get("is_multi_step", False)),
                missing_slots=custom.get("missing_slots", []),
                normalized_text=text,
                model_used="mock:qwen3:0.6b",
                reason_code=ReasonCode.LLM_CLASSIFIED,
            )
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.LANE_1,
            intent="volume_down",
            slots={},
            confidence=0.92,
            source=RouteSource.TINY_MODEL,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=text,
            model_used="mock:qwen3:0.6b",
            reason_code=ReasonCode.LLM_CLASSIFIED,
        )

    async def close(self):
        pass
