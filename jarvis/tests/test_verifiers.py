import asyncio
import os
import tempfile
import time
import pytest
from pathlib import Path

from jarvis.core.executor.selector import (
    CircuitBreaker,
    CircuitState,
    FailureClassifier,
    FailureClassification,
    MethodSelector,
    MethodStatsTracker,
    RetryDecision,
    RetryEngine,
)
from jarvis.security.verifiers.strategies import (
    FileAbsentVerifier,
    FileExistsVerifier,
    FileHashVerifier,
    FileSizeVerifier,
    FolderContainsVerifier,
    async_poll_condition,
)
from jarvis.tools.base import (
    Contract,
    ExecutionMethod,
    IdempotencyClass,
    RiskLevel,
    ToolDefinition,
    ToolVariant,
    VerificationStatus,
)

class DummyInput(Contract):
    pass

class DummyOutput(Contract):
    pass

@pytest.mark.asyncio
async def test_file_verifiers():
    with tempfile.TemporaryDirectory() as td:
        dir_p = Path(td)
        test_file = dir_p / "test_doc.txt"
        test_file.write_text("Hello verification engine")
        
        # 1. File exists
        fe_v = FileExistsVerifier()
        res_exists = await fe_v.verify(test_file)
        assert res_exists.verified
        assert res_exists.status == VerificationStatus.VERIFIED
        assert res_exists.evidence["size"] > 0

        # 2. File size
        fs_v = FileSizeVerifier()
        res_size = await fs_v.verify(test_file, expected_size=len("Hello verification engine"))
        assert res_size.verified

        # 3. File hash
        import hashlib
        expected_hash = hashlib.sha256(b"Hello verification engine").hexdigest()
        fh_v = FileHashVerifier()
        res_hash = await fh_v.verify(test_file, expected_sha256=expected_hash)
        assert res_hash.verified

        # 4. Folder contains
        fc_v = FolderContainsVerifier()
        res_contains = await fc_v.verify(dir_p, expected_name="test_doc.txt")
        assert res_contains.verified

        # 5. File absent after delete
        os.remove(test_file)
        fa_v = FileAbsentVerifier()
        res_absent = await fa_v.verify(test_file)
        assert res_absent.verified

@pytest.mark.asyncio
async def test_async_polling_ladder():
    # Poll condition that succeeds after 50ms
    call_count = 0
    t0 = time.monotonic()
    
    def condition():
        nonlocal call_count
        call_count += 1
        return time.monotonic() - t0 >= 0.05

    success, _ = await async_poll_condition(condition, timeout_s=1.0, initial_delay_s=0.01)
    assert success
    # Ladder shouldn't busy-loop hundreds of times; should only poll a few times
    assert call_count < 10

def test_circuit_breaker_and_quarantine():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_s=0.1)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute()

    # Record 3 failures -> trips to OPEN
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert not cb.can_execute()

    # Wait for recovery timeout
    time.sleep(0.12)
    assert cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN

    # Success closes circuit
    cb.record_success()
    assert cb.state == CircuitState.CLOSED

def test_method_selector_and_stats():
    tracker = MethodStatsTracker()
    selector = MethodSelector(stats_tracker=tracker)

    t_def = ToolDefinition(
        name="open_app",
        description="launch app",
        input_model=DummyInput,
        output_model=DummyOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        execution_method=ExecutionMethod.NATIVE,
        variants=(
            ToolVariant(method=ExecutionMethod.NATIVE, priority=1, confidence=1.0),
            ToolVariant(method=ExecutionMethod.CLI, priority=2, confidence=0.8),
        ),
    )

    # Initially prefers NATIVE
    selected = selector.select_variant(t_def)
    assert selected.method == ExecutionMethod.NATIVE

    # Record repeated failures on NATIVE to trigger quarantine
    for _ in range(5):
        tracker.record_attempt("open_app", ExecutionMethod.NATIVE.value, success=False, verified=False, duration_ms=10.0)

    assert tracker.is_quarantined("open_app", ExecutionMethod.NATIVE.value)

    # After quarantine, selector prioritizes fallback variant (CLI)
    selected_after = selector.select_variant(t_def)
    assert selected_after.method == ExecutionMethod.CLI

def test_failure_classification_and_retry_rules():
    # Classify errors
    assert FailureClassifier.classify(FileNotFoundError("not found")) == FailureClassification.NOT_FOUND
    assert FailureClassifier.classify(PermissionError("access is denied")) == FailureClassification.PERMISSION_DENIED
    assert FailureClassifier.classify(TimeoutError("operation timed out")) == FailureClassification.TIMEOUT
    assert FailureClassifier.classify("requires uac elevation") == FailureClassification.UAC_REQUIRED

    t_idem = ToolDefinition(
        name="get_info",
        description="info",
        input_model=DummyInput,
        output_model=DummyOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        idempotency=IdempotencyClass.IDEMPOTENT,
    )

    # Idempotent tool can retry
    dec = RetryEngine.decide(
        t_idem,
        attempt=1,
        failure_class=FailureClassification.TIMEOUT,
        verification_status=VerificationStatus.FAILED,
    )
    assert dec == RetryDecision.RETRY_SAME_METHOD

    t_non_idem = ToolDefinition(
        name="send_wire",
        description="wire",
        input_model=DummyInput,
        output_model=DummyOutput,
        read_only=False,
        risk=RiskLevel.EXTERNAL_EFFECT,
        idempotency=IdempotencyClass.NON_IDEMPOTENT,
    )

    # Non-idempotent tool with UNCERTAIN result MUST NEVER RETRY
    dec_non_idem = RetryEngine.decide(
        t_non_idem,
        attempt=1,
        failure_class=FailureClassification.UNCERTAIN_SIDE_EFFECT,
        verification_status=VerificationStatus.UNCERTAIN,
    )
    assert dec_non_idem == RetryDecision.DO_NOT_RETRY
