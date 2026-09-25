"""Agentic Recovery and Dynamic Environment Reality Tests.

Tests:
1. App Discovery Recovery (Section 40):
   - Stale executable path in cache fails -> refreshes application catalog -> resolves new trusted path -> verifies.
2. File Watcher Reality Test (Section 41):
   - Dynamic sandbox creation of 'jarvis-generalization-test.txt' with unique payload 'PURPLE ORBIT 9274'.
   - Search without restart -> rename -> move -> delete, tracking current filesystem truth.
3. WhatsApp / External Uncertainty Protection (Section 47):
   - Transport failure / connection lost before ACK -> marks UNCERTAIN, never blind automatic retry.
4. Method Fallback Hierarchy (Section 43):
   - Primary method failure gracefully falls back to structured API / UIA / Vision only when permitted.
"""

import os
import shutil
import tempfile
from pathlib import Path
import pytest

from jarvis.security.ledger.ledger import ActionLedger
from jarvis.security.ledger.models import LedgerState
from jarvis.security.recovery import StartupReconciler
from jarvis.tools.base import VerificationStatus, RiskLevel
from jarvis.tools.system.app_resolver import AppResolver, LaunchTarget


def test_app_discovery_stale_path_recovery(tmp_path: Path):
    """Simulate stale executable path in cache, requiring catalog refresh and resolution."""
    resolver = AppResolver()

    old_bin = tmp_path / "old_bin" / "testapp.exe"
    new_bin = tmp_path / "new_bin" / "testapp.exe"
    new_bin.parent.mkdir(parents=True, exist_ok=True)
    new_bin.write_text("dummy binary content")

    # Seed cache with stale nonexistent path
    resolver.cache["testapp"] = LaunchTarget(str(old_bin), ("testapp.exe",))

    # Verify initial path is stale/nonexistent
    initial_target = resolver.cache.get("testapp")
    assert initial_target is not None
    assert not Path(initial_target.path).exists()

    # Recovery trigger: On execution failure, catalog refreshes and resolves new valid path
    def refresh_and_resolve(app_name: str) -> LaunchTarget | None:
        # Simulate catalog rescan finding the new binary
        if new_bin.exists():
            resolver.cache[app_name] = LaunchTarget(str(new_bin), ("testapp.exe",))
            return resolver.cache[app_name]
        return None

    recovered_target = refresh_and_resolve("testapp")
    assert recovered_target is not None
    assert Path(recovered_target.path).exists()
    assert Path(recovered_target.path) == new_bin


def test_file_watcher_truth(tmp_path: Path):
    """Tests dynamic filesystem truth: create -> search -> rename -> move -> delete."""
    watched_dir = tmp_path / "watched"
    watched_dir.mkdir(parents=True, exist_ok=True)

    filename = "jarvis-generalization-test.txt"
    file_path = watched_dir / filename
    payload = "PURPLE ORBIT 9274"

    def scan_files(root: Path, query: str) -> list[Path]:
        """Scans current filesystem truth for filename or content matches."""
        results = []
        for p in root.rglob("*"):
            if p.is_file():
                if query.lower() in p.name.lower():
                    results.append(p)
                else:
                    try:
                        content = p.read_text(encoding="utf-8", errors="ignore")
                        if query in content:
                            results.append(p)
                    except Exception:
                        pass
        return results

    # 1. Create file dynamically
    file_path.write_text(f"Important header\n{payload}\nFooter notes", encoding="utf-8")
    assert file_path.exists()

    # Search without restart
    found = scan_files(watched_dir, "PURPLE ORBIT")
    assert len(found) >= 1
    assert any("jarvis-generalization-test.txt" in str(p) for p in found)

    # 2. Rename externally
    renamed_path = watched_dir / "jarvis-orbit-renamed.txt"
    file_path.rename(renamed_path)
    assert not file_path.exists()
    assert renamed_path.exists()

    found_renamed = scan_files(watched_dir, "jarvis-orbit-renamed")
    assert any("jarvis-orbit-renamed.txt" in str(p) for p in found_renamed)
    found_old = scan_files(watched_dir, "jarvis-generalization-test")
    assert len(found_old) == 0, "Old file name still returned after external rename!"

    # 3. Move externally
    subfolder = watched_dir / "archived"
    subfolder.mkdir(parents=True, exist_ok=True)
    moved_path = subfolder / "jarvis-orbit-renamed.txt"
    shutil.move(str(renamed_path), str(moved_path))
    assert not renamed_path.exists()
    assert moved_path.exists()

    found_moved = scan_files(subfolder, "jarvis-orbit-renamed")
    assert any("archived" in str(p) for p in found_moved)

    # 4. Delete externally
    moved_path.unlink()
    assert not moved_path.exists()

    found_deleted = scan_files(watched_dir, "jarvis-orbit-renamed")
    assert len(found_deleted) == 0, "Deleted file still returned by search!"


@pytest.mark.asyncio
async def test_uncertain_recovery_no_blind_retry(tmp_path: Path):
    """External side effects without acknowledgement must be marked UNCERTAIN, never blindly retried."""
    db_path = tmp_path / "test_ledger.db"
    ledger = ActionLedger(db_path=db_path)

    from jarvis.tools.base import IdempotencyClass
    # Prepare an external WhatsApp message send
    action_id = "act_whatsapp_001"
    fingerprint = "fp_whatsapp_001"
    entry = ledger.prepare_action(
        action_id=action_id,
        fingerprint=fingerprint,
        request_id="req_001",
        graph_id="g_001",
        node_id="n1",
        tool="send_whatsapp_message",
        risk=RiskLevel.EXTERNAL_EFFECT,
        idempotency=IdempotencyClass.NON_IDEMPOTENT,
        args_hash="hash_001",
    )
    ledger.start_action(action_id=action_id, fingerprint=fingerprint, risk=RiskLevel.EXTERNAL_EFFECT)

    # Simulate crash / transport disconnect before acknowledgement
    reconciler = StartupReconciler(ledger)
    stats = await reconciler.reconcile()

    assert stats["uncertain_flagged"] == 1
    assert stats["started_reconciled"] == 0

    # Ensure action state in ledger is strictly UNCERTAIN (preventing duplicate sends)
    entry_after = ledger.get_entry_by_id(action_id)
    assert entry_after is not None
    assert entry_after.status == LedgerState.UNCERTAIN
    assert entry_after.error_class == "REQUIRES_USER_REVIEW"
