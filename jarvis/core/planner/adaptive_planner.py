"""Adaptive Complex Planner for Phase 4.

Implements the deterministic planning cascade:
1. Plan Template Cache (HIT -> instantiate template)
2. Deterministic Decomposer (confidently solvable -> TaskGraph)
3. Capability Retriever (Top-K compact schemas, Recall@12 >= 99%)
4. Complexity Analyzer (LOW / MEDIUM / HIGH)
5. Model Provider (qwen3:1.7b small planner -> qwen3:4b full planner)
6. GraphValidator (strict Pydantic, cycle check, bounds check)
7. Deterministic One-Shot Repair (if invalid, escalate model, feed validator errors)
8. GraphOptimizer (safe READ_ONLY deduplication)
9. Plan Confidence estimation & CapabilityGap / BlockingQuestion detection
"""

import asyncio
import json
import time
from typing import Any, Optional
import httpx
from pydantic import BaseModel

from jarvis.core.planner.cache import PlanTemplateCache
from jarvis.core.planner.complexity import ComplexityAnalyzer, PlannerComplexity
from jarvis.core.planner.decomposer import DeterministicDecomposer
from jarvis.core.planner.optimizer import GraphOptimizer
from jarvis.core.planner.schema import (
    BlockingQuestion,
    CapabilityGap,
    PlanConfidence,
    TaskGraph,
    TaskNode,
    ValueBinding,
)
from jarvis.core.planner.tool_retriever import CompactToolSchema, ToolRetriever
from jarvis.core.planner.validator import GraphValidator, ValidationResult
from jarvis.tools.registry import ToolRegistry


PLANNER_SYSTEM_PROMPT = """You compile a user's request into a TaskGraph using ONLY the provided tools.
Never invent a tool that is not in the provided tool list.
For system tasks, package/software installations, or scripts, use the `powershell_command` tool with as_admin=true.
For web/browser tasks, use browser_navigate, browser_click, browser_type, or browser_snapshot.
For desktop UI tasks, use desktop_ui_snapshot or desktop_ui_click.
Never guess missing critical parameters.
If ambiguity prevents correct execution, output blocking_questions.
If no supplied tool can perform a required capability, output missing_capabilities.
Use independent nodes when operations can run concurrently.
Use dependencies only when one node actually requires another node's output.
Do not include explanations outside the schema."""


class PlanningResult(BaseModel):
    graph: Optional[TaskGraph] = None
    confidence: PlanConfidence = PlanConfidence.LOW
    source: str  # "cache", "decomposer", "model_small", "model_full", "repair", "unavailable"
    model_used: Optional[str] = None
    validation_result: Optional[ValidationResult] = None
    planning_ms: float = 0.0
    repair_used: bool = False
    cache_hit: bool = False
    error: Optional[str] = None


class AdaptivePlanner:
    def __init__(
        self,
        registry: ToolRegistry,
        cache: Optional[PlanTemplateCache] = None,
        decomposer: Optional[DeterministicDecomposer] = None,
        retriever: Optional[ToolRetriever] = None,
        validator: Optional[GraphValidator] = None,
        optimizer: Optional[GraphOptimizer] = None,
        ollama_url: str = "http://127.0.0.1:11434",
        small_model: str = "llama3.2:latest",
        full_model: str = "llama3.2:latest",
        timeout: float = 30.0,
    ):
        self.registry = registry
        self.cache = cache or PlanTemplateCache()
        self.decomposer = decomposer or DeterministicDecomposer()
        self.retriever = retriever or ToolRetriever(registry)
        self.validator = validator or GraphValidator(registry)
        self.optimizer = optimizer or GraphOptimizer(registry)
        self.complexity_analyzer = ComplexityAnalyzer()
        self.ollama_url = ollama_url
        self.small_model = small_model
        self.full_model = full_model
        self.timeout = timeout
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(base_url=self.ollama_url, timeout=self.timeout)
        return self._http_client

    async def _resolve_model(self, requested: str) -> str:
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags", timeout=2.0)
            if resp.status_code == 200:
                names = [m.get("name", "") for m in resp.json().get("models", [])]
                if requested in names:
                    return requested
                for n in names:
                    if any(cand in n.lower() for cand in ("llama3.2", "qwen2.5-coder", "mistral", "llama3.1", "phi3")):
                        return n
                if names:
                    return names[0]
        except Exception:
            pass
        return requested

    async def plan(
        self,
        request_text: str,
        router_intents: Optional[list[str]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> PlanningResult:
        """Executes the complete planning cascade for a Lane 2 request."""
        t0 = time.perf_counter_ns()
        registry_fp = self.registry.get_fingerprint()

        # Step 1: Check Plan Template Cache
        cached_graph = self.cache.get(request_text, router_intents or [], registry_fp)
        if cached_graph is not None:
            v_res = self.validator.validate(cached_graph)
            if v_res.is_valid:
                dur_ms = (time.perf_counter_ns() - t0) / 1e6
                return PlanningResult(
                    graph=cached_graph,
                    confidence=PlanConfidence.HIGH,
                    source="cache",
                    cache_hit=True,
                    validation_result=v_res,
                    planning_ms=dur_ms,
                )

        # Step 2: Check Deterministic Decomposer
        decomposed = self.decomposer.decompose(request_text)
        if decomposed is not None:
            v_res = self.validator.validate(decomposed)
            if v_res.is_valid:
                optimized = self.optimizer.optimize(decomposed)
                dur_ms = (time.perf_counter_ns() - t0) / 1e6
                # Prime plan cache
                self.cache.record_execution(
                    request_text, router_intents or [], optimized, True, registry_fp
                )
                return PlanningResult(
                    graph=optimized,
                    confidence=PlanConfidence.HIGH,
                    source="decomposer",
                    validation_result=v_res,
                    planning_ms=dur_ms,
                )

        # Step 3: Capability Retrieval (Top-K compact schemas)
        candidate_tools = self.retriever.retrieve(request_text, top_k=12, router_intents=router_intents)
        candidate_names = {t.name for t in candidate_tools}

        # Step 3b: Fast Capability Gap check (e.g. WhatsApp, Spotify, Uber, etc.)
        gap = self._detect_missing_capability(request_text, candidate_names)
        if gap is not None:
            dur_ms = (time.perf_counter_ns() - t0) / 1e6
            gap_graph = TaskGraph(
                goal=request_text,
                goal_summary="Capability gap detected",
                missing_capabilities=[gap],
                registry_version=registry_fp,
            )
            return PlanningResult(
                graph=gap_graph,
                confidence=PlanConfidence.HIGH,
                source="capability_retriever",
                planning_ms=dur_ms,
            )

        # Step 4: Complexity Scoring to select model
        complexity = self.complexity_analyzer.analyze(request_text, likely_tools_count=len(candidate_names))
        chosen_model = self.small_model if complexity != PlannerComplexity.HIGH else self.full_model
        chosen_model = await self._resolve_model(chosen_model)

        # Step 5: Generate graph proposal from model
        graph_proposal, model_err = await self._generate_graph(
            request_text, chosen_model, candidate_tools, context
        )

        if graph_proposal is None:
            dur_ms = (time.perf_counter_ns() - t0) / 1e6
            return PlanningResult(
                graph=None,
                confidence=PlanConfidence.LOW,
                source="unavailable",
                model_used=chosen_model,
                planning_ms=dur_ms,
                error=model_err or "Planner model unavailable or failed to produce structured graph",
            )

        # Step 6: Validate graph proposal
        v_res = self.validator.validate(graph_proposal)
        if v_res.is_valid:
            optimized = self.optimizer.optimize(graph_proposal)
            dur_ms = (time.perf_counter_ns() - t0) / 1e6
            self.cache.record_execution(request_text, router_intents or [], optimized, True, registry_fp)
            return PlanningResult(
                graph=optimized,
                confidence=PlanConfidence.HIGH,
                source="model_initial",
                model_used=chosen_model,
                validation_result=v_res,
                planning_ms=dur_ms,
            )

        # Step 7: One-shot repair attempt (escalate model if small model failed)
        repair_model = await self._resolve_model(self.full_model)
        repaired_graph, repair_err = await self._repair_graph(
            request_text,
            graph_proposal,
            v_res.errors,
            repair_model,
            candidate_tools,
        )

        if repaired_graph is not None:
            v_repair = self.validator.validate(repaired_graph)
            if v_repair.is_valid:
                optimized = self.optimizer.optimize(repaired_graph)
                dur_ms = (time.perf_counter_ns() - t0) / 1e6
                self.cache.record_execution(request_text, router_intents or [], optimized, True, registry_fp)
                return PlanningResult(
                    graph=optimized,
                    confidence=PlanConfidence.MEDIUM,
                    source="repair",
                    model_used=repair_model,
                    validation_result=v_repair,
                    planning_ms=dur_ms,
                    repair_used=True,
                )
            else:
                dur_ms = (time.perf_counter_ns() - t0) / 1e6
                return PlanningResult(
                    graph=repaired_graph,
                    confidence=PlanConfidence.LOW,
                    source="repair_failed",
                    model_used=repair_model,
                    validation_result=v_repair,
                    planning_ms=dur_ms,
                    repair_used=True,
                    error="Repair attempt failed validation",
                )

        dur_ms = (time.perf_counter_ns() - t0) / 1e6
        return PlanningResult(
            graph=graph_proposal,
            confidence=PlanConfidence.LOW,
            source="initial_failed",
            model_used=chosen_model,
            validation_result=v_res,
            planning_ms=dur_ms,
            error=repair_err or "Validation failed and repair was unsuccessful",
        )

    async def _generate_graph(
        self,
        request_text: str,
        model: str,
        candidate_tools: list[CompactToolSchema],
        context: Optional[dict[str, Any]],
    ) -> tuple[Optional[TaskGraph], Optional[str]]:
        """Sends request to Ollama with TaskGraph JSON schema format."""
        prompt = self._build_prompt(request_text, candidate_tools, context)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": TaskGraph.model_json_schema(),
            "options": {
                "temperature": 0.0,
                "num_predict": 1024,
            },
            "keep_alive": "2m",
        }

        try:
            client = await self._get_client()
            resp = await client.post("/api/generate", json=payload)
            if resp.status_code != 200:
                return None, f"Ollama HTTP {resp.status_code}: {resp.text}"

            data = resp.json()
            raw_text = data.get("response", "{}")
            graph_data = json.loads(raw_text)
            graph = TaskGraph.model_validate(graph_data)
            graph.planner_model = model
            return graph, None
        except Exception as e:
            return None, str(e)

    async def _repair_graph(
        self,
        goal: str,
        invalid_graph: TaskGraph,
        errors: list[Any],
        model: str,
        candidate_tools: list[CompactToolSchema],
    ) -> tuple[Optional[TaskGraph], Optional[str]]:
        """Sends exactly one targeted repair prompt with deterministic validator errors."""
        err_lines = [f"- {e.code}: {e.message} (node={e.node_id}, field={e.field})" for e in errors]
        err_block = "\n".join(err_lines)
        tools_block = json.dumps([t.model_dump() for t in candidate_tools], indent=2)

        prompt = (
            f"{PLANNER_SYSTEM_PROMPT}\n\n"
            f"REPAIR INSTRUCTION: The previous task graph was INVALID. Correct the errors below.\n\n"
            f"User Goal: {goal}\n\n"
            f"Available Tools:\n{tools_block}\n\n"
            f"Validator Errors:\n{err_block}\n\n"
            f"Invalid Graph:\n{invalid_graph.model_dump_json(indent=2)}\n\n"
            "Generate the corrected, strictly valid TaskGraph JSON:"
        )

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": TaskGraph.model_json_schema(),
            "options": {"temperature": 0.0, "num_predict": 1024},
            "keep_alive": "2m",
        }

        try:
            client = await self._get_client()
            resp = await client.post("/api/generate", json=payload)
            if resp.status_code != 200:
                return None, f"Ollama HTTP {resp.status_code}"
            data = resp.json()
            raw_text = data.get("response", "{}")
            graph_data = json.loads(raw_text)
            graph = TaskGraph.model_validate(graph_data)
            graph.planner_model = model
            return graph, None
        except Exception as e:
            return None, str(e)

    def _build_prompt(
        self,
        text: str,
        candidate_tools: list[CompactToolSchema],
        context: Optional[dict[str, Any]],
    ) -> str:
        tools_json = json.dumps([t.model_dump() for t in candidate_tools], indent=2)
        ctx_str = json.dumps(context or {}, indent=2)

        return (
            f"{PLANNER_SYSTEM_PROMPT}\n\n"
            f"Available Tools:\n{tools_json}\n\n"
            f"Current Context:\n{ctx_str}\n\n"
            f'User Request: "{text}"\n\n'
            "TaskGraph JSON:"
        )

    def _detect_missing_capability(self, text: str, available_tools: set[str]) -> Optional[CapabilityGap]:
        """Detects requests requiring capabilities not present in ToolRegistry (e.g. WhatsApp, Email)."""
        req_lower = text.lower()
        if "whatsapp" in req_lower and "whatsapp_send" not in available_tools:
            return CapabilityGap(
                capability="whatsapp_messaging",
                reason="WhatsApp integration is not installed or enabled in current build.",
                related_tools=[],
            )
        if any(w in req_lower for w in ("email", "gmail", "send mail")) and "send_email" not in available_tools:
            return CapabilityGap(
                capability="email_messaging",
                reason="Email sending capability is not installed in current build.",
                related_tools=[],
            )
        if "slack" in req_lower and "slack_send" not in available_tools:
            return CapabilityGap(
                capability="slack_messaging",
                reason="Slack integration is not installed in current build.",
                related_tools=[],
            )
        return None
