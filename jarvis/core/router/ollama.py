import asyncio
import json
import time
from typing import Any, Protocol
import httpx
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

class OllamaProvider:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llama3.2:latest",
        timeout: float = 30.0,
        capability_retriever: Any = None,
        capability_registry: Any = None,
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.capability_retriever = capability_retriever
        self.capability_registry = capability_registry
        self._client: httpx.AsyncClient | None = None
        self._resolved_model: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client

    async def _resolve_model(self, client: httpx.AsyncClient) -> str:
        if self._resolved_model:
            return self._resolved_model
        try:
            resp = await client.get("/api/tags", timeout=2.5)
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                if self.model in models:
                    self._resolved_model = self.model
                    return self._resolved_model
                # Find matching model or pick first fast model
                for m in models:
                    if any(cand in m.lower() for cand in ("llama3.2", "qwen2.5-coder:1.5b", "qwen2.5-coder:3b", "phi3", "mistral")):
                        self._resolved_model = m
                        return self._resolved_model
                if models:
                    self._resolved_model = models[0]
                    return self._resolved_model
        except Exception:
            pass
        self._resolved_model = self.model
        return self._resolved_model

    def _build_prompt(self, text: str, candidates: list[IntentDefinition]) -> str:
        try:
            from jarvis.core.capabilities.context import CapabilityContextBuilder
            return CapabilityContextBuilder.build_classifier_prompt(
                text,
                candidates=candidates,
                retriever=self.capability_retriever,
            )
        except Exception:
            intent_lines = []
            for c in candidates:
                req = f" required_slots: {list(c.required_slots)}" if c.required_slots else ""
                intent_lines.append(f"- {c.name}: {c.examples[:2]}{req}")

            intents_block = "\n".join(intent_lines)
            return (
                "You are a command intent classifier. Classify user text into exactly ONE candidate intent, "
                "or set unknown=true if unfamiliar or not an imperative command.\n\n"
                f"Candidate Intents:\n{intents_block}\n\n"
                f'User Text: "{text}"'
            )

    async def classify(
        self,
        text: str,
        candidate_intents: list[IntentDefinition],
        request_id: str,
    ) -> RouteDecision:
        t0 = time.perf_counter_ns()
        breakdown: dict[str, float] = {}

        prompt = self._build_prompt(text, candidate_intents)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": CLASSIFIER_SCHEMA,
            "options": {
                "temperature": 0.0,
                "num_predict": 128,
            },
            "keep_alive": "60m",
        }

        try:
            client = await self._get_client()
            active_model = await self._resolve_model(client)
            payload["model"] = active_model
            resp = await client.post("/api/generate", json=payload, timeout=self.timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            # Extract Ollama timing metrics if present (nanoseconds -> ms)
            if "total_duration" in data:
                breakdown["model_total_ms"] = data["total_duration"] / 1e6
            if "load_duration" in data:
                breakdown["model_load_ms"] = data["load_duration"] / 1e6
            if "prompt_eval_duration" in data:
                breakdown["model_prompt_eval_ms"] = data["prompt_eval_duration"] / 1e6
            if "eval_duration" in data:
                breakdown["model_generation_ms"] = data["eval_duration"] / 1e6

            raw_response = data.get("response", "{}")
            parsed = json.loads(raw_response)

            intent = parsed.get("intent")
            slots = parsed.get("slots", {})
            confidence = float(parsed.get("confidence", 0.8))
            is_multi_step = bool(parsed.get("is_multi_step", False))
            is_command = bool(parsed.get("is_command", True))
            unknown = bool(parsed.get("unknown", False))
            missing_slots = parsed.get("missing_slots", [])

            # Map canonical capability ID to target tool name if Ollama returned canonical format
            from jarvis.core.capabilities.canonical import to_canonical
            if intent:
                canon = to_canonical(intent)
                if self.capability_registry:
                    cap_def = self.capability_registry.get(canon)
                    if cap_def and cap_def.target_tool:
                        intent = cap_def.target_tool
                elif canon == "whatsapp.send":
                    intent = "send_whatsapp_message"
                elif canon == "phone.mirror_open":
                    intent = "android_open_control"
                elif canon == "phone.mirror_close":
                    intent = "android_close_control"
                elif canon == "phone.status":
                    intent = "android_status"

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
                    model_used=self.model,
                    routing_ms=total_ms,
                    reason_code=ReasonCode.MULTI_STEP,
                    breakdown_ms=breakdown,
                )

            # 2. Unknown or not a command
            if unknown or not is_command or intent is None or intent == "null":
                # Check if semantic capability retrieval can rescue the intent
                if self.capability_retriever:
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
                    model_used=self.model,
                    routing_ms=total_ms,
                    reason_code=ReasonCode.UNKNOWN_INTENT,
                    breakdown_ms=breakdown,
                )

            # 3. Missing slots
            if missing_slots:
                return RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CLARIFY,
                    intent=intent,
                    slots=slots,
                    confidence=confidence,
                    source=RouteSource.TINY_MODEL,
                    complexity=ComplexityLevel.SIMPLE,
                    missing_slots=missing_slots,
                    clarification=f"Please specify the required {missing_slots[0]} for {intent}.",
                    normalized_text=text,
                    model_used=self.model,
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
                model_used=self.model,
                routing_ms=total_ms,
                reason_code=ReasonCode.LLM_CLASSIFIED,
                breakdown_ms=breakdown,
            )

        except Exception as exc:
            total_ms = (time.perf_counter_ns() - t0) / 1e6
            # If Ollama timed out or failed, attempt semantic capability retrieval fallback first!
            if self.capability_retriever:
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

            # Graceful degradation when Ollama is stopped / times out and no capability matches
            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.CLARIFY,
                intent=None,
                slots={},
                confidence=0.0,
                source=RouteSource.TINY_MODEL,
                complexity=ComplexityLevel.SIMPLE,
                clarification=f"AI model unavailable ({type(exc).__name__}). Please use standard deterministic commands.",
                normalized_text=text,
                model_used=self.model,
                routing_ms=total_ms,
                reason_code=ReasonCode.UNKNOWN_INTENT,
                breakdown_ms=breakdown,
            )

    async def close(self):
        if self._client and not self._client.is_closed:
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
