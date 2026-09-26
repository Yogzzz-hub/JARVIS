import asyncio
import inspect
import logging
import os
import re
import time
from typing import Any
from pydantic import ValidationError
from jarvis.core.commands.contracts import CommandResult
from jarvis.core.commands.resolver import resolve
from jarvis.core.metrics.clock import Clock, now_ns
from jarvis.core.router.models import ComplexityLevel, RouteLane
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.control import match_control
from jarvis.core.tasks.manager import State
from jarvis.tools.base import ToolResult, VerificationResult

class CommandService:
    # Sources whose results must never be spoken on the PC speakers (remote / background channels).
    SILENT_SOURCES = frozenset({"whatsapp", "test_silent", "benchmark", "test"})

    def __init__(self, registry, executor, verifier, response, tasks, bus, writer, metrics, router=None, planner=None, scheduler=None, planner_enabled=True, pulse=None, working_memory=None,
                 assistant=None, agent=None, whatsapp_ai=None):
        self.registry, self.executor, self.verifier, self.response = registry, executor, verifier, response
        self.tasks, self.bus, self.writer, self.metrics = tasks, bus, writer, metrics
        self.router = router or SmartRouter(app_resolver=getattr(executor, "resolver", None))
        self.working_memory = working_memory or getattr(self.router, "working_memory", None)
        self.planner = planner
        self.scheduler = scheduler
        self.planner_enabled = planner_enabled
        self.pulse = pulse
        self.assistant = assistant
        self.agent = agent
        self.whatsapp_ai = whatsapp_ai
        self.accepting = True
        self.active = set()
        self._pending_execution: dict[str, Any] | None = None
        self._last_decisions: dict[str, Any] = {}
        self._request_channels: dict[str, str] = {}
        self._last_command_text = ""

    _last_volume = 50

    def _translate_intent(self, name: str, slots: dict | None) -> tuple[str, dict]:
        """Router intents that are phrasings of an existing tool call (relative volume, mute, restore, status)."""
        slots = dict(slots or {})
        if name in ("volume_up", "volume_down", "volume_mute", "mute", "volume_unmute", "unmute") and self.registry.contains("volume_set"):
            current = None
            if self.registry.contains("volume_get"):
                try:
                    current = float(self.registry.get("volume_get").run({}).get("percent"))
                except Exception:
                    current = None
            if name in ("volume_mute", "mute"):
                if current:
                    CommandService._last_volume = int(current)
                return "volume_set", {"percent": 0}
            if name in ("volume_unmute", "unmute"):
                return "volume_set", {"percent": int(CommandService._last_volume or 50)}
            step = int(slots.get("step") or slots.get("amount") or 10)
            base = 50.0 if current is None else current
            target = base + step if name == "volume_up" else base - step
            return "volume_set", {"percent": int(max(0, min(100, round(target))))}
        if name == "restore_window" and self.registry.contains("move_resize_window"):
            return "move_resize_window", {"action": "restore"}
        if name == "whatsapp_status" and self.registry.contains("whatsapp_action"):
            return "whatsapp_action", {"action": "status"}
        return name, slots

    def _expand_repeat(self, request):
        """"Do that again" re-runs the last routed command (routing and policy run again as normal)."""
        last = getattr(self, "_last_command_text", "")
        if last and self._REPEAT.match((request.text or "").strip()):
            try:
                return request.model_copy(update={"text": last})
            except Exception:
                return request
        return request

    async def _run_shortcut(self, request, clock=None):
        """Voice shortcuts: a saved phrase expands into its steps, each handled (routed + policy-checked) in order."""
        if not getattr(request, "is_owner", True) or (getattr(request, "metadata", None) or {}).get("shortcut_depth"):
            return None
        try:
            from jarvis.tools.system.everyday_tools import get_store, normalize_phrase
            steps = get_store().shortcuts().get(normalize_phrase(request.text))
        except Exception:
            return None
        if not steps:
            return None
        messages, state, started = [], "SUCCESS", now_ns()
        for i, step in enumerate(steps, 1):
            sub = request.model_copy(update={"text": step, "request_id": f"{request.request_id[:56]}_s{i}",
                                             "metadata": {**(request.metadata or {}), "shortcut_depth": 1}})
            try:
                result = await self.handle(sub)
            except Exception as exc:
                messages.append(f"Step {i} ({step}) failed: {exc}")
                state = "FAILED"
                break
            messages.append(result.message)
            if result.state == "WAITING_CONFIRMATION":
                state = "WAITING_CONFIRMATION"
                if i < len(steps):
                    messages.append(f"Say the shortcut again after confirming to run the remaining {len(steps) - i} step(s).")
                break
            if result.state != "SUCCESS":
                state = result.state
        return CommandResult(request_id=request.request_id, state=state, message=" ".join(m for m in messages if m),
                             metrics={"total_ms": (now_ns() - started) / 1e6})

    def _jde_observe(self, request, decision) -> None:
        """Shadow mode: JDE decides in the background and logs; it never changes this request's route."""
        try:
            from jarvis.decision.runtime import get_runtime
            runtime = get_runtime()
            if runtime.writer is None and self.writer is not None and hasattr(self.writer, "pragmas"):
                runtime.attach_writer(self.writer)
            runtime.observe(request.text, decision, self._channel(request),
                            pending_confirmation=self._pending_execution is not None, request_id=request.request_id)
        except Exception:
            pass

    def _jde_prefers_chat(self, request) -> bool:
        """Stage B only: an unmatched plain question goes to read-only chat instead of the tool-using agent."""
        try:
            from jarvis.decision.runtime import get_runtime
            return get_runtime().answer_as_knowledge(request.text, self._channel(request))
        except Exception:
            return False

    # A pending confirmation older than this is dropped, so a later unrelated "yes" cannot approve it.
    PENDING_TTL_S = 120.0

    @property
    def _pending_execution(self) -> dict[str, Any] | None:
        pending = self.__dict__.get("_pending_store")
        if pending is not None and time.monotonic() - pending.get("_stamped", 0.0) > self.PENDING_TTL_S:
            self.__dict__["_pending_store"] = None
            return None
        return pending

    @_pending_execution.setter
    def _pending_execution(self, value: dict[str, Any] | None) -> None:
        if value is not None:
            value = dict(value)
            value.setdefault("_stamped", time.monotonic())
        self.__dict__["_pending_store"] = value

    # ------------------------------------------------------------------ channel helpers
    @staticmethod
    def _channel(request) -> str:
        if getattr(request, "source", "") == "whatsapp":
            return f"whatsapp:{getattr(request, 'chat_id', '') or getattr(request, 'sender_id', '')}"
        return "local"

    def _speaks(self, request) -> bool:
        """Talk back on the PC for local interactive channels only (never for WhatsApp / tests)."""
        source = getattr(request, "source", "")
        if source in self.SILENT_SOURCES:
            return False
        if source in ("voice", "websocket", "desktop_ui", "local", "chat", "ui", "http", "api", "cli"):
            return True
        return bool(self.pulse and getattr(self.pulse, "audio_output", None) is not None)

    def _conversation(self):
        assistant = self.assistant
        if assistant is None:
            try:
                from jarvis.core.llm.assistant import get_assistant
                assistant = get_assistant()
            except Exception:
                return None
        return getattr(assistant, "memory", None)


    _REPEAT = re.compile(r"^(?:jarvis,?\s+)?(?:repeat (?:that|it|the last command|my last command)|do (?:it|that|the same) again|"
                                       r"again|one more time|once more|same again)(?:\s+please)?[.!]?$", re.I)

    async def handle(self, request, clock=None):
        if not self.accepting:
            raise RuntimeError("service shutting down")
        request = self._expand_repeat(request)
        shortcut = await self._run_shortcut(request, clock)
        if shortcut is not None:
            return shortcut
        self.active = {t for t in self.active if not getattr(t, "done", lambda: False)()}
        if len(self.active) >= 8 and not match_control(request.text, request.request_id):
            raise RuntimeError("native execution capacity reached; retry later")
        clock = clock or Clock()
        clock.parsed_ns = clock.parsed_ns or now_ns()
        task = self.tasks.create(request, clock)
        self._request_channels[task.request_id] = self._channel(request)
        current = asyncio.current_task()
        self.active.add(current)
        tool_result, verification = None, None
        name = "unresolved"
        is_voice = self._speaks(request)
        self.bus.emit("request.received", task.request_id)
        self.writer.enqueue("requests", task.request_id, request.model_dump())
        self.tasks.transition(task, State.UNDERSTANDING)
        try:
            decision = await self.router.route(request)
            self._last_decisions[task.request_id] = decision
            self._jde_observe(request, decision)
            if decision.lane not in (RouteLane.CONTROL, RouteLane.REJECT, RouteLane.CLARIFY) \
                    and decision.intent not in ("command_history",):
                self._last_command_text = request.text
            clock.resolved_ns = now_ns()

            # Handle CONTROL bypass
            if decision.lane == RouteLane.CONTROL:
                if decision.intent == "confirm_ticket":
                    ticket_id = decision.slots.get("ticket_id") if decision.slots else None
                    cm = getattr(self.executor, "confirmation_manager", None)
                    approved = False
                    ticket_to_approve = ticket_id or (self._pending_execution.get("ticket_id") if self._pending_execution else None)
                    if cm:
                        approved = cm.approve_ticket(ticket_to_approve if ticket_to_approve else "")

                    if not approved and not self._pending_execution:
                        state, message = State.FAILED, "No pending action or ticket found to confirm."
                        tool_result = ToolResult(success=False, error=message, tool_name="confirmation")
                        return self._finalize(task, state, message, tool_result, None, clock, current, is_voice=is_voice)

                    if self._pending_execution:
                        pending = self._pending_execution
                        self._pending_execution = None
                        t_id = ticket_to_approve or pending.get("ticket_id")

                        if pending["type"] == "compound":
                            self.tasks.transition(task, State.EXECUTING)
                            if self.pulse:
                                from jarvis.core.pulse.earcons import EarconType
                                self.pulse.play_earcon(EarconType.COMMAND_ACCEPTED, task.request_id)
                                self.pulse.on_execution_started(task.request_id)
                                self.pulse._dispatch_micro_ack(task.request_id, "Confirmed. Executing now.")
                            compound_results = list(pending.get("results", []))
                            remaining = pending["remaining"]
                            first_item = True
                            for sub_tool, sub_args in remaining:
                                if task.cancellation.is_set():
                                    raise asyncio.CancelledError
                                if first_item:
                                    sub_res = await self.executor.execute(sub_tool, sub_args, task, ticket_id=t_id)
                                    first_item = False
                                else:
                                    sub_res = await self.executor.execute(sub_tool, sub_args, task)
                                if not sub_res.success:
                                    if sub_res.data and sub_res.data.get("confirmation_required"):
                                        new_ticket_id = sub_res.data.get("ticket_id")
                                        new_summary = sub_res.data.get("human_summary")
                                        self._pending_execution = {
                                            "type": "compound",
                                            "task": task,
                                            "ticket_id": new_ticket_id,
                                            "remaining": remaining[remaining.index((sub_tool, sub_args)):],
                                            "results": compound_results,
                                            "clock": clock,
                                            "current": current,
                                            "is_voice": is_voice,
                                            "predicted_ms": pending.get("predicted_ms", 400.0),
                                        }
                                        self.bus.emit("confirmation.required", task.request_id, ticket_id=new_ticket_id, summary=new_summary)
                                        self.tasks.transition(task, State.WAITING_CONFIRMATION)
                                        message = f"Please confirm: {new_summary}. Shall I proceed?"
                                        return self._finalize(task, State.WAITING_CONFIRMATION, message, sub_res, None, clock, current, is_voice=is_voice, predicted_ms=pending.get("predicted_ms", 400.0))
                                    raise ValueError(f"Compound action stopped after {len(compound_results)} action(s): {sub_res.error}")
                                sub_verification = await self.verifier.verify(sub_tool.definition.name, sub_res, sub_args, task.cancellation)
                                compound_results.append(sub_res.data)

                            self.tasks.transition(task, State.VERIFYING)
                            if self.pulse:
                                self.pulse.on_execution_finished(task.request_id, 100.0, "compound")
                            tool_result = ToolResult(success=True, data={"compound": compound_results}, tool_name="compound")
                            verification = VerificationResult(verified=True, confidence=1.0, evidence={"count": len(compound_results)})
                            
                            summaries = []
                            for r in compound_results:
                                if isinstance(r, dict):
                                    if "summary" in r and r["summary"]:
                                        summaries.append(r["summary"])
                                    elif "message" in r and r.get("status") == "SENT":
                                        summaries.append(r["message"])
                            if summaries:
                                message = "Confirmed. " + " ".join(summaries)
                            else:
                                message = f"Confirmed. Executed all compound actions successfully."
                            return self._finalize(task, State.SUCCESS, message, tool_result, verification, clock, current, is_voice=is_voice)

                        elif pending["type"] == "graph":
                            return await self._execute_graph(pending["graph"], task, clock, current, is_voice,
                                                             pending.get("predicted_ms", 400.0), approved=True, prefix="Confirmed. ")

                        elif pending["type"] == "agent":
                            return await self._run_agent(request, task, clock, current, is_voice, pending.get("predicted_ms", 400.0),
                                                         goal=pending["goal"], state=pending["state"], confirmed=True)

                        elif pending["type"] == "single":
                            self.tasks.transition(task, State.EXECUTING)
                            tool = pending["tool"]
                            args = pending["arguments"]
                            t_name = getattr(tool.definition, "name", str(tool)) if hasattr(tool, "definition") else str(tool)

                            # TALKBACK: Immediately dispatch verbal confirmation & earcon before awaiting execution
                            if self.pulse:
                                from jarvis.core.pulse.earcons import EarconType
                                self.pulse.play_earcon(EarconType.COMMAND_ACCEPTED, task.request_id)
                                recipient = getattr(args, "recipient", None) or (args.get("recipient") if isinstance(args, dict) else None)
                                if t_name in ("send_whatsapp_message", "send_whatsapp"):
                                    if recipient:
                                        ack_msg = f"Confirmed. Sending your message to {str(recipient).strip().capitalize()} now."
                                    else:
                                        ack_msg = "Confirmed. Sending your message now."
                                elif t_name in ("gmail_send", "send_email"):
                                    ack_msg = "Confirmed. Sending your email now."
                                else:
                                    ack_msg = "Confirmed. Processing now."
                                self.pulse.on_execution_started(task.request_id)
                                self.pulse._dispatch_micro_ack(task.request_id, ack_msg)

                            res = await self.executor.execute(tool, args, task, ticket_id=t_id)
                            if not res.success:
                                return self._finalize(task, State.FAILED, res.error or "Execution failed after confirmation", res, None, clock, current, is_voice=is_voice)
                            self.tasks.transition(task, State.VERIFYING)
                            ver = await self.verifier.verify(tool.definition.name, res, args, task.cancellation)
                            msg = self.response.render(res, ver)
                            return self._finalize(task, State.SUCCESS, f"Confirmed. {msg}", res, ver, clock, current, is_voice=is_voice)
                    else:
                        self.tasks.transition(task, State.EXECUTING)
                        self.tasks.transition(task, State.VERIFYING)
                        state, message = State.SUCCESS, f"Ticket {ticket_to_approve} confirmed and approved."
                        tool_result = ToolResult(success=True, data={"ticket_id": ticket_to_approve}, tool_name="confirmation")
                        return self._finalize(task, state, message, tool_result, None, clock, current, is_voice=is_voice)

                elif decision.intent == "reject_ticket":
                    ticket_id = decision.slots.get("ticket_id") if decision.slots else None
                    cm = getattr(self.executor, "confirmation_manager", None)
                    if cm:
                        cm.deny_ticket(ticket_id if ticket_id else "")
                    self._pending_execution = None
                    if self.working_memory and hasattr(self.working_memory, "clear_pending_confirmation"):
                        self.working_memory.clear_pending_confirmation()
                    if self.pulse:
                        from jarvis.core.pulse.earcons import EarconType
                        self.pulse.play_earcon(EarconType.FAILED_UNCERTAIN, task.request_id)
                        self.pulse._dispatch_micro_ack(task.request_id, "Action cancelled.")
                    self.tasks.transition(task, State.EXECUTING)
                    self.tasks.transition(task, State.VERIFYING)
                    state, message = State.SUCCESS, "Action cancelled. No changes were made."
                    tool_result = ToolResult(success=True, data={"cancelled": True}, tool_name="confirmation")
                    return self._finalize(task, state, message, tool_result, None, clock, current, is_voice=is_voice)

                if hasattr(self.response, "stop_speaking"):
                    self.response.stop_speaking()
                elif hasattr(self.response, "audio_output") and self.response.audio_output:
                    if hasattr(self.response.audio_output, "cancel_all"):
                        self.response.audio_output.cancel_all()
                    elif hasattr(self.response.audio_output, "cancel_current"):
                        self.response.audio_output.cancel_current()

                cancelled = sum(self.tasks.cancel(other.request_id)
                                for other in tuple(self.tasks.tasks.values())
                                if other is not task and other.result is None)
                self.tasks.transition(task, State.EXECUTING)
                self.tasks.transition(task, State.VERIFYING)
                state = State.SUCCESS
                if decision.intent == "stop_speaking":
                    message = "Speech stopped."
                else:
                    message = (f"Cancellation requested for {cancelled} active task(s); actions already started may complete."
                               if cancelled else "No active tasks to cancel.")
                if self.pulse:
                    from jarvis.core.pulse.earcons import EarconType
                    self.pulse.play_earcon(EarconType.FAILED_UNCERTAIN, task.request_id)
                    self.pulse._dispatch_micro_ack(task.request_id, "Speech stopped." if decision.intent == "stop_speaking" else "Cancelled.")
                tool_result = ToolResult(success=True, data={"control": decision.intent, "cancelled_tasks": cancelled}, tool_name="control")
                verification = VerificationResult(verified=True, confidence=1.0, evidence={"control": True})
                if hasattr(self.response, "handle_cancellation") and is_voice and decision.intent != "stop_speaking":
                    self.response.handle_cancellation(task.request_id, is_voice=is_voice)
                return self._finalize(task, state, message, tool_result, verification, clock, current, is_voice=is_voice)

            # Handle REJECT (e.g. Negated command)
            if decision.lane == RouteLane.REJECT:
                state, message = State.FAILED, decision.clarification or "Command was negated. No action taken."
                tool_result = ToolResult(success=False, error=message, tool_name="negation_guard")
                return self._finalize(task, state, message, tool_result, None, clock, current, is_voice=is_voice)

            # Handle CLARIFY (ambiguous app, missing slots, low confidence)
            if decision.lane == RouteLane.CLARIFY:
                if self.working_memory and hasattr(self.working_memory, "set_pending_clarification"):
                    from jarvis.core.context.models import PendingClarification
                    cands = list(decision.slots.get("candidates", [])) if decision.slots else []
                    self.working_memory.set_pending_clarification(
                        PendingClarification(
                            original_intent=decision.intent or "",
                            candidate_names=cands,
                            missing_slot="target",
                            context_snapshot={"raw_text": getattr(request, "text", ""), "slots": decision.slots},
                        )
                    )
                state, message = State.FAILED, decision.clarification or "Could you please clarify your request?"
                tool_result = ToolResult(success=False, error=message, tool_name="clarification")
                return self._finalize(task, state, message, tool_result, None, clock, current, is_voice=is_voice)

            # PULSE: Start parallel Feedback Lane without blocking execution
            predicted_ms = 400.0
            if self.pulse:
                predicted_ms = self.pulse.predict_duration(decision.intent or "unknown", decision.slots)
                self.pulse.start_interaction(
                    task.request_id,
                    decision.intent or "unknown",
                    predicted_ms,
                    source=task.source,
                    slots=decision.slots,
                )
            elif hasattr(self.response, "schedule_ack_or_skip") and is_voice:
                is_complex = (decision.lane == RouteLane.LANE_2 or decision.needs_planner or decision.complexity == ComplexityLevel.COMPOUND)
                ack_res = self.response.schedule_ack_or_skip(task.request_id, decision.intent, is_complex=is_complex, is_voice=is_voice)
                if inspect.isawaitable(ack_res):
                    await ack_res

            # Handle LANE 2 (conversation, planner, agent)
            if decision.lane == RouteLane.LANE_2 or decision.needs_planner:
                from jarvis.core.router.models import ReasonCode
                if getattr(decision, "reason_code", None) == ReasonCode.QUESTION_NOT_COMMAND and self.registry.contains("ollama_chat"):
                    return await self._run_chat(request, task, clock, current, is_voice, predicted_ms)

                if not self.planner_enabled:
                    if self.agent is not None:
                        return await self._run_agent(request, task, clock, current, is_voice, predicted_ms)
                    raise ValueError("This request requires the planner, which is disabled in this deployment.")
                if self.planner is None:
                    from jarvis.core.planner.adaptive_planner import AdaptivePlanner
                    from jarvis.core.scheduler.scheduler import DAGScheduler
                    self.planner = AdaptivePlanner(registry=self.registry)
                    self.scheduler = DAGScheduler(registry=self.registry, executor=self.executor)
                elif self.scheduler is None:
                    from jarvis.core.scheduler.scheduler import DAGScheduler
                    self.scheduler = DAGScheduler(registry=self.registry, executor=self.executor)

                self.tasks.transition(task, State.EXECUTING)
                if self.pulse:
                    self.pulse.on_execution_started(task.request_id)
                clock.dispatch_started_ns = now_ns()

                planning_res = await self.planner.plan(
                    request.text,
                    router_intents=[decision.intent] if decision.intent else None,
                )
                graph = planning_res.graph
                invalid = graph is not None and planning_res.validation_result is not None and not planning_res.validation_result.is_valid

                if graph is None or invalid:
                    # The planner could not compile a valid graph: let the tool-using agent work it out step by step.
                    if self.agent is not None:
                        return await self._run_agent(request, task, clock, current, is_voice, predicted_ms)
                    if self.registry.contains("ollama_chat"):
                        return await self._run_chat(request, task, clock, current, is_voice, predicted_ms)
                    state, message = State.FAILED, planning_res.error or "Planning failed or planner model unavailable."
                    tool_result = ToolResult(success=False, error=message, tool_name="planner")
                    verification = VerificationResult(verified=False, confidence=0.0, evidence={"error": message})
                    return self._finalize(task, state, message, tool_result, verification, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)

                consequential = self._plan_consequential_steps(graph, ai_generated=planning_res.source not in ("cache", "decomposer", "capability_retriever"))
                if consequential and not graph.missing_capabilities and not graph.blocking_questions:
                    from jarvis.security.confirmation.manager import generate_graph_summary
                    summary = generate_graph_summary(consequential)
                    self._pending_execution = {"type": "graph", "graph": graph, "task": task, "clock": clock,
                                               "current": current, "is_voice": is_voice, "predicted_ms": predicted_ms}
                    self._remember_pending_confirmation("plan:" + graph.graph_id, "task_graph", summary, {"goal": graph.goal})
                    self.bus.emit("confirmation.required", task.request_id, ticket_id=None, summary=summary)
                    self.tasks.transition(task, State.WAITING_CONFIRMATION)
                    message = summary if summary.endswith("?") else f"{summary}. Shall I proceed?"
                    tool_result = ToolResult(success=False, data={"confirmation_required": True, "plan": [n.tool for n in graph.nodes]},
                                             error=message, tool_name="dag_scheduler")
                    return self._finalize(task, State.WAITING_CONFIRMATION, message, tool_result, None, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)

                return await self._execute_graph(graph, task, clock, current, is_voice, predicted_ms)

            # Handle COMPOUND COMMAND (Lane 0)
            if decision.complexity == ComplexityLevel.COMPOUND and decision.subcommands:
                self.tasks.transition(task, State.EXECUTING)
                if self.pulse:
                    self.pulse.on_execution_started(task.request_id)
                clock.dispatch_started_ns = now_ns()
                compound_results = []
                prepared = []
                # Validate all subcommands before starting any external action.
                for sub in decision.subcommands:
                    if not self.registry.contains(sub.tool):
                        raise ValueError(f"Capability is not available: {sub.tool}")
                    sub_tool = self.registry.get(sub.tool)
                    sub_valid = sub_tool.definition.input_model.model_fields.keys()
                    filtered_sub = {k: v for k, v in sub.arguments.items() if k in sub_valid} if sub.arguments else {}
                    sub_args = sub_tool.definition.input_model.model_validate(filtered_sub)
                    prepared.append((sub_tool, sub_args))
                for idx, (sub_tool, sub_args) in enumerate(prepared):
                    if task.cancellation.is_set():
                        raise asyncio.CancelledError
                    sub_res = await self.executor.execute(sub_tool, sub_args, task)
                    if not sub_res.success:
                        if sub_res.data and sub_res.data.get("confirmation_required"):
                            ticket_id = sub_res.data.get("ticket_id")
                            human_summary = sub_res.data.get("human_summary")
                            self._pending_execution = {
                                "type": "compound",
                                "task": task,
                                "ticket_id": ticket_id,
                                "remaining": prepared[idx:],
                                "results": compound_results,
                                "clock": clock,
                                "current": current,
                                "is_voice": is_voice,
                                "predicted_ms": predicted_ms,
                            }
                            if self.working_memory and hasattr(self.working_memory, "set_pending_confirmation"):
                                from jarvis.core.context.models import PendingConfirmation
                                self.working_memory.set_pending_confirmation(
                                    PendingConfirmation(
                                        ticket_id=ticket_id or "",
                                        action=sub_tool.definition.name if hasattr(sub_tool, "definition") else str(sub_tool),
                                        human_summary=human_summary or "",
                                        prepared_slots=dict(filtered_sub) if isinstance(filtered_sub, dict) else {},
                                        risk_level=getattr(decision, "risk", "HIGH") or "HIGH",
                                    )
                                )
                            self.bus.emit("confirmation.required", task.request_id, ticket_id=ticket_id, summary=human_summary)
                            self.tasks.transition(task, State.WAITING_CONFIRMATION)
                            message = f"Please confirm: {human_summary}. Shall I proceed?"
                            tool_result = ToolResult(
                                success=False,
                                data=sub_res.data,
                                error=message,
                                tool_name=sub_tool.definition.name,
                            )
                            return self._finalize(task, State.WAITING_CONFIRMATION, message, tool_result, None, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)
                        raise ValueError(f"Compound action stopped after {len(compound_results)} verified action(s): {sub_res.error}")
                    sub_verification = await self.verifier.verify(sub_tool.definition.name, sub_res, sub_args, task.cancellation)
                    if not sub_verification.verified:
                        raise ValueError(f"Compound action could not be verified: {sub_verification.error}")
                    compound_results.append(sub_res.data)
                self.tasks.transition(task, State.VERIFYING)
                if self.pulse:
                    self.pulse.on_execution_finished(task.request_id, 100.0, "compound")
                tool_result = ToolResult(success=True, data={"compound": compound_results}, tool_name="compound")
                verification = VerificationResult(verified=True, confidence=1.0, evidence={"count": len(compound_results)})
                summaries = []
                for r in compound_results:
                    if isinstance(r, dict):
                        if "summary" in r and r["summary"]:
                            summaries.append(r["summary"])
                        elif "message" in r and r.get("status") == "SENT":
                            summaries.append(r["message"])
                if summaries:
                    message = " ".join(summaries)
                else:
                    message = f"Executed {len(decision.subcommands)} compound actions successfully."
                return self._finalize(task, State.SUCCESS, message, tool_result, verification, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)

            # Standard LANE 0 / LANE 1 Tool Execution
            name = decision.intent
            raw_arguments = decision.slots
            if name in ("stop_speaking", "stop_task", "cancel_task"):
                if hasattr(self.response, "stop_speaking"):
                    self.response.stop_speaking()
                elif hasattr(self.response, "audio_output") and self.response.audio_output:
                    if hasattr(self.response.audio_output, "cancel_all"):
                        self.response.audio_output.cancel_all()
                    elif hasattr(self.response.audio_output, "cancel_current"):
                        self.response.audio_output.cancel_current()
                cancelled = sum(self.tasks.cancel(other.request_id)
                                for other in tuple(self.tasks.tasks.values())
                                if other is not task and other.result is None)
                self.tasks.transition(task, State.EXECUTING)
                self.tasks.transition(task, State.VERIFYING)
                msg = "Speech stopped." if name == "stop_speaking" else ("Cancellation requested for active tasks." if cancelled else "No active tasks to cancel.")
                tool_res = ToolResult(success=True, data={"control": name, "cancelled_tasks": cancelled}, tool_name="control")
                ver = VerificationResult(verified=True, confidence=1.0, evidence={"control": True})
                return self._finalize(task, State.SUCCESS, msg, tool_res, ver, clock, current, is_voice=is_voice)

            name, raw_arguments = self._translate_intent(name, raw_arguments)
            if name in ("read_whatsapp_messages", "summarize_whatsapp_messages"):
                # Group chats only when the owner names them ("my group messages", "the CSE group").
                from jarvis.tools.system.whatsapp_tools import group_scope_from_text
                raw_arguments = {**dict(raw_arguments or {}), "include_groups": False, "group": "",
                                 **group_scope_from_text(request.text)}
            if not self.registry.contains(name):
                target_tool = None
                if hasattr(self.router, "catalog") and hasattr(self.router.catalog, "intents"):
                    defn = self.router.catalog.intents.get(name)
                    if defn and defn.tool:
                        target_tool = defn.tool
                if target_tool and self.registry.contains(target_tool):
                    name = target_tool
                elif self.registry.contains(name.lower()):
                    name = name.lower()
                else:
                    raise ValueError(f"Capability is not available in this deployment: {name or 'unknown'}")
            tool = self.registry.get(name)
            tool_name = tool.definition.name
            if tool_name == "ollama_chat":
                ctx = decision.context_trace or {}
                if ctx.get("fallback") == "unknown_command" and self.agent is not None \
                        and not self._jde_prefers_chat(request):
                    return await self._run_agent(request, task, clock, current, is_voice, predicted_ms)
                return await self._run_chat(request, task, clock, current, is_voice, predicted_ms,
                                            query=(raw_arguments or {}).get("query"))
            from jarvis.core.llm.tool_catalog import normalize_slots
            raw_arguments = normalize_slots(tool_name, raw_arguments)
            if tool_name == "send_whatsapp_message":
                raw_arguments = await self._prepare_whatsapp_message(raw_arguments, decision, request)
            clock.lookup_ns = now_ns()
            valid_fields = tool.definition.input_model.model_fields.keys()
            filtered_args = {k: v for k, v in raw_arguments.items() if k in valid_fields} if raw_arguments else {}
            arguments = tool.definition.input_model.model_validate(filtered_args)
            self.tasks.transition(task, State.EXECUTING)
            if self.pulse:
                self.pulse.on_execution_started(task.request_id)
            clock.dispatch_started_ns = now_ns()
            try:
                tool_result = await self.executor.execute(tool, arguments, task)
            finally:
                # Timestamp is taken at actual invocation; diagnostic delivery can follow.
                if clock.tool_started_ns:
                    self.bus.emit("tool.started", task.request_id, at_ns=clock.tool_started_ns)
                    self.bus.emit("tool.finished", task.request_id, at_ns=clock.tool_returned_ns)
                if self.pulse:
                    dur_ms = (clock.tool_returned_ns - clock.tool_started_ns) / 1e6 if (clock.tool_started_ns and clock.tool_returned_ns) else 50.0
                    entity = str(decision.slots.get("name") or decision.slots.get("path") or "") if decision.slots else ""
                    self.pulse.on_execution_finished(task.request_id, dur_ms, name, entity)

            if not tool_result.success:
                if tool_result.data and tool_result.data.get("confirmation_required"):
                    ticket_id = tool_result.data.get("ticket_id")
                    human_summary = tool_result.data.get("human_summary")
                    self._pending_execution = {
                        "type": "single",
                        "task": task,
                        "ticket_id": ticket_id,
                        "tool": tool,
                        "arguments": arguments,
                        "clock": clock,
                        "current": current,
                        "is_voice": is_voice,
                        "predicted_ms": predicted_ms,
                    }
                    if self.working_memory and hasattr(self.working_memory, "set_pending_confirmation"):
                        from jarvis.core.context.models import PendingConfirmation
                        self.working_memory.set_pending_confirmation(
                            PendingConfirmation(
                                ticket_id=ticket_id or "",
                                action=tool.definition.name if hasattr(tool, "definition") else name,
                                human_summary=human_summary or "",
                                prepared_slots=dict(filtered_args) if isinstance(filtered_args, dict) else {},
                                risk_level=getattr(decision, "risk", "HIGH") or "HIGH",
                            )
                        )
                    self.bus.emit("confirmation.required", task.request_id, ticket_id=ticket_id, summary=human_summary)
                    self.tasks.transition(task, State.WAITING_CONFIRMATION)
                    message = f"Please confirm: {human_summary}. Shall I proceed?"
                    return self._finalize(task, State.WAITING_CONFIRMATION, message, tool_result, None, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)
                from jarvis.core.response.formatter import ResponseFormatter
                raw_err = tool_result.error or "Execution failed"
                message = ResponseFormatter.sanitize_error(raw_err, tool_name=name)
                state = State.FAILED
                return self._finalize(task, state, message, tool_result, None, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)

            next_action = tool_result.data.get("next_action") if isinstance(tool_result.data, dict) else None
            if next_action and self.registry.contains(str(next_action.get("tool", ""))):
                # e.g. a drafted WhatsApp reply: continue with the (policy-confirmed) send step.
                return await self._chain_next_action(next_action, tool_result, task, clock, current, is_voice, predicted_ms)

            self.tasks.transition(task, State.VERIFYING)
            clock.verification_started_ns = now_ns()
            try:
                verification = await self.verifier.verify(name, tool_result, arguments, task.cancellation)
            finally:
                clock.verification_finished_ns = now_ns()
            self.bus.emit("verification.finished", task.request_id, verified=verification.verified)
            if task.cancellation.is_set():
                raise asyncio.CancelledError
            state = State.SUCCESS if verification.verified else State.FAILED
            if not verification.verified:
                tool_result = tool_result.model_copy(update={"success": False, "error": verification.error})
            else:
                tool_result = tool_result.model_copy(update={"evidence": verification.evidence})
            message = self.response.render(tool_result, verification)
        except asyncio.CancelledError:
            task.cancellation.set()
            state, message = State.CANCELLED, "Cancelled; any native action already started may have completed."
            if hasattr(self.response, "handle_cancellation") and getattr(task, "source", "") == "voice":
                self.response.handle_cancellation(task.request_id, is_voice=True)
        except (ValueError, OSError, TimeoutError, ValidationError) as exc:
            from jarvis.core.response.formatter import ResponseFormatter
            raw_err = str(exc) or type(exc).__name__
            message = ResponseFormatter.sanitize_error(raw_err, tool_name=name)
            state = State.FAILED
            tool_result = ToolResult(success=False, error=raw_err, tool_name=name)
        except Exception:
            logging.getLogger("jarvis.commands").exception("unexpected core failure", extra={"request_id": task.request_id})
            self.tasks.transition(task, State.FAILED)
            self.active.discard(current)
            raise
        return self._finalize(task, state, message, tool_result, verification, clock, current, is_voice=is_voice, predicted_ms=locals().get("predicted_ms", 400.0))

    def _finalize(self, task, state, message, tool_result, verification, clock, current, is_voice: bool = False, predicted_ms: float = 400.0):
        try:
            if task.state != state:
                self.tasks.transition(task, state)
            clock.response_ready_ns = now_ns()

            # Handle PULSE Feedback Lane vs Legacy Response
            is_fast_silent = (predicted_ms < 250.0 and not is_voice)
            is_waiting_confirmation = (state == State.WAITING_CONFIRMATION)
            if self.pulse:
                self.pulse.on_verified(
                    request_id=task.request_id,
                    is_verified=(state == State.SUCCESS),
                    result_message=message,
                    is_voice=is_voice,
                    is_fast_silent=is_fast_silent,
                    is_waiting_confirmation=is_waiting_confirmation,
                )
            elif getattr(self.response, "enabled", False):
                self.response.schedule_final(task.request_id, message)

            result = CommandResult(request_id=task.request_id, state=state.value, message=message,
                                   tool_result=tool_result, verification=verification, metrics=clock.metrics())
            task.result = result
            self.metrics.record(task.request_id, result.metrics)
            if tool_result:
                self.writer.enqueue("tool_runs", task.request_id, tool_result.model_dump(mode="json"))
            self.tasks.transition(task, State.RESPONDING)
            self.bus.emit("response.ready", task.request_id, result=result.model_dump(mode="json"), source=task.source)
            logging.getLogger("jarvis.commands").info(message, extra={"request_id": task.request_id,
                "event": "response.ready", "duration_ms": result.metrics["total_ms"]})

            # Conversation transcript for the chat model / agent (per channel).
            dec = self._last_decisions.get(task.request_id)
            channel = self._request_channels.pop(task.request_id, "local")
            memory = self._conversation()
            if memory is not None and dec is not None and dec.lane not in (RouteLane.CONTROL, RouteLane.REJECT):
                try:
                    memory.add(channel, "user", getattr(task, "raw_text", ""))
                    memory.add(channel, "assistant", message)
                except Exception:
                    pass

            # Contextual working memory updates
            if self.working_memory:
                try:
                    if state == State.SUCCESS:
                        if hasattr(self.working_memory, "clear_pending_clarification"):
                            self.working_memory.clear_pending_clarification()

                        t_name = tool_result.tool_name if tool_result else (dec.intent if dec else "")
                        # Record files opened
                        if t_name in ("open_file", "edit_file", "write_file", "view_file") or (tool_result and isinstance(tool_result.data, dict) and tool_result.data.get("opened")):
                            opened_path = None
                            if tool_result and isinstance(tool_result.data, dict):
                                opened_path = tool_result.data.get("path")
                            if not opened_path and dec and dec.slots:
                                opened_path = dec.slots.get("path")
                            if opened_path and hasattr(self.working_memory, "record_file_opened"):
                                self.working_memory.record_file_opened(opened_path)

                        # Record search results
                        if tool_result and isinstance(tool_result.data, dict):
                            paths = tool_result.data.get("results") or tool_result.data.get("files") or tool_result.data.get("paths")
                            if paths and isinstance(paths, list) and hasattr(self.working_memory, "record_search_results"):
                                q = (dec.slots.get("query") if dec and dec.slots else None) or getattr(task, "raw_text", "")
                                self.working_memory.record_search_results(query=q, paths=paths)

                        # Record app focused
                        if t_name in ("launch_app", "open_app", "focus_app") and hasattr(self.working_memory, "record_app_focused"):
                            app_name = (tool_result.data.get("app") or tool_result.data.get("name")) if (tool_result and isinstance(tool_result.data, dict)) else None
                            if not app_name and dec and dec.slots:
                                app_name = dec.slots.get("name")
                            if app_name:
                                self.working_memory.record_app_focused(app_name)

                        # Record assistant answers / extract entities (Sections 48, 49)
                        from jarvis.core.router.models import ReasonCode
                        is_info_turn = (t_name in ("ollama_chat", "system_info")) or (dec and getattr(dec, "reason_code", None) == ReasonCode.QUESTION_NOT_COMMAND)
                        if is_info_turn and message and hasattr(self.working_memory, "record_assistant_answer"):
                            from jarvis.core.context.entity_extractor import EntityExtractor
                            extracted_entities = EntityExtractor.extract_from_assistant_response(message)
                            self.working_memory.record_assistant_answer(message, entities=extracted_entities)

                    elif state == State.FAILED:
                        # Record action failure (Section 24, 25)
                        if hasattr(self.working_memory, "record_action_failure"):
                            fail_target = (dec.slots.get("name") or dec.slots.get("path")) if (dec and dec.slots) else getattr(task, "raw_text", "")
                            fail_reason = (tool_result.error if tool_result and tool_result.error else message) or "FAILED"
                            self.working_memory.record_action_failure(target=fail_target, reason=fail_reason)
                except Exception as _ctx_err:
                    logging.getLogger("jarvis.commands").debug("Working memory outcome update error: %s", _ctx_err)

            # Non-invasive manual acceptance test diagnostic trace
            if os.environ.get("JARVIS_TEST_MODE") == "manual":
                dec = self._last_decisions.pop(task.request_id, None)
                norm_text = getattr(dec, "normalized_text", getattr(task, "raw_text", "")) if dec else getattr(task, "raw_text", "")
                lane_str = getattr(dec.lane, "value", str(dec.lane)) if (dec and hasattr(dec, "lane")) else "UNKNOWN"
                conf = getattr(dec, "confidence", 1.0) if dec else 1.0
                slots = getattr(dec, "slots", {}) if dec else {}
                model_used = getattr(dec, "model_used", None) or "NONE"
                plan_used = "DAG_PLAN" if (dec and getattr(dec, "needs_planner", False)) else "DIRECT"
                t_name = tool_result.tool_name if tool_result else (dec.intent if dec else "NONE")
                risk_class = getattr(dec, "risk", "REVERSIBLE") if dec else "REVERSIBLE"
                policy_res = "ALLOWED" if state in (State.SUCCESS, State.WAITING_CONFIRMATION) else "DENIED_OR_FAILED"
                ver_res = verification.status if verification else ("VERIFIED" if state == State.SUCCESS else "NONE")
                dur = result.metrics.get("total_ms", 0.0)

                ctx_trace = getattr(dec, "context_trace", None) or {}
                followup_type = ctx_trace.get("followup_type", "NONE")
                active_topic_val = ctx_trace.get("active_topic") or (self.working_memory.active_topic.canonical_name if (self.working_memory and getattr(self.working_memory, "active_topic", None)) else "NONE")
                candidates_str = ctx_trace.get("candidates", "NONE")
                slot_type = ctx_trace.get("expected_slot_type", "NONE")
                resolved_ent = ctx_trace.get("resolved") or (slots.get("name") or slots.get("path") or "NONE")

                trace_output = (
                    f"\n============================================================\n"
                    f"MANUAL ACCEPTANCE DIAGNOSTIC TRACE\n"
                    f"INPUT:               {getattr(task, 'raw_text', 'N/A')}\n"
                    f"FOLLOWUP_TYPE:       {followup_type}\n"
                    f"ACTIVE_TOPIC:        {active_topic_val}\n"
                    f"CANDIDATES:          {candidates_str}\n"
                    f"EXPECTED_SLOT_TYPE:  {slot_type}\n"
                    f"RESOLVED:            {resolved_ent}\n"
                    f"CAPABILITY:          {t_name}\n"
                    f"NORMALIZED:          {norm_text}\n"
                    f"ROUTE:               {lane_str}\n"
                    f"ROUTE CONFIDENCE:    {conf}\n"
                    f"RESOLVED ENTITIES:   {slots}\n"
                    f"MODEL USED:          {model_used}\n"
                    f"PLAN USED:           {plan_used}\n"
                    f"TOOL SELECTED:       {t_name}\n"
                    f"RISK CLASS:          {risk_class}\n"
                    f"POLICY RESULT:       {policy_res}\n"
                    f"EXECUTION START:     {clock.parsed_ns}\n"
                    f"EXECUTION RESULT:    {'SUCCESS' if (tool_result and tool_result.success) or state == State.SUCCESS else 'FAILED'}\n"
                    f"VERIFICATION RESULT: {ver_res}\n"
                    f"FINAL RESPONSE:      {message}\n"
                    f"TOTAL LATENCY:       {dur:.2f} ms\n"
                    f"============================================================\n"
                )
                print(trace_output, flush=True)
                logging.getLogger("jarvis.manual_test").info(trace_output)
            else:
                self._last_decisions.pop(task.request_id, None)

            return result
        finally:
            self.active.discard(current)

    # ------------------------------------------------------------------ AI lanes
    def _to_executing(self, task) -> None:
        if task.state in (State.UNDERSTANDING, State.ACKNOWLEDGED, State.PLANNING, State.WAITING_CONFIRMATION):
            self.tasks.transition(task, State.EXECUTING)

    def _remember_pending_confirmation(self, ticket_id: str, action: str, summary: str, slots: dict | None = None) -> None:
        if self.working_memory and hasattr(self.working_memory, "set_pending_confirmation"):
            from jarvis.core.context.models import PendingConfirmation
            self.working_memory.set_pending_confirmation(
                PendingConfirmation(ticket_id=ticket_id or "", action=action, human_summary=summary or "", prepared_slots=dict(slots or {}))
            )

    async def _run_chat(self, request, task, clock, current, is_voice, predicted_ms, query=None):
        """Grounded conversational answer (RAG + history + live web when needed)."""
        from jarvis.core.response.formatter import ResponseFormatter
        tool = self.registry.get("ollama_chat")
        question = (query or request.text).strip()[:8000]
        args = tool.definition.input_model.model_validate({
            "query": question,
            "channel": self._channel(request),
            "speakable": bool(is_voice),
        })
        self._to_executing(task)
        if self.pulse:
            self.pulse.on_execution_started(task.request_id)
        clock.tool_started_ns = now_ns()
        sink, token = self._open_answer_stream(task, is_voice)
        try:
            res = await self.executor.execute(tool, args, task)
        finally:
            if token is not None:
                from jarvis.core.llm.streaming import current_stream
                current_stream.reset(token)
            if sink is not None:
                sink.close()
        clock.tool_returned_ns = now_ns()
        if sink is not None and sink.first_delta_at is not None:
            clock.first_token_ns = sink.first_delta_at
        if (not res.success or res.data.get("status") == "error") and self.pulse:
            self.pulse.close_speech_stream(task.request_id)  # speak the error message normally instead
        if self.pulse:
            self.pulse.on_execution_finished(task.request_id, (clock.tool_returned_ns - clock.tool_started_ns) / 1e6, "ollama_chat")
        self.tasks.transition(task, State.VERIFYING)
        if not res.success:
            message = ResponseFormatter.sanitize_error(res.error or "Chat failed", tool_name="ollama_chat")
            return self._finalize(task, State.FAILED, message, res, None, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)
        message = res.data.get("response") or "I processed your request."
        if res.data.get("status") == "error":
            # Model offline: fall back to live web results for information questions.
            from jarvis.core.llm.assistant import needs_live_data
            if needs_live_data(question) and self.registry.contains("search_web"):
                web = self.registry.get("search_web")
                web_res = await self.executor.execute(web, web.definition.input_model.model_validate({"query": question}), task)
                if web_res.success and web_res.data.get("summary"):
                    message = web_res.data["summary"]
                    res = web_res
        verification = VerificationResult(verified=True, confidence=0.9, evidence={
            "model": res.data.get("model", ""), "sources": len(res.data.get("sources", []) or []), "used_web": bool(res.data.get("used_web"))})
        return self._finalize(task, State.SUCCESS, message, res, verification, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)

    def _open_answer_stream(self, task, is_voice):
        """Stream the chat answer: speech starts at the first sentence and the UI shows text as it is written."""
        from jarvis.core.llm.streaming import StreamSink, current_stream
        speech = self.pulse.open_speech_stream(task.request_id) if (is_voice and self.pulse is not None) else None
        request_id = task.request_id

        def on_text(text: str) -> None:
            self.bus.emit("assistant.partial", request_id, text=text)

        sink = StreamSink(on_sentence=speech.push if speech is not None else None, on_text=on_text)
        return sink, current_stream.set(sink)

    async def _run_agent(self, request, task, clock, current, is_voice, predicted_ms, goal=None, state=None, confirmed=False):
        """Tool-using agent for open-ended requests; pauses for confirmation on risky steps."""
        goal = goal or request.text
        self._to_executing(task)
        if self.pulse:
            self.pulse.on_execution_started(task.request_id)
        clock.tool_started_ns = now_ns()
        memory = self._conversation()
        history = memory.history(self._channel(request)) if memory is not None and state is None else None
        outcome = await self.agent.run(goal, task=task, history=history, state=state, confirmed=confirmed)
        clock.tool_returned_ns = now_ns()
        if self.pulse:
            self.pulse.on_execution_finished(task.request_id, (clock.tool_returned_ns - clock.tool_started_ns) / 1e6, "agent")
        steps = [{"tool": st.tool, "ok": st.success, "arguments": st.arguments} for st in outcome.steps]
        if outcome.status == "needs_confirmation" and outcome.pending is not None:
            self._pending_execution = {"type": "agent", "goal": goal, "state": outcome.state, "task": task, "clock": clock,
                                       "current": current, "is_voice": is_voice, "predicted_ms": predicted_ms}
            self._remember_pending_confirmation(outcome.pending.ticket_id or f"agent:{task.request_id}", outcome.pending.tool,
                                                outcome.pending.summary, outcome.pending.arguments)
            self.bus.emit("confirmation.required", task.request_id, ticket_id=outcome.pending.ticket_id, summary=outcome.pending.summary)
            self.tasks.transition(task, State.WAITING_CONFIRMATION)
            tool_result = ToolResult(success=False, error=outcome.message, tool_name="agent",
                                     data={"confirmation_required": True, "pending_tool": outcome.pending.tool, "steps": steps})
            return self._finalize(task, State.WAITING_CONFIRMATION, outcome.message, tool_result, None, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)

        self.tasks.transition(task, State.VERIFYING)
        ok = outcome.status in ("done", "needs_input")
        message = outcome.message
        if is_voice:
            from jarvis.core.llm.assistant import to_speakable
            message = to_speakable(message, max_chars=500) or message
        data = {"status": outcome.status, "steps": steps, "model": outcome.model}
        if ok:
            tool_result = ToolResult(success=True, data=data, tool_name="agent")
            verification = VerificationResult(verified=True, confidence=0.8, evidence={"agent_steps": len(steps), "status": outcome.status})
            return self._finalize(task, State.SUCCESS, message, tool_result, verification, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)
        tool_result = ToolResult(success=False, data=data, error=message, tool_name="agent")
        return self._finalize(task, State.FAILED, message, tool_result, None, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)

    async def _prepare_whatsapp_message(self, args: dict, decision, request) -> dict:
        """Turn indirect requests ('ask Rahul if he is free') into the exact text the recipient reads."""
        message = str((args or {}).get("message", "") or "")
        recipient = str((args or {}).get("recipient", "") or "")
        if not message or not recipient:
            return args
        ctx = decision.context_trace or {}
        style = ctx.get("compose_style", "direct")
        try:
            from jarvis.integrations.whatsapp.ai import deterministic_compose, get_whatsapp_ai
            ai = self.whatsapp_ai or get_whatsapp_ai()
            if style != "direct" or ai.needs_composition(message, style):
                composed = await ai.compose_outgoing(recipient, message, style, raw_text=ctx.get("raw_text") or request.text)
            else:
                composed = deterministic_compose(recipient, message, "direct")
        except Exception as exc:
            logging.getLogger("jarvis.commands").debug("Message composition skipped: %s", exc)
            return args
        if composed:
            args = dict(args)
            args["message"] = composed[:4096]
        return args

    def _plan_consequential_steps(self, graph, ai_generated: bool = True) -> list:
        from jarvis.core.llm.tool_catalog import AI_CONFIRM_TOOLS
        from jarvis.tools.base import RiskLevel
        steps = []
        for node in graph.nodes:
            if not self.registry.contains(node.tool):
                continue
            risk = self.registry.get(node.tool).definition.risk
            if risk in (RiskLevel.EXTERNAL_EFFECT, RiskLevel.DESTRUCTIVE, RiskLevel.PRIVILEGED) or (ai_generated and node.tool in AI_CONFIRM_TOOLS):
                shown = dict(node.args)
                for arg_name in node.bindings:
                    shown.setdefault(arg_name, f"<result of step {node.bindings[arg_name].node_id}>")
                steps.append((node.tool, shown, risk if risk != RiskLevel.READ_ONLY else RiskLevel.REVERSIBLE))
        return steps

    async def _execute_graph(self, graph, task, clock, current, is_voice, predicted_ms, approved=False, prefix=""):
        from jarvis.core.planner.schema import GraphStatus
        if self.scheduler is None:
            from jarvis.core.scheduler.scheduler import DAGScheduler
            self.scheduler = DAGScheduler(registry=self.registry, executor=self.executor)
        self._to_executing(task)
        clock.tool_started_ns = now_ns()
        graph_result = await self.scheduler.execute(graph, approved=approved)
        clock.tool_returned_ns = now_ns()
        if self.pulse:
            self.pulse.on_execution_finished(task.request_id, (clock.tool_returned_ns - clock.tool_started_ns) / 1e6, "dag_scheduler")

        if graph_result.status == GraphStatus.NEEDS_CONFIRMATION and not approved:
            from jarvis.security.confirmation.manager import generate_graph_summary
            summary = generate_graph_summary(self._plan_consequential_steps(graph)) or "This plan makes changes outside the PC."
            self._pending_execution = {"type": "graph", "graph": graph, "task": task, "clock": clock, "current": current,
                                       "is_voice": is_voice, "predicted_ms": predicted_ms}
            self._remember_pending_confirmation("plan:" + graph.graph_id, "task_graph", summary, {"goal": graph.goal})
            self.tasks.transition(task, State.WAITING_CONFIRMATION)
            message = summary if summary.endswith("?") else f"{summary}. Shall I proceed?"
            tool_result = ToolResult(success=False, data={"confirmation_required": True}, error=message, tool_name="dag_scheduler")
            return self._finalize(task, State.WAITING_CONFIRMATION, message, tool_result, None, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)

        self.tasks.transition(task, State.VERIFYING)
        is_success = graph_result.status == GraphStatus.SUCCESS
        state = State.SUCCESS if is_success else State.FAILED
        message = self._graph_message(graph_result)
        err_msg = None if is_success else (message or "Plan execution failed")
        tool_result = ToolResult(success=is_success, data=graph_result.model_dump(mode="json"), error=err_msg, tool_name="dag_scheduler")
        verification = VerificationResult(
            verified=is_success,
            error=None if is_success else (err_msg or "Execution failed"),
            confidence=1.0 if is_success else 0.5,
            evidence={"graph_id": graph_result.graph_id, "status": str(graph_result.status), "parallelism_factor": graph_result.parallelism_factor},
        )
        return self._finalize(task, state, prefix + message, tool_result, verification, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)

    def _graph_message(self, graph_result) -> str:
        """Speak what the plan actually produced (e.g. the answer or the sent message), not just a step count."""
        from jarvis.core.response.formatter import ResponseFormatter
        base = graph_result.user_message_data or "Done."
        if str(getattr(graph_result.status, "value", graph_result.status)) != "success":
            return base
        summaries = []
        for node_id in graph_result.successful_nodes:
            nr = graph_result.node_results.get(node_id)
            if nr is None or not isinstance(nr.output, dict):
                continue
            try:
                line = ResponseFormatter.format_verified_tool(nr.tool, nr.output)
            except Exception:
                continue
            if line and line not in summaries and not line.startswith("Task completed"):
                summaries.append(line)
        return " ".join(summaries[-3:]) if summaries else base

    async def _chain_next_action(self, next_action, first_result, task, clock, current, is_voice, predicted_ms):
        """Run a follow-up step proposed by a tool (e.g. send a drafted reply) through normal policy."""
        from jarvis.core.llm.tool_catalog import filter_arguments
        from jarvis.core.response.formatter import ResponseFormatter
        tool = self.registry.get(next_action["tool"])
        args_dict, missing = filter_arguments(tool, next_action.get("arguments") or {})
        if missing:
            raise ValueError(f"Follow-up step is missing {', '.join(missing)}")
        arguments = tool.definition.input_model.model_validate(args_dict)
        res = await self.executor.execute(tool, arguments, task)
        preview = first_result.data.get("draft") or args_dict.get("message", "")
        who = next_action.get("display_recipient") or args_dict.get("recipient", "")
        if not res.success and res.data and res.data.get("confirmation_required"):
            ticket_id = res.data.get("ticket_id")
            self._pending_execution = {"type": "single", "task": task, "ticket_id": ticket_id, "tool": tool, "arguments": arguments,
                                       "clock": clock, "current": current, "is_voice": is_voice, "predicted_ms": predicted_ms}
            self._remember_pending_confirmation(ticket_id or "", tool.definition.name, res.data.get("human_summary") or "", args_dict)
            self.bus.emit("confirmation.required", task.request_id, ticket_id=ticket_id, summary=res.data.get("human_summary"))
            self.tasks.transition(task, State.WAITING_CONFIRMATION)
            if first_result.data.get("confirm_prompt"):
                message = first_result.data["confirm_prompt"]
            elif preview:
                message = f"Here's a reply for {who}: \"{preview}\". Shall I send it?"
            else:
                message = f"Please confirm: {res.data.get('human_summary')}. Shall I proceed?"
            return self._finalize(task, State.WAITING_CONFIRMATION, message, res, None, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)
        self.tasks.transition(task, State.VERIFYING)
        if not res.success:
            message = ResponseFormatter.sanitize_error(res.error or "Follow-up step failed", tool_name=tool.definition.name)
            return self._finalize(task, State.FAILED, message, res, None, clock, current, is_voice=is_voice, predicted_ms=predicted_ms)
        verification = await self.verifier.verify(tool.definition.name, res, arguments, task.cancellation)
        message = self.response.render(res, verification)
        return self._finalize(task, State.SUCCESS if verification.verified else State.FAILED, message, res, verification,
                              clock, current, is_voice=is_voice, predicted_ms=predicted_ms)

    async def close(self):
        self.accepting = False
        for task in self.tasks.tasks.values():
            if task.result is None:
                task.cancellation.set()
        if self.active:
            await asyncio.gather(*tuple(self.active), return_exceptions=True)
        await self.executor.close()
