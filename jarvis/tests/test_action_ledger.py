import os
import tempfile
import pytest
from pathlib import Path

from jarvis.security.ledger.ledger import ActionLedger
from jarvis.security.ledger.models import LedgerState
from jarvis.security.recovery import StartupReconciler
from jarvis.tools.base import IdempotencyClass, RiskLevel

@pytest.fixture
def temp_ledger():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
    ledger = ActionLedger(db_path=db_path)
    yield ledger
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass

def test_ledger_preparation_and_commit(temp_ledger):
    ledger = temp_ledger
    entry = ledger.prepare_action(
        action_id="act_001",
        fingerprint="fp_abc123",
        request_id="req_1",
        graph_id="grp_1",
        node_id="n1",
        tool="copy_file",
        risk=RiskLevel.EXTERNAL_EFFECT,
        idempotency=IdempotencyClass.VERIFY_BEFORE_RETRY,
        args_hash="hash_123",
    )
    assert entry.status == LedgerState.PREPARED

    # Transition to STARTED
    ledger.start_action("act_001", "fp_abc123", RiskLevel.EXTERNAL_EFFECT)
    stored = ledger.get_entry_by_id("act_001")
    assert stored is not None
    assert stored.status == LedgerState.STARTED

    # Transition to VERIFIED
    ledger.record_outcome("act_001", "fp_abc123", RiskLevel.EXTERNAL_EFFECT, LedgerState.VERIFIED)
    stored_v = ledger.get_entry_by_id("act_001")
    assert stored_v.status == LedgerState.VERIFIED

def test_duplicate_guard(temp_ledger):
    ledger = temp_ledger
    fp = "fp_unique_email_send"
    ledger.prepare_action(
        action_id="act_002",
        fingerprint=fp,
        request_id="req_2",
        graph_id="grp_2",
        node_id="n2",
        tool="send_email",
        risk=RiskLevel.EXTERNAL_EFFECT,
        idempotency=IdempotencyClass.NON_IDEMPOTENT,
        args_hash="h2",
    )
    ledger.start_action("act_002", fp, RiskLevel.EXTERNAL_EFFECT)
    ledger.record_outcome("act_002", fp, RiskLevel.EXTERNAL_EFFECT, LedgerState.VERIFIED)

    # Check duplicate
    is_dup, prior = ledger.check_duplicate(fp)
    assert is_dup
    assert prior is not None
    assert prior.action_id == "act_002"
    assert prior.status == LedgerState.VERIFIED

def test_duplicate_uncertain_guard(temp_ledger):
    ledger = temp_ledger
    fp = "fp_timeout_action"
    ledger.prepare_action(
        action_id="act_003",
        fingerprint=fp,
        request_id="req_3",
        graph_id="grp_3",
        node_id="n3",
        tool="send_message",
        risk=RiskLevel.EXTERNAL_EFFECT,
        idempotency=IdempotencyClass.NON_IDEMPOTENT,
        args_hash="h3",
    )
    ledger.start_action("act_003", fp, RiskLevel.EXTERNAL_EFFECT)
    ledger.record_outcome("act_003", fp, RiskLevel.EXTERNAL_EFFECT, LedgerState.UNCERTAIN)

    # Duplicate check for uncertain non-idempotent action
    is_dup, prior = ledger.check_duplicate(fp)
    assert is_dup
    assert prior is not None
    assert prior.status == LedgerState.UNCERTAIN

@pytest.mark.asyncio
async def test_startup_reconciliation_crash_before_start(temp_ledger):
    ledger = temp_ledger
    # Crash while in PREPARED state (before action began)
    ledger.prepare_action(
        action_id="act_crash_prep",
        fingerprint="fp_crash1",
        request_id="req_crash",
        graph_id="grp_crash",
        node_id="n_crash",
        tool="delete_file",
        risk=RiskLevel.DESTRUCTIVE,
        idempotency=IdempotencyClass.VERIFY_BEFORE_RETRY,
        args_hash="h_crash",
    )

    reconciler = StartupReconciler(ledger)
    stats = await reconciler.reconcile()
    assert stats["prepared_cancelled"] == 1

    entry = ledger.get_entry_by_id("act_crash_prep")
    assert entry.status == LedgerState.CANCELLED

@pytest.mark.asyncio
async def test_startup_reconciliation_crash_during_execution(temp_ledger):
    ledger = temp_ledger
    # Crash while in STARTED state
    ledger.prepare_action(
        action_id="act_crash_start",
        fingerprint="fp_crash2",
        request_id="req_crash2",
        graph_id="grp_crash2",
        node_id="n_crash2",
        tool="send_external_payload",
        risk=RiskLevel.EXTERNAL_EFFECT,
        idempotency=IdempotencyClass.NON_IDEMPOTENT,
        args_hash="h_crash2",
    )
    ledger.start_action("act_crash_start", "fp_crash2", RiskLevel.EXTERNAL_EFFECT)

    reconciler = StartupReconciler(ledger)
    stats = await reconciler.reconcile()
    assert stats["uncertain_flagged"] == 1

    entry = ledger.get_entry_by_id("act_crash_start")
    assert entry.status == LedgerState.UNCERTAIN
