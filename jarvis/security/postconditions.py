from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from jarvis.security.paths import canonicalize_path
from jarvis.security.verifiers.strategies import (
    FileAbsentVerifier,
    FileExistsVerifier,
    FileSizeVerifier,
    ProcessRunningVerifier,
)
from jarvis.tools.base import VerificationResult, VerificationStatus, VerificationStrength

file_exists_verifier = FileExistsVerifier()
file_absent_verifier = FileAbsentVerifier()
file_size_verifier = FileSizeVerifier()
process_running_verifier = ProcessRunningVerifier()

async def verify_postconditions(
    tool_name: str,
    args: dict[str, Any],
    execution_result: dict[str, Any] | None = None,
    strength: VerificationStrength = VerificationStrength.BASIC,
    timeout_s: float = 2.0,
) -> VerificationResult:
    """Verifies postconditions deterministically using the cheapest verification strategy first."""
    t0 = time.perf_counter_ns()
    tn = tool_name.lower()

    if tn in ("move_file", "move"):
        dst = args.get("destination") or args.get("dest")
        src = args.get("source") or args.get("path")
        # 1. Verify destination exists
        v_dst = await file_exists_verifier.verify(dst, timeout_s=timeout_s)
        if not v_dst.verified:
            return v_dst
        # 2. Verify source is absent
        v_src = await file_absent_verifier.verify(src, timeout_s=timeout_s)
        if not v_src.verified:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                verified=False,
                confidence=0.5,
                evidence={"destination": str(dst), "source_still_present": True},
                error="Move partially succeeded: destination created but source remains",
                method="move_postcondition",
                duration_ms=(time.perf_counter_ns() - t0) / 1e6,
            )
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            verified=True,
            confidence=1.0,
            evidence={"source_absent": True, "destination_present": True, "path": str(dst)},
            method="move_postcondition",
            duration_ms=(time.perf_counter_ns() - t0) / 1e6,
            observed_state={"destination": str(dst)},
        )

    if tn in ("copy_file", "copy"):
        dst = args.get("destination") or args.get("dest")
        v_dst = await file_exists_verifier.verify(dst, timeout_s=timeout_s)
        if not v_dst.verified:
            return v_dst
        # If strong verification requested, verify size
        src = args.get("source") or args.get("path")
        if strength == VerificationStrength.STRONG and src:
            src_p = canonicalize_path(src)
            if src_p.exists():
                expected_size = src_p.stat().st_size
                v_size = await file_size_verifier.verify(dst, expected_size=expected_size, timeout_s=timeout_s)
                if not v_size.verified:
                    return v_size
        return v_dst

    if tn in ("delete_file", "delete", "remove_file", "remove"):
        target = args.get("path") or args.get("target")
        return await file_absent_verifier.verify(target, timeout_s=timeout_s)

    if tn in ("create_folder", "mkdir"):
        path = args.get("path")
        p = canonicalize_path(path)
        if p.exists() and p.is_dir():
            dur_ms = (time.perf_counter_ns() - t0) / 1e6
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified=True,
                confidence=1.0,
                evidence={"path": str(p), "is_dir": True},
                method="folder_exists",
                duration_ms=dur_ms,
                observed_state={"folder_exists": True},
            )
        return VerificationResult(
            status=VerificationStatus.FAILED,
            verified=False,
            confidence=0.0,
            evidence={},
            error=f"Directory '{p}' was not created",
            method="folder_exists",
            duration_ms=(time.perf_counter_ns() - t0) / 1e6,
        )

    if tn in ("open_app", "launch_app"):
        app_name = args.get("name") or args.get("app") or ""
        if execution_result and ("pid" in execution_result or "target" in execution_result):
            dur_ms = (time.perf_counter_ns() - t0) / 1e6
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified=True,
                confidence=1.0,
                evidence=execution_result,
                method="open_app_receipt",
                duration_ms=dur_ms,
                observed_state=execution_result,
            )
        # Check if process is running if an executable name is given
        if app_name.endswith(".exe"):
            return await process_running_verifier.verify(app_name, timeout_s=timeout_s)
        dur_ms = (time.perf_counter_ns() - t0) / 1e6
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            verified=True,
            confidence=0.9,
            evidence={"app": app_name, "launched": True},
            method="open_app_basic",
            duration_ms=dur_ms,
            observed_state={"launched": True},
        )

    # Default verification for general tools with non-empty results
    dur_ms = (time.perf_counter_ns() - t0) / 1e6
    if execution_result:
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            verified=True,
            confidence=1.0,
            evidence={"result_keys": list(execution_result.keys())},
            method="default_result_evidence",
            duration_ms=dur_ms,
            observed_state={"executed": True},
        )
    return VerificationResult(
        status=VerificationStatus.VERIFIED,
        verified=True,
        confidence=0.8,
        evidence={"executed": True},
        method="default_heuristic",
        duration_ms=dur_ms,
        observed_state={"executed": True},
    )
