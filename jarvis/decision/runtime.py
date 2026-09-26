"""JDE runtime integration: shadow logging and staged promotion.

Stages (``[decision] stage`` in config/jarvis.toml, overridable with ``JARVIS_JDE_STAGE``):

* ``off``       - JDE is not loaded at all.
* ``shadow``    - (default) the existing router decides and acts; JDE decides in a background thread and the
                  pair is stored in the SQLite table ``jde_decisions`` (or ``data/jde/shadow.jsonl`` when no
                  database writer is attached) for offline comparison. Zero effect on routing.
* ``read_only`` - stage B: additionally, when the router has *no* deterministic match (the ``unknown_command``
                  fallback that would start the tool-using agent) and JDE says, with a calibrated EXECUTE gate,
                  that the request is a plain KNOWLEDGE question, it is answered by the read-only chat model
                  instead of the agent. JDE never selects a consequential tool in this stage.

Stages C (reversible actions) and D (consequential routing) are deliberately not implemented: the offline
benchmark (reports/JDE_BENCHMARK.md) must first show zero wrong consequential executions on every split.
Whatever JDE says, the chosen tool still goes through the Phase 5 PolicyEvaluator / ConfirmationManager;
JDE confidence is never used as authorization.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any, Optional

from jarvis.decision.schemas import DecisionResult, DecisionState

logger = logging.getLogger("jarvis.decision.runtime")

STAGES = ("off", "shadow", "read_only")
SHADOW_LOG = Path(__file__).resolve().parents[2] / "data" / "jde" / "shadow.jsonl"
SHADOW_LOG_MAX_BYTES = 20 * 1024 * 1024


def configured_stage() -> str:
    env = os.environ.get("JARVIS_JDE_STAGE", "").strip().lower()
    if env:
        return env if env in STAGES else "shadow"
    if "PYTEST_CURRENT_TEST" in os.environ:  # unit tests never load the model or write shadow logs
        return "off"
    try:
        from jarvis.config import load
        return load().decision.stage
    except Exception:
        return "shadow"


class JDERuntime:
    """Owns the engine and a single background worker. Every public method is exception-safe."""

    def __init__(self, stage: Optional[str] = None, engine: Any = None, log_path: Path = SHADOW_LOG,
                 max_queue: int = 256):
        self.stage = stage if stage in STAGES else configured_stage()
        self._engine = engine
        self._engine_loaded = engine is not None
        self.log_path = Path(log_path)
        self._queue: "queue.Queue[tuple]" = queue.Queue(maxsize=max_queue)
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.previous_route = ""
        self.dropped = 0
        self.logged = 0
        self.writer: Any = None  # PersistenceWriter: when attached, decisions go to SQLite (jde_decisions)

    def attach_writer(self, writer: Any) -> None:
        self.writer = writer

    # --- engine -------------------------------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self.stage != "off"

    def engine(self):
        if not self.enabled:
            return None
        if not self._engine_loaded:
            with self._lock:
                if not self._engine_loaded:
                    from jarvis.decision.engine import get_engine
                    self._engine = get_engine()
                    self._engine_loaded = True
        return self._engine

    def state_for(self, text: str, channel: str = "local", pending_confirmation: bool = False) -> DecisionState:
        return DecisionState(text=text, channel=(channel or "local").split(":", 1)[0], previous_route=self.previous_route,
                             pending_confirmation=bool(pending_confirmation))

    def decide(self, state: DecisionState) -> Optional[DecisionResult]:
        try:
            engine = self.engine()
            return engine.decide(state) if engine is not None else None
        except Exception as exc:  # JDE must never break routing
            logger.debug("JDE decide failed: %s", exc)
            return None

    # --- shadow -------------------------------------------------------------------------------------------
    def observe(self, text: str, router_decision: Any, channel: str = "local", pending_confirmation: bool = False,
                request_id: str = "") -> None:
        """Queue a shadow comparison. Non-blocking; drops the sample when the worker is behind."""
        if not self.enabled or not text:
            return
        try:
            state = self.state_for(text, channel, pending_confirmation)
            self._queue.put_nowait((time.time(), state, _router_summary(router_decision), request_id))
            self._ensure_worker()
        except queue.Full:
            self.dropped += 1
        except Exception as exc:
            logger.debug("JDE shadow observe failed: %s", exc)

    def _ensure_worker(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._run, name="jde-shadow", daemon=True)
            self._worker.start()

    def _run(self) -> None:
        while True:
            try:
                ts, state, router, request_id = self._queue.get(timeout=30)
            except queue.Empty:
                return
            try:
                result = self.decide(state)
                if result is not None:
                    self.previous_route = result.route.value
                    self._write({"ts": round(ts, 3), "stage": self.stage, "text": state.text, "channel": state.channel,
                                 "router": router, "jde": _jde_summary(result),
                                 "agree": _agrees(router, result)}, request_id)
            except Exception as exc:
                logger.debug("JDE shadow worker error: %s", exc)
            finally:
                self._queue.task_done()

    def _write(self, record: dict, request_id: str = "") -> None:
        writer = self.writer
        if writer is not None and not getattr(writer, "error", None):
            try:
                if writer.enqueue("jde_decisions", request_id or "shadow", record):
                    self.logged += 1
                    return
            except Exception:
                pass
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if self.log_path.exists() and self.log_path.stat().st_size > SHADOW_LOG_MAX_BYTES:
            self.log_path.replace(self.log_path.with_suffix(".jsonl.1"))
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.logged += 1

    def warm(self) -> bool:
        """Load the model and encoder ahead of the first request (call from a background thread)."""
        engine = self.engine()
        if engine is None:
            return False
        try:
            engine.decide(self.state_for("warm up the decision engine"))
            return True
        except Exception:
            return False

    def flush(self, timeout: float = 5.0) -> None:
        end = time.time() + timeout
        while self._queue.unfinished_tasks and time.time() < end:
            time.sleep(0.01)

    # --- stage B ------------------------------------------------------------------------------------------
    def answer_as_knowledge(self, text: str, channel: str = "local") -> bool:
        """Stage B only: True when an unmatched request should go to read-only chat instead of the agent."""
        if self.stage != "read_only":
            return False
        result = self.decide(self.state_for(text, channel))
        if result is None:
            return False
        return (result.route.value == "KNOWLEDGE" and result.gate.action == "EXECUTE"
                and result.p("external_effect") < 0.2 and result.p("destructive") < 0.1)


# Router intent/tool -> JDE family, for agreement statistics only.
def _router_summary(decision: Any) -> dict:
    if decision is None:
        return {}
    try:
        trace = decision.context_trace or {}
        intent = decision.intent or ""
        family = ""
        if decision.lane in ("CLARIFY",):
            family = "CLARIFY"
        elif decision.lane in ("REJECT",):
            family = "UNKNOWN"
        elif intent == "ollama_chat":
            family = "PLANNER" if trace.get("fallback") == "unknown_command" else "KNOWLEDGE"
        elif intent:
            from jarvis.decision.catalog import family_for_tool
            family = family_for_tool(intent) or ""
        return {"lane": str(decision.lane), "intent": intent, "family": family,
                "confidence": round(float(decision.confidence), 4), "source": str(decision.source),
                "fallback": trace.get("fallback", "")}
    except Exception:
        return {}


def _jde_summary(result: DecisionResult) -> dict:
    return {"route": result.route.value, "confidence": round(result.route.confidence, 4),
            "gate": result.gate.action, "risk": result.gate.risk_class, "model_class": result.model_class,
            "top3": [(k, round(v, 3)) for k, v in result.families[:3]],
            "p": {k: round(result.p(k), 3) for k in ("is_action", "needs_llm", "external_effect", "destructive", "ambiguous")},
            "latency_ms": round(result.latency_ms, 3), "version": result.versions.get("decision_model_version", "")}


def _agrees(router: dict, result: DecisionResult) -> Optional[bool]:
    fam = router.get("family") if router else ""
    return None if not fam else fam == result.route.value


_runtime: Optional[JDERuntime] = None


def get_runtime() -> JDERuntime:
    global _runtime
    if _runtime is None:
        _runtime = JDERuntime()
    return _runtime


def set_runtime(runtime: Optional[JDERuntime]) -> None:
    global _runtime
    _runtime = runtime
