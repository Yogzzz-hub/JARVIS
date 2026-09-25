from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from pydantic import ValidationError

from jarvis.core.executor.selector import (
    FailureClassifier,
    FailureClassification,
    MethodSelector,
    MethodStatsTracker,
    RetryDecision,
    RetryEngine,
)
from jarvis.core.metrics.clock import now_ns
from jarvis.security.audit.logger import AuditLogger
from jarvis.security.confirmation.manager import ConfirmationManager
from jarvis.security.confirmation.models import compute_action_fingerprint
from jarvis.security.ledger.ledger import ActionLedger
from jarvis.security.ledger.models import LedgerState
from jarvis.security.paths import toctou_snapshot, verify_toctou
from jarvis.security.policy.evaluator import PolicyEvaluator
from jarvis.security.policy.models import PolicyDecisionType
from jarvis.security.postconditions import verify_postconditions
from jarvis.security.preconditions import check_preconditions
from jarvis.security.supervisor import global_supervisor
from jarvis.security.undo import UndoManager
from jarvis.tools.base import (
    ExecutionMethod,
    IdempotencyClass,
    RiskLevel,
    ToolDefinition,
    ToolResult,
    VerificationResult,
    VerificationStatus,
)

class ExecutionEngine:
    """Hardened Phase 5 Execution Engine.
    Enforces deterministic policy evaluation, confirmation tickets, pre/postconditions,
    action fingerprints, duplicate prevention, verifier cascades, structured error classification,
    and append-only audit logging.
    """

    def __init__(
        self,
        policy_evaluator: PolicyEvaluator | None = None,
        confirmation_manager: ConfirmationManager | None = None,
        ledger: ActionLedger | None = None,
        audit_logger: AuditLogger | None = None,
        undo_manager: UndoManager | None = None,
        stats_tracker: MethodStatsTracker | None = None,
    ) -> None:
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="jarvis-exec")
        self.policy_evaluator = policy_evaluator or PolicyEvaluator()
        self.confirmation_manager = confirmation_manager or ConfirmationManager()
        self.ledger = ledger or ActionLedger()
        self.audit_logger = audit_logger or AuditLogger()
        self.undo_manager = undo_manager or UndoManager()
        self.stats_tracker = stats_tracker or MethodStatsTracker()
        self.method_selector = MethodSelector(self.stats_tracker)

    async def execute(
        self,
        tool: Any,
        arguments: Any,
        task: Any = None,
        ticket_id: str | None = None,
        graph_id: str = "",
        node_id: str = "",
        dry_run_policy: bool = False,
    ) -> ToolResult:
        t0 = time.perf_counter_ns()
        definition: ToolDefinition = tool.definition
        if isinstance(arguments, dict) and hasattr(definition, "input_model"):
            try:
                arguments = definition.input_model.model_validate(arguments)
            except Exception:
                pass
        arg_dict = arguments.model_dump() if hasattr(arguments, "model_dump") else (arguments if isinstance(arguments, dict) else {})
        if ticket_id:
            arg_dict["confirmation_ticket"] = ticket_id
            if hasattr(arguments, "confirmation_ticket"):
                try:
                    arguments.confirmation_ticket = ticket_id
                except Exception:
                    pass
        request_id = getattr(task, "request_id", f"req_{uuid.uuid4().hex[:8]}") if task else f"req_{uuid.uuid4().hex[:8]}"

        # 0. Check Kill Switch / Cancellation
        if global_supervisor.is_stopped() or (task and task.cancellation and task.cancellation.is_set()):
            raise asyncio.CancelledError("Execution halted by supervisor kill switch")

        # 1. Policy Evaluation
        policy_decision = self.policy_evaluator.evaluate_node(
            definition,
            arg_dict,
            graph_id=graph_id,
            node_id=node_id,
        )

        if dry_run_policy:
            dur_ms = (time.perf_counter_ns() - t0) / 1e6
            return ToolResult(
                success=True,
                data={
                    "dry_run": True,
                    "policy_decision": policy_decision.model_dump(),
                    "tool": definition.name,
                    "risk": definition.risk.value,
                    "idempotency": definition.idempotency.value,
                    "args": arg_dict,
                },
                evidence={"dry_run_policy": True},
                duration_ms=dur_ms,
                tool_name=definition.name,
                method_used=definition.execution_method,
            )

        # Handle Policy Denials and Pauses
        if policy_decision.is_denied:
            dur_ms = (time.perf_counter_ns() - t0) / 1e6
            self.audit_logger.log(
                request_id=request_id,
                graph_id=graph_id,
                node_id=node_id,
                tool=definition.name,
                method=definition.execution_method.value,
                risk=definition.risk,
                decision=policy_decision.decision.value,
                action_fingerprint="DENIED",
                result_status="DENIED",
                verification_summary=f"Denied by rule {policy_decision.rule_id}: {policy_decision.reason_code.value}",
                duration_ms=dur_ms,
            )
            return ToolResult(
                success=False,
                error=f"Policy DENY ({policy_decision.reason_code.value}): {policy_decision.constraints.get('reason', policy_decision.rule_id)}",
                duration_ms=dur_ms,
                tool_name=definition.name,
                method_used=definition.execution_method,
            )

        if policy_decision.pauses_for_user:
            dur_ms = (time.perf_counter_ns() - t0) / 1e6
            return ToolResult(
                success=False,
                error=f"PAUSE_FOR_USER ({policy_decision.reason_code.value}): {policy_decision.constraints.get('message', 'User intervention required')}",
                duration_ms=dur_ms,
                tool_name=definition.name,
                method_used=definition.execution_method,
            )

        # 2. Action Fingerprint
        fp = compute_action_fingerprint(definition.name, arg_dict, graph_id=graph_id, node_id=node_id)

        # 3. Confirmation Ticket Validation
        if policy_decision.requires_confirmation:
            if not ticket_id:
                # Auto-issue a pending confirmation ticket bound to action fingerprint
                ticket = self.confirmation_manager.issue_ticket(
                    request_id=request_id,
                    graph_id=graph_id,
                    node_id=node_id,
                    tool_name=definition.name,
                    args=arg_dict,
                    risk=definition.risk,
                )
                dur_ms = (time.perf_counter_ns() - t0) / 1e6
                return ToolResult(
                    success=False,
                    data={
                        "confirmation_required": True,
                        "ticket_id": ticket.ticket_id,
                        "human_summary": ticket.human_summary,
                        "ticket": ticket.model_dump(mode="json"),
                    },
                    error=f"CONFIRMATION_REQUIRED: {ticket.human_summary}",
                    duration_ms=dur_ms,
                    tool_name=definition.name,
                    method_used=definition.execution_method,
                )

            valid, reason = self.confirmation_manager.consume_ticket(ticket_id, fp)
            if not valid:
                dur_ms = (time.perf_counter_ns() - t0) / 1e6
                self.audit_logger.log(
                    request_id=request_id,
                    graph_id=graph_id,
                    node_id=node_id,
                    tool=definition.name,
                    method=definition.execution_method.value,
                    risk=definition.risk,
                    decision="INVALID_CONFIRMATION",
                    confirmation_ticket_id=ticket_id,
                    action_fingerprint=fp,
                    result_status="DENIED",
                    verification_summary=f"Ticket invalid: {reason}",
                    duration_ms=dur_ms,
                )
                return ToolResult(
                    success=False,
                    error=f"Confirmation invalid: {reason}",
                    duration_ms=dur_ms,
                    tool_name=definition.name,
                    method_used=definition.execution_method,
                )

        # 4. Precondition Validation
        pre_ok, pre_err = check_preconditions(definition.name, arg_dict)
        if not pre_ok:
            dur_ms = (time.perf_counter_ns() - t0) / 1e6
            return ToolResult(
                success=False,
                error=f"Precondition failed: {pre_err}",
                duration_ms=dur_ms,
                tool_name=definition.name,
                method_used=definition.execution_method,
            )

        # 5. Duplicate Guard
        # If an explicit confirmation ticket was provided and approved, the user has directly
        # authorized this execution; do not suppress it.
        if not ticket_id:
            is_dup, prior_entry = self.ledger.check_duplicate(fp, request_id=request_id, risk=definition.risk)
            if is_dup and prior_entry:
                if prior_entry.status in (LedgerState.VERIFIED, LedgerState.COMMITTED):
                    if definition.idempotency != IdempotencyClass.NON_IDEMPOTENT or (prior_entry.request_id and prior_entry.request_id == request_id):
                        dur_ms = (time.perf_counter_ns() - t0) / 1e6
                        cached_data = json.loads(prior_entry.output_json) if prior_entry.output_json else {"duplicate_suppressed": True, "action_id": prior_entry.action_id}
                        return ToolResult(
                            success=True,
                            data=cached_data,
                            evidence={"cached_verified": True, "action_id": prior_entry.action_id},
                            duration_ms=dur_ms,
                            tool_name=definition.name,
                            method_used=definition.execution_method,
                        )
                if prior_entry.status in (LedgerState.STARTED, LedgerState.UNCERTAIN):
                    if definition.idempotency == IdempotencyClass.NON_IDEMPOTENT:
                        dur_ms = (time.perf_counter_ns() - t0) / 1e6
                        return ToolResult(
                            success=False,
                            error="Duplicate non-idempotent action in UNCERTAIN state; automatic retry forbidden",
                            duration_ms=dur_ms,
                            tool_name=definition.name,
                            method_used=definition.execution_method,
                        )

        # 6. Method Selection
        selected_variant = self.method_selector.select_variant(definition)
        method_used = (
            selected_variant.method
            if hasattr(selected_variant, "method")
            else definition.execution_method
        )

        # 7. Action Ledger PREPARED
        action_id = f"act_{uuid.uuid4().hex[:12]}"
        args_hash = hashlib.sha256(json.dumps(arg_dict, sort_keys=True, default=str).encode()).hexdigest()
        self.ledger.prepare_action(
            action_id=action_id,
            fingerprint=fp,
            request_id=request_id,
            graph_id=graph_id,
            node_id=node_id,
            tool=definition.name,
            risk=definition.risk,
            idempotency=definition.idempotency,
            args_hash=args_hash,
            confirmation_ticket=ticket_id,
            method=method_used.value,
        )

        # 8. TOCTOU Snapshot (for file destinations/sources)
        path_arg = arg_dict.get("path") or arg_dict.get("source")
        toctou_snap = toctou_snapshot(path_arg) if path_arg else None

        # 9. Execution
        self.ledger.start_action(action_id, fp, definition.risk)
        exec_output = None
        exec_err = None

        def invoke():
            if global_supervisor.is_stopped() or (task and task.cancellation.is_set()):
                raise asyncio.CancelledError
            if task and hasattr(task, "clock"):
                task.clock.tool_started_ns = now_ns()
            out = tool.run(arguments)
            validated = definition.output_model.model_validate(out)
            return validated.model_dump()

        try:
            async with asyncio.timeout(definition.timeout_s):
                async_impl = getattr(tool, "arun", None)
                if inspect.iscoroutinefunction(async_impl) or inspect.iscoroutinefunction(tool.run):
                    # Async tools (LLM, browser agent, RAG) run on the event loop; ``arun`` wins over a sync ``run``.
                    if task and hasattr(task, "clock"):
                        task.clock.tool_started_ns = now_ns()
                    out = await (async_impl(arguments) if inspect.iscoroutinefunction(async_impl) else tool.run(arguments))
                    exec_output = definition.output_model.model_validate(out).model_dump()
                else:
                    loop = asyncio.get_running_loop()
                    exec_output = await loop.run_in_executor(self.pool, invoke)
        except (ValidationError, asyncio.CancelledError):
            raise
        except Exception as e:
            exec_err = e
        finally:
            if task and hasattr(task, "clock"):
                task.clock.tool_returned_ns = now_ns()

        # Re-check TOCTOU if destructive
        if definition.risk == RiskLevel.DESTRUCTIVE and path_arg and toctou_snap:
            t_ok, t_msg = verify_toctou(path_arg, toctou_snap)
            if not t_ok:
                exec_err = RuntimeError(f"TOCTOU violation: {t_msg}")

        # 10. Postcondition Verification
        verification: VerificationResult
        if exec_err is not None:
            f_class = FailureClassifier.classify(exec_err)
            err_label = str(exec_err) or type(exec_err).__name__
            if definition.risk == RiskLevel.EXTERNAL_EFFECT and f_class == FailureClassification.TIMEOUT:
                # External side effect with timeout -> UNCERTAIN
                verification = VerificationResult(
                    status=VerificationStatus.UNCERTAIN,
                    verified=False,
                    confidence=0.0,
                    evidence={},
                    error=f"Execution timed out during external effect ({err_label}); result is UNCERTAIN",
                    method="timeout_uncertainty",
                    retry_safe=False,
                )
            else:
                verification = VerificationResult(
                    status=VerificationStatus.FAILED,
                    verified=False,
                    confidence=0.0,
                    evidence={},
                    error=err_label,
                    method="execution_exception",
                    retry_safe=definition.idempotency == IdempotencyClass.IDEMPOTENT,
                )
        else:
            verification = await verify_postconditions(
                definition.name,
                arg_dict,
                execution_result=exec_output,
                strength=definition.verification_strength,
                timeout_s=min(2.0, definition.timeout_s),
            )

        dur_ms = (time.perf_counter_ns() - t0) / 1e6

        # 11. Record Final Ledger Outcome & Audit
        final_ledger_status = (
            LedgerState.VERIFIED if verification.status == VerificationStatus.VERIFIED
            else (LedgerState.UNCERTAIN if verification.status == VerificationStatus.UNCERTAIN
                  else LedgerState.FAILED_SAFE_TO_RETRY)
        )

        self.ledger.record_outcome(
            action_id=action_id,
            fingerprint=fp,
            risk=definition.risk,
            status=final_ledger_status,
            verification_json=json.dumps(verification.model_dump(), default=str),
            error_class=verification.error,
            output_json=json.dumps(exec_output, default=str) if exec_output else None,
        )

        # Update stats
        self.stats_tracker.record_attempt(
            capability=definition.name,
            method=method_used.value,
            success=(exec_err is None),
            verified=verification.verified,
            duration_ms=dur_ms,
            uncertain=(verification.status == VerificationStatus.UNCERTAIN),
        )

        # Audit log
        self.audit_logger.log(
            request_id=request_id,
            graph_id=graph_id,
            node_id=node_id,
            tool=definition.name,
            method=method_used.value,
            risk=definition.risk,
            decision=policy_decision.decision.value,
            action_fingerprint=fp,
            result_status=final_ledger_status.value,
            confirmation_ticket_id=ticket_id,
            verification_summary=json.dumps(verification.evidence) if verification.evidence else verification.error,
            duration_ms=dur_ms,
        )

        # Create ActionReceipt for Undo
        if verification.verified and definition.risk != RiskLevel.READ_ONLY:
            self.undo_manager.create_receipt(
                action_id=action_id,
                tool_name=definition.name,
                args=arg_dict,
                summary=f"Executed {definition.name}",
                status="VERIFIED",
                verification=verification.evidence,
                rollback_supported=definition.rollback_supported,
            )

        if verification.status == VerificationStatus.UNCERTAIN:
            return ToolResult(
                success=False,
                error=verification.error or "Action outcome is UNCERTAIN. Automatic retry is prevented for safety.",
                evidence=verification.evidence,
                duration_ms=dur_ms,
                tool_name=definition.name,
                method_used=method_used,
            )

        if not verification.verified:
            return ToolResult(
                success=False,
                error=verification.error or "Verification failed",
                evidence=verification.evidence,
                duration_ms=dur_ms,
                tool_name=definition.name,
                method_used=method_used,
            )

        return ToolResult(
            success=True,
            data=exec_output or {},
            evidence=verification.evidence,
            duration_ms=dur_ms,
            tool_name=definition.name,
            method_used=method_used,
        )

    async def close(self) -> None:
        await asyncio.to_thread(self.pool.shutdown, wait=True, cancel_futures=True)
