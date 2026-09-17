import asyncio
import logging
from pydantic import ValidationError
from jarvis.core.commands.contracts import CommandResult
from jarvis.core.commands.resolver import resolve
from jarvis.core.metrics.clock import Clock, now_ns
from jarvis.core.router.models import ComplexityLevel, RouteLane
from jarvis.core.router.router import SmartRouter
from jarvis.core.tasks.manager import State
from jarvis.tools.base import ToolResult, VerificationResult

class CommandService:
    def __init__(self, registry, executor, verifier, response, tasks, bus, writer, metrics, router=None, planner=None, scheduler=None):
        self.registry, self.executor, self.verifier, self.response = registry, executor, verifier, response
        self.tasks, self.bus, self.writer, self.metrics = tasks, bus, writer, metrics
        self.router = router or SmartRouter(app_resolver=getattr(executor, "resolver", None))
        self.planner = planner
        self.scheduler = scheduler
        self.accepting = True
        self.active = set()


    async def handle(self, request, clock=None):
        if not self.accepting:
            raise RuntimeError("service shutting down")
        if len(self.active) >= 2:
            raise RuntimeError("native execution capacity reached; retry later")
        clock = clock or Clock()
        clock.parsed_ns = clock.parsed_ns or now_ns()
        task = self.tasks.create(request, clock)
        current = asyncio.current_task()
        self.active.add(current)
        tool_result, verification = None, None
        name = "unresolved"
        is_voice = (getattr(request, "source", "") == "voice")
        self.bus.emit("request.received", task.request_id)
        self.writer.enqueue("requests", task.request_id, request.model_dump())
        self.tasks.transition(task, State.UNDERSTANDING)
        try:
            decision = await self.router.route(request)
            clock.resolved_ns = now_ns()

            # Handle CONTROL bypass
            if decision.lane == RouteLane.CONTROL:
                state, message = State.SUCCESS, "Control signal received: task stopped/cancelled."
                tool_result = ToolResult(success=True, data={"control": decision.intent}, tool_name="control")
                verification = VerificationResult(verified=True, confidence=1.0, evidence={"control": True})
                if hasattr(self.response, "handle_cancellation") and is_voice:
                    self.response.handle_cancellation(task.request_id, is_voice=is_voice)
                return self._finalize(task, state, message, tool_result, verification, clock, current, is_voice=is_voice)

            # Handle REJECT (e.g. Negated command)
            if decision.lane == RouteLane.REJECT:
                state, message = State.FAILED, decision.clarification or "Command was negated. No action taken."
                tool_result = ToolResult(success=False, error=message, tool_name="negation_guard")
                return self._finalize(task, state, message, tool_result, None, clock, current, is_voice=is_voice)

            # Handle CLARIFY (ambiguous app, missing slots, low confidence)
            if decision.lane == RouteLane.CLARIFY:
                state, message = State.FAILED, decision.clarification or "Could you please clarify your request?"
                tool_result = ToolResult(success=False, error=message, tool_name="clarification")
                return self._finalize(task, state, message, tool_result, None, clock, current, is_voice=is_voice)

            # Schedule ACK or skip for valid execution intents
            if hasattr(self.response, "schedule_ack_or_skip") and is_voice:
                is_complex = (decision.lane == RouteLane.LANE_2 or decision.needs_planner or decision.complexity == ComplexityLevel.COMPOUND)
                await self.response.schedule_ack_or_skip(task.request_id, decision.intent, is_complex=is_complex, is_voice=is_voice)

            # Handle LANE 2 (Planner required)
            if decision.lane == RouteLane.LANE_2 or decision.needs_planner:
                if self.planner is None:
                    from jarvis.core.planner.adaptive_planner import AdaptivePlanner
                    from jarvis.core.scheduler.scheduler import DAGScheduler
                    self.planner = AdaptivePlanner(registry=self.registry)
                    self.scheduler = DAGScheduler(registry=self.registry)

                from jarvis.core.planner.schema import GraphStatus
                self.tasks.transition(task, State.EXECUTING)
                clock.dispatch_started_ns = now_ns()

                planning_res = await self.planner.plan(
                    request.text,
                    router_intents=[decision.intent] if decision.intent else None,
                )

                if planning_res.graph is None:
                    state, message = State.FAILED, planning_res.error or "Planning failed or planner model unavailable."
                    tool_result = ToolResult(success=False, error=message, tool_name="planner")
                    verification = VerificationResult(verified=False, confidence=0.0, evidence={"error": message})
                    return self._finalize(task, state, message, tool_result, verification, clock, current)

                # Execute via DAGScheduler
                graph_result = await self.scheduler.execute(planning_res.graph)
                clock.tool_started_ns = now_ns()
                clock.tool_returned_ns = now_ns()

                is_success = graph_result.status in (GraphStatus.SUCCESS, GraphStatus.PARTIAL)
                state = State.SUCCESS if is_success else State.FAILED
                message = graph_result.user_message_data
                tool_result = ToolResult(
                    success=is_success,
                    data=graph_result.model_dump(mode="json"),
                    tool_name="dag_scheduler",
                )
                verification = VerificationResult(
                    verified=is_success,
                    confidence=1.0 if graph_result.status == GraphStatus.SUCCESS else 0.5,
                    evidence={
                        "graph_id": graph_result.graph_id,
                        "status": graph_result.status,
                        "parallelism_factor": graph_result.parallelism_factor,
                    },
                )
                return self._finalize(task, state, message, tool_result, verification, clock, current)


            # Handle COMPOUND COMMAND (Lane 0)
            if decision.complexity == ComplexityLevel.COMPOUND and decision.subcommands:
                self.tasks.transition(task, State.EXECUTING)
                clock.dispatch_started_ns = now_ns()
                compound_results = []
                for sub in decision.subcommands:
                    sub_tool = self.registry.get(sub.tool)
                    sub_args = sub_tool.definition.input_model.model_validate(sub.arguments)
                    sub_res = await self.executor.execute(sub_tool, sub_args, task)
                    compound_results.append(sub_res.data)
                tool_result = ToolResult(success=True, data={"compound": compound_results}, tool_name="compound")
                verification = VerificationResult(verified=True, confidence=1.0, evidence={"count": len(compound_results)})
                state, message = State.SUCCESS, f"Executed {len(decision.subcommands)} compound actions successfully."
                return self._finalize(task, state, message, tool_result, verification, clock, current)

            # Standard LANE 0 / LANE 1 Tool Execution
            name = decision.intent
            raw_arguments = decision.slots
            tool = self.registry.get(name)
            clock.lookup_ns = now_ns()
            arguments = tool.definition.input_model.model_validate(raw_arguments)
            self.tasks.transition(task, State.EXECUTING)
            clock.dispatch_started_ns = now_ns()
            try:
                tool_result = await self.executor.execute(tool, arguments, task)
            finally:
                # Timestamp is taken at actual invocation; diagnostic delivery can follow.
                if clock.tool_started_ns:
                    self.bus.emit("tool.started", task.request_id, at_ns=clock.tool_started_ns)
                    self.bus.emit("tool.finished", task.request_id, at_ns=clock.tool_returned_ns)

            if not tool_result.success:
                state, message = State.FAILED, tool_result.error or "Execution failed"
                return self._finalize(task, state, message, tool_result, None, clock, current)

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
            state, message = State.FAILED, str(exc) or type(exc).__name__
            tool_result = ToolResult(success=False, error=message, tool_name=name)
        except Exception:
            logging.getLogger("jarvis.commands").exception("unexpected core failure", extra={"request_id": task.request_id})
            self.tasks.transition(task, State.FAILED)
            self.active.discard(current)
            raise
        return self._finalize(task, state, message, tool_result, verification, clock, current)

    def _finalize(self, task, state, message, tool_result, verification, clock, current, is_voice: bool = False):
        try:
            self.tasks.transition(task, state)
            clock.response_ready_ns = now_ns()

            # Handle spoken final output for voice requests
            is_voice = (getattr(task, "source", "") == "voice")
            if hasattr(self.response, "handle_final_result") and is_voice:
                try:
                    spoken = self.response.handle_final_result(task.request_id, tool_result, verification, is_voice=is_voice)
                    if spoken and spoken.text:
                        message = spoken.text
                except Exception as resp_err:
                    logging.getLogger("jarvis.commands").warning("Voice response rendering error: %s", resp_err)

            result = CommandResult(request_id=task.request_id, state=state.value, message=message,
                                   tool_result=tool_result, verification=verification, metrics=clock.metrics())
            task.result = result
            self.metrics.record(task.request_id, result.metrics)
            if tool_result:
                self.writer.enqueue("tool_runs", task.request_id, tool_result.model_dump(mode="json"))
            self.tasks.transition(task, State.RESPONDING)
            self.bus.emit("response.ready", task.request_id, state=state.value)
            logging.getLogger("jarvis.commands").info(message, extra={"request_id": task.request_id,
                "event": "response.ready", "duration_ms": result.metrics["total_ms"]})
            return result
        finally:
            self.active.discard(current)

    async def close(self):
        self.accepting = False
        for task in self.tasks.tasks.values():
            if task.result is None:
                task.cancellation.set()
        if self.active:
            await asyncio.gather(*tuple(self.active), return_exceptions=True)
        await self.executor.close()
