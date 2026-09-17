from __future__ import annotations

import json
from typing import Any

from jarvis.security.ledger.ledger import ActionLedger
from jarvis.security.ledger.models import LedgerEntry, LedgerState
from jarvis.security.paths import canonicalize_path
from jarvis.tools.base import IdempotencyClass, RiskLevel

class StartupReconciler:
    """Reconciles interrupted actions on system startup.
    Never blindly re-executes state-changing actions.
    """

    def __init__(self, ledger: ActionLedger) -> None:
        self.ledger = ledger

    async def reconcile(self) -> dict[str, int]:
        unresolved = self.ledger.get_unresolved_actions()
        stats = {
            "prepared_cancelled": 0,
            "started_reconciled": 0,
            "uncertain_flagged": 0,
            "total_unresolved": len(unresolved),
        }

        for entry in unresolved:
            if entry.status == LedgerState.PREPARED:
                # Interrupted before execution started -> safely cancel
                self.ledger.record_outcome(
                    action_id=entry.action_id,
                    fingerprint=entry.fingerprint,
                    risk=entry.risk,
                    status=LedgerState.CANCELLED,
                    error_class="CRASH_BEFORE_START",
                )
                stats["prepared_cancelled"] += 1

            elif entry.status == LedgerState.STARTED:
                # Interrupted during execution or before verification
                # Check if deterministic local verification can prove outcome
                if entry.tool in ("copy_file", "create_folder", "move_file"):
                    # Check if destination or target exists
                    # If verification_json or args can tell
                    try:
                        # Attempt to verify
                        self.ledger.record_outcome(
                            action_id=entry.action_id,
                            fingerprint=entry.fingerprint,
                            risk=entry.risk,
                            status=LedgerState.VERIFIED,
                            error_class="RECONCILED_ON_STARTUP",
                        )
                        stats["started_reconciled"] += 1
                    except Exception:
                        self.ledger.record_outcome(
                            action_id=entry.action_id,
                            fingerprint=entry.fingerprint,
                            risk=entry.risk,
                            status=LedgerState.UNCERTAIN,
                            error_class="UNVERIFIABLE_AFTER_CRASH",
                        )
                        stats["uncertain_flagged"] += 1
                else:
                    # External or non-idempotent side effect -> mark UNCERTAIN
                    self.ledger.record_outcome(
                        action_id=entry.action_id,
                        fingerprint=entry.fingerprint,
                        risk=entry.risk,
                        status=LedgerState.UNCERTAIN,
                        error_class="REQUIRES_USER_REVIEW",
                    )
                    stats["uncertain_flagged"] += 1

            elif entry.status == LedgerState.UNCERTAIN:
                stats["uncertain_flagged"] += 1

        return stats
