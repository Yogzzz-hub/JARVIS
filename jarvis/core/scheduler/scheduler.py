"""Deterministic DAG Scheduler for Phase 4.

Executes validated TaskGraphs using:
1. Ready-set algorithm with reverse adjacency and atomic dependency tracking.
2. Structured concurrency with safe exception handling (tool failure is data, not unhandled crash).
3. Deadlock-free resource locking across parallel branches.
4. Per-tool timeout enforcement from trusted ToolDefinition.
5. Typed output binding resolution (results[0].path -> target arg).
6. Declarative condition evaluation without eval/exec.
7. Phase 3 Search confidence protection (ambiguous results block auto-consumption).
8. Minimal Phase-4 Risk Gate (intercepts EXTERNAL_EFFECT/DESTRUCTIVE pending Phase 5 confirmation).
"""

import asyncio
from collections import defaultdict
import inspect
import os
import re
import time
from typing import Any, Optional

from jarvis.core.planner.schema import (
    ConditionDSL,
    ConditionOperator,
    FailurePolicy,
    GraphResult,
    GraphStatus,
    NodeResult,
    NodeState,
    TaskGraph,
    TaskNode,
    ValueBinding,
)
from jarvis.core.scheduler.locks import ResourceLockManager
from jarvis.core.scheduler.models import SchedulerConfig
from jarvis.tools.base import RiskLevel
from jarvis.tools.registry import ToolRegistry

PATH_SEGMENT_REGEX = re.compile(r"([a-zA-Z0-9_]+)(?:\[([0-9]+)\])?")


class DAGScheduler:
    def __init__(
        self,
        registry: ToolRegistry,
        config: Optional[SchedulerConfig] = None,
        lock_manager: Optional[ResourceLockManager] = None,
        executor: Optional[Any] = None,
    ):
        self.registry = registry
        self.config = config or SchedulerConfig()
        self.lock_manager = lock_manager or ResourceLockManager()
        self.executor = executor

    async def execute(
        self,
        graph: TaskGraph,
        tickets: Optional[dict[str, str]] = None,
        approved: bool = False,
    ) -> GraphResult:
        """Executes a validated TaskGraph and returns a structured GraphResult.

        ``approved`` means the user already confirmed this whole plan (its consequential steps
        were read back to them); risky nodes then run, each still receiving its own policy
        ticket bound to the node's final, binding-resolved arguments.
        """
        t0 = time.perf_counter()
        first_action_ms: float = 0.0

        # Handle explicit capability gaps
        if graph.missing_capabilities:
            gap = graph.missing_capabilities[0]
            dur = (time.perf_counter() - t0) * 1000
            return GraphResult(
                graph_id=graph.graph_id,
                status=GraphStatus.CAPABILITY_GAP,
                duration_ms=dur,
                user_message_data=f"I can't perform this request because capability '{gap.capability}' is not installed: {gap.reason}",
            )

        # Handle explicit blocking questions / clarification
        if graph.blocking_questions:
            bq = graph.blocking_questions[0]
            dur = (time.perf_counter() - t0) * 1000
            return GraphResult(
                graph_id=graph.graph_id,
                status=GraphStatus.NEEDS_CLARIFICATION,
                duration_ms=dur,
                user_message_data=bq.question,
            )

        if not graph.nodes:
            dur = (time.perf_counter() - t0) * 1000
            return GraphResult(
                graph_id=graph.graph_id,
                status=GraphStatus.SUCCESS,
                duration_ms=dur,
                user_message_data="Empty task graph completed.",
            )

        node_map: dict[str, TaskNode] = {n.id: n for n in graph.nodes}
        node_results: dict[str, NodeResult] = {}

        # Reverse adjacency list: upstream_node -> list of downstream dependent nodes
        dependents_map: dict[str, list[str]] = defaultdict(list)
        remaining_deps: dict[str, int] = {}

        for node in graph.nodes:
            remaining_deps[node.id] = len(node.depends_on)
            for dep in node.depends_on:
                dependents_map[dep].append(node.id)

        # Concurrency semaphore
        semaphore = asyncio.Semaphore(self.config.max_concurrency)
        ready_queue: asyncio.Queue[str] = asyncio.Queue()

        # Seed ready queue with nodes that have 0 dependencies
        for nid, count in remaining_deps.items():
            if count == 0:
                ready_queue.put_nowait(nid)

        active_tasks: dict[asyncio.Task, str] = {}
        clarification_needed: Optional[str] = None
        needs_policy_confirmation: bool = False

        while len(node_results) < len(graph.nodes):
            # Launch all available ready nodes up to concurrency limit
            while not ready_queue.empty():
                nid = ready_queue.get_nowait()
                if nid in node_results:
                    continue

                node = node_map[nid]
                task = asyncio.create_task(
                    self._execute_node_safe(node, node_results, semaphore, graph_id=graph.graph_id, tickets=tickets, approved=approved)
                )
                active_tasks[task] = nid

            if not active_tasks:
                # No tasks running and ready queue empty, but unexecuted nodes remain
                # Mark any remaining pending nodes as skipped
                for remaining_id in graph.nodes:
                    if remaining_id.id not in node_results:
                        node_results[remaining_id.id] = NodeResult(
                            node_id=remaining_id.id,
                            tool=remaining_id.tool,
                            state=NodeState.SKIPPED_DEPENDENCY_FAILED,
                            error="Dependency resolution blocked",
                        )
                break

            # Wait for at least one active task to complete
            done, _ = await asyncio.wait(
                active_tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            for finished_task in done:
                nid = active_tasks.pop(finished_task)
                try:
                    result: NodeResult = finished_task.result()
                except asyncio.CancelledError:
                    result = NodeResult(
                        node_id=nid,
                        tool=node_map[nid].tool,
                        state=NodeState.CANCELLED,
                        error="Task cancelled",
                    )
                except Exception as ex:
                    result = NodeResult(
                        node_id=nid,
                        tool=node_map[nid].tool,
                        state=NodeState.FAILED,
                        error=f"Unhandled runner exception: {ex}",
                    )

                node_results[nid] = result

                # First action metric
                if first_action_ms == 0.0 and result.start_time > 0:
                    first_action_ms = (result.start_time - t0) * 1000

                # Check if risk gate flagged confirmation
                if result.error == "NEEDS_POLICY_CONFIRMATION":
                    needs_policy_confirmation = True

                # Process dependents based on node state
                if result.state == NodeState.SUCCESS:
                    # Check if node was find_file and returned ambiguous results
                    if result.tool == "find_file" and isinstance(result.output, dict):
                        is_ambiguous = result.output.get("is_ambiguous", False)
                        results_list = result.output.get("results", [])
                        if is_ambiguous or (len(results_list) > 1 and result.output.get("clarification")):
                            clarification_needed = result.output.get(
                                "clarification",
                                "I found multiple matching files. Which one would you like me to use?"
                            )
                            # Block downstream state-changing nodes
                            self._block_dependents_for_ambiguity(
                                nid, dependents_map, node_map, node_results
                            )
                            continue

                    # Decrement dependencies for downstream nodes
                    for downstream_id in dependents_map.get(nid, []):
                        if downstream_id not in node_results:
                            remaining_deps[downstream_id] -= 1
                            if remaining_deps[downstream_id] == 0:
                                ready_queue.put_nowait(downstream_id)

                elif result.state in (
                    NodeState.FAILED,
                    NodeState.TIMEOUT,
                    NodeState.SKIPPED_DEPENDENCY_FAILED,
                    NodeState.SKIPPED_CONDITION_FALSE,
                    NodeState.BLOCKED_AMBIGUOUS_INPUT,
                ):
                    node = node_map[nid]
                    if node.on_failure == FailurePolicy.FAIL_DEPENDENTS:
                        self._skip_transitive_dependents(
                            nid, dependents_map, node_map, node_results
                        )
                    elif node.on_failure == FailurePolicy.OPTIONAL:
                        # Optional node: allow dependents to run with missing output
                        for downstream_id in dependents_map.get(nid, []):
                            if downstream_id not in node_results:
                                remaining_deps[downstream_id] -= 1
                                if remaining_deps[downstream_id] == 0:
                                    ready_queue.put_nowait(downstream_id)

        total_duration_ms = (time.perf_counter() - t0) * 1000
        sequential_est_ms = sum(r.duration_ms for r in node_results.values())
        parallelism_factor = (
            max(1.0, sequential_est_ms / total_duration_ms)
            if total_duration_ms > 0
            else 1.0
        )

        successful = [nid for nid, r in node_results.items() if r.state == NodeState.SUCCESS]
        failed = [nid for nid, r in node_results.items() if r.state in (NodeState.FAILED, NodeState.TIMEOUT)]
        skipped = [
            nid
            for nid, r in node_results.items()
            if r.state in (
                NodeState.SKIPPED_DEPENDENCY_FAILED,
                NodeState.SKIPPED_CONDITION_FALSE,
                NodeState.BLOCKED_AMBIGUOUS_INPUT,
            )
        ]

        # Determine overall graph status
        if clarification_needed:
            status = GraphStatus.NEEDS_CLARIFICATION
            msg = clarification_needed
        elif needs_policy_confirmation:
            status = GraphStatus.NEEDS_CONFIRMATION
            msg = "This operation involves external or destructive changes and requires confirmation."
        elif len(successful) == len(graph.nodes):
            status = GraphStatus.SUCCESS
            msg = f"Completed all {len(successful)} steps successfully."
        elif len(successful) > 0 and (failed or skipped):
            status = GraphStatus.PARTIAL
            msg = f"Completed {len(successful)} of {len(graph.nodes)} steps. Some actions failed or were skipped."
        elif any(r.state == NodeState.CANCELLED for r in node_results.values()):
            status = GraphStatus.CANCELLED
            msg = "Task graph execution was cancelled."
        else:
            status = GraphStatus.FAILED
            first_fail = next((r.error for r in node_results.values() if r.error), "Execution failed.")
            msg = f"Task graph execution failed: {first_fail}"

        return GraphResult(
            graph_id=graph.graph_id,
            status=status,
            node_results=node_results,
            successful_nodes=successful,
            failed_nodes=failed,
            skipped_nodes=skipped,
            duration_ms=total_duration_ms,
            first_action_ms=first_action_ms,
            parallelism_factor=parallelism_factor,
            user_message_data=msg,
            needs_policy_confirmation=needs_policy_confirmation,
        )

    async def _execute_node_safe(
        self,
        node: TaskNode,
        prior_results: dict[str, NodeResult],
        semaphore: asyncio.Semaphore,
        graph_id: str = "",
        tickets: Optional[dict[str, str]] = None,
        approved: bool = False,
    ) -> NodeResult:
        """Executes a single node safely with bindings, locks, timeout, and condition check."""
        t_start = time.perf_counter()

        # 1. Condition evaluation
        if node.condition:
            cond_passed = self._eval_condition(node.condition, prior_results)
            if not cond_passed:
                dur = (time.perf_counter() - t_start) * 1000
                return NodeResult(
                    node_id=node.id,
                    tool=node.tool,
                    state=NodeState.SKIPPED_CONDITION_FALSE,
                    duration_ms=dur,
                    start_time=t_start,
                    end_time=time.perf_counter(),
                )

        # 2. Output binding resolution
        actual_args = dict(node.args)
        for field_name, binding in node.bindings.items():
            upstream_res = prior_results.get(binding.node_id)
            if not upstream_res or upstream_res.state != NodeState.SUCCESS:
                dur = (time.perf_counter() - t_start) * 1000
                return NodeResult(
                    node_id=node.id,
                    tool=node.tool,
                    state=NodeState.SKIPPED_DEPENDENCY_FAILED,
                    error=f"Upstream node '{binding.node_id}' was not successful",
                    duration_ms=dur,
                    start_time=t_start,
                    end_time=time.perf_counter(),
                )

            val, err = self._resolve_output_path(upstream_res.output, binding.output_path)
            if err:
                dur = (time.perf_counter() - t_start) * 1000
                return NodeResult(
                    node_id=node.id,
                    tool=node.tool,
                    state=NodeState.SKIPPED_DEPENDENCY_FAILED,
                    error=f"Failed to resolve binding for field '{field_name}': {err}",
                    duration_ms=dur,
                    start_time=t_start,
                    end_time=time.perf_counter(),
                )
            actual_args[field_name] = val

        # 3. Tool existence check
        if not self.registry.contains(node.tool):
            dur = (time.perf_counter() - t_start) * 1000
            return NodeResult(
                node_id=node.id,
                tool=node.tool,
                state=NodeState.FAILED,
                error=f"Tool '{node.tool}' not found in registry",
                duration_ms=dur,
                start_time=t_start,
                end_time=time.perf_counter(),
            )

        tool_obj = self.registry.get(node.tool)
        tool_defn = tool_obj.definition
        ticket_id = (tickets or {}).get(node.id) or (tickets or {}).get(graph_id)

        # 4. Phase 5 Policy & Confirmation Gate
        if self.config.enforce_risk_gate and (
            tool_defn.risk in (RiskLevel.EXTERNAL_EFFECT, RiskLevel.DESTRUCTIVE, RiskLevel.PRIVILEGED)
            or tool_defn.requires_confirmation
        ):
            if not ticket_id and not approved:
                dur = (time.perf_counter() - t_start) * 1000
                return NodeResult(
                    node_id=node.id,
                    tool=node.tool,
                    state=NodeState.FAILED,
                    error="NEEDS_POLICY_CONFIRMATION",
                    duration_ms=dur,
                    start_time=t_start,
                    end_time=time.perf_counter(),
                )

        # 5. Dry-run support
        if self.config.dry_run:
            dur = (time.perf_counter() - t_start) * 1000
            return NodeResult(
                node_id=node.id,
                tool=node.tool,
                state=NodeState.SUCCESS,
                output={"dry_run": True, "args": actual_args},
                duration_ms=dur,
                start_time=t_start,
                end_time=time.perf_counter(),
            )

        # 6. Execute via ExecutionEngine if configured
        if self.executor:
            res = await self.executor.execute(
                tool_obj,
                actual_args,
                ticket_id=ticket_id,
                graph_id=graph_id,
                node_id=node.id,
                dry_run_policy=self.config.dry_run_policy,
            )
            cm = getattr(self.executor, "confirmation_manager", None)
            if approved and not res.success and (res.data or {}).get("confirmation_required") and cm is not None:
                # The user approved this plan; satisfy the ticket issued for this node's exact arguments.
                node_ticket = res.data.get("ticket_id")
                if node_ticket and cm.approve_ticket(node_ticket):
                    res = await self.executor.execute(
                        tool_obj,
                        actual_args,
                        ticket_id=node_ticket,
                        graph_id=graph_id,
                        node_id=node.id,
                        dry_run_policy=self.config.dry_run_policy,
                    )
            end_t = time.perf_counter()
            if res.success:
                return NodeResult(
                    node_id=node.id,
                    tool=node.tool,
                    state=NodeState.SUCCESS,
                    output=res.data,
                    duration_ms=(end_t - t_start) * 1000,
                    start_time=t_start,
                    end_time=end_t,
                )
            else:
                return NodeResult(
                    node_id=node.id,
                    tool=node.tool,
                    state=NodeState.FAILED,
                    error=res.error or "Execution failed",
                    duration_ms=(end_t - t_start) * 1000,
                    start_time=t_start,
                    end_time=end_t,
                )

        # 6. Execute under semaphore and resource locks
        resource_keys = ResourceLockManager.extract_resource_keys(node.tool, actual_args)
        timeout_s = tool_defn.timeout_s or self.config.default_timeout_s

        async with semaphore:
            async with self.lock_manager.acquire(resource_keys):
                try:
                    async with asyncio.timeout(timeout_s):
                        input_payload = tool_defn.input_model.model_validate(actual_args)
                        # Run tool (sync or async)
                        if inspect.iscoroutinefunction(getattr(tool_obj, "arun", None)):
                            output_obj = await tool_obj.arun(input_payload)
                        elif inspect.iscoroutinefunction(tool_obj.run):
                            output_obj = await tool_obj.run(input_payload)
                        else:
                            loop = asyncio.get_running_loop()
                            output_obj = await loop.run_in_executor(None, tool_obj.run, input_payload)

                        dur = (time.perf_counter() - t_start) * 1000
                        out_dict = (
                            output_obj.model_dump(mode="json")
                            if hasattr(output_obj, "model_dump")
                            else output_obj
                        )
                        return NodeResult(
                            node_id=node.id,
                            tool=node.tool,
                            state=NodeState.SUCCESS,
                            output=out_dict,
                            duration_ms=dur,
                            start_time=t_start,
                            end_time=time.perf_counter(),
                        )
                except asyncio.TimeoutError:
                    dur = (time.perf_counter() - t_start) * 1000
                    return NodeResult(
                        node_id=node.id,
                        tool=node.tool,
                        state=NodeState.TIMEOUT,
                        error=f"Node execution timed out after {timeout_s}s",
                        duration_ms=dur,
                        start_time=t_start,
                        end_time=time.perf_counter(),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as ex:
                    dur = (time.perf_counter() - t_start) * 1000
                    return NodeResult(
                        node_id=node.id,
                        tool=node.tool,
                        state=NodeState.FAILED,
                        error=str(ex),
                        duration_ms=dur,
                        start_time=t_start,
                        end_time=time.perf_counter(),
                    )

    def _resolve_output_path(self, output: Any, path: str) -> tuple[Any, Optional[str]]:
        """Resolves nested path or sequence index on tool output object/dictionary."""
        curr = output
        parts = path.split(".")
        for p in parts:
            m = PATH_SEGMENT_REGEX.match(p)
            if not m:
                return None, f"Invalid path segment: '{p}'"
            attr_name, index_str = m.group(1), m.group(2)

            # Access field
            if isinstance(curr, dict):
                if attr_name not in curr:
                    return None, f"Field '{attr_name}' not in output dict"
                curr = curr[attr_name]
            elif hasattr(curr, attr_name):
                curr = getattr(curr, attr_name)
            else:
                return None, f"Cannot access '{attr_name}' on {type(curr)}"

            # Access index if present (e.g. results[0])
            if index_str is not None:
                idx = int(index_str)
                if isinstance(curr, (list, tuple)):
                    if idx >= len(curr):
                        return None, f"Index [{idx}] out of range (length {len(curr)})"
                    curr = curr[idx]
                else:
                    return None, f"Cannot index non-sequence {type(curr)}"

        return curr, None

    def _eval_condition(self, cond: ConditionDSL, results: dict[str, NodeResult]) -> bool:
        """Evaluates restricted declarative condition DSL without eval/exec."""
        left_val = self._resolve_operand(cond.left, results)
        right_val = self._resolve_operand(cond.right, results) if cond.right is not None else None

        op = cond.operator
        if op == ConditionOperator.EQ:
            return left_val == right_val
        elif op == ConditionOperator.NE:
            return left_val != right_val
        elif op == ConditionOperator.GT:
            return left_val > right_val if (left_val is not None and right_val is not None) else False
        elif op == ConditionOperator.GTE:
            return left_val >= right_val if (left_val is not None and right_val is not None) else False
        elif op == ConditionOperator.LT:
            return left_val < right_val if (left_val is not None and right_val is not None) else False
        elif op == ConditionOperator.LTE:
            return left_val <= right_val if (left_val is not None and right_val is not None) else False
        elif op == ConditionOperator.EXISTS:
            return left_val is not None
        elif op == ConditionOperator.NOT_EXISTS:
            return left_val is None
        elif op == ConditionOperator.IS_TRUE:
            return bool(left_val) is True
        elif op == ConditionOperator.IS_FALSE:
            return bool(left_val) is False
        return False

    def _resolve_operand(self, operand: Any, results: dict[str, NodeResult]) -> Any:
        if isinstance(operand, ValueBinding):
            upstream = results.get(operand.node_id)
            if not upstream or upstream.state != NodeState.SUCCESS:
                return None
            val, err = self._resolve_output_path(upstream.output, operand.output_path)
            return val if not err else None
        return operand

    def _skip_transitive_dependents(
        self,
        failed_id: str,
        dependents_map: dict[str, list[str]],
        node_map: dict[str, TaskNode],
        node_results: dict[str, NodeResult],
    ):
        """Recursively marks all transitive dependents of a failed node as skipped."""
        stack = list(dependents_map.get(failed_id, []))
        while stack:
            downstream = stack.pop()
            if downstream not in node_results:
                node_results[downstream] = NodeResult(
                    node_id=downstream,
                    tool=node_map[downstream].tool,
                    state=NodeState.SKIPPED_DEPENDENCY_FAILED,
                    error=f"Blocked because dependency '{failed_id}' failed or was skipped",
                )
                stack.extend(dependents_map.get(downstream, []))

    def _block_dependents_for_ambiguity(
        self,
        ambiguous_node_id: str,
        dependents_map: dict[str, list[str]],
        node_map: dict[str, TaskNode],
        node_results: dict[str, NodeResult],
    ):
        """Blocks dependents when search is ambiguous to prevent accidental state changes."""
        stack = list(dependents_map.get(ambiguous_node_id, []))
        while stack:
            downstream = stack.pop()
            if downstream not in node_results:
                node_results[downstream] = NodeResult(
                    node_id=downstream,
                    tool=node_map[downstream].tool,
                    state=NodeState.BLOCKED_AMBIGUOUS_INPUT,
                    error=f"Blocked because upstream search '{ambiguous_node_id}' was ambiguous",
                )
                stack.extend(dependents_map.get(downstream, []))
