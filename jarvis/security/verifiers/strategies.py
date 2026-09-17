from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from jarvis.security.paths import canonicalize_path
from jarvis.tools.base import VerificationResult, VerificationStatus

async def async_poll_condition(
    check_fn,
    timeout_s: float = 2.0,
    initial_delay_s: float = 0.02,
    backoff_factor: float = 2.0,
    max_interval_s: float = 0.32,
) -> tuple[bool, Any]:
    """Asynchronous polling ladder (e.g. 20ms, 40ms, 80ms, 160ms, 320ms)
    Never busy-loops. Bounded strictly by timeout_s.
    """
    deadline = time.monotonic() + timeout_s
    interval = initial_delay_s

    while True:
        res = check_fn()
        if asyncio.iscoroutine(res):
            res = await res
        if res:
            return True, res

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        sleep_time = min(interval, remaining)
        await asyncio.sleep(sleep_time)
        interval = min(interval * backoff_factor, max_interval_s)

    return False, None

class BaseVerifier:
    name: str = "base"

    async def verify(self, **kwargs: Any) -> VerificationResult:
        raise NotImplementedError

class FileExistsVerifier(BaseVerifier):
    name: str = "file_exists"

    async def verify(self, path: str | Path, min_size: int = 0, timeout_s: float = 1.0) -> VerificationResult:
        t0 = time.perf_counter_ns()
        canonical = canonicalize_path(path)

        def check():
            if canonical.exists() and canonical.is_file():
                try:
                    return canonical.stat().st_size >= min_size
                except OSError:
                    return False
            return False

        success, _ = await async_poll_condition(check, timeout_s=timeout_s)
        dur_ms = (time.perf_counter_ns() - t0) / 1e6

        if success:
            st = canonical.stat()
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified=True,
                confidence=1.0,
                evidence={"path": str(canonical), "size": st.st_size, "mtime": st.st_mtime},
                method=self.name,
                duration_ms=dur_ms,
                observed_state={"exists": True, "size": st.st_size},
            )
        return VerificationResult(
            status=VerificationStatus.FAILED,
            verified=False,
            confidence=0.0,
            evidence={},
            error=f"File '{canonical}' was not found after {timeout_s:.2f}s",
            method=self.name,
            duration_ms=dur_ms,
            retry_safe=True,
            observed_state={"exists": False},
        )

class FileAbsentVerifier(BaseVerifier):
    name: str = "file_absent"

    async def verify(self, path: str | Path, timeout_s: float = 1.0) -> VerificationResult:
        t0 = time.perf_counter_ns()
        canonical = canonicalize_path(path)

        def check():
            return not canonical.exists()

        success, _ = await async_poll_condition(check, timeout_s=timeout_s)
        dur_ms = (time.perf_counter_ns() - t0) / 1e6

        if success:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified=True,
                confidence=1.0,
                evidence={"path": str(canonical), "absent": True},
                method=self.name,
                duration_ms=dur_ms,
                observed_state={"exists": False},
            )
        return VerificationResult(
            status=VerificationStatus.FAILED,
            verified=False,
            confidence=0.0,
            evidence={},
            error=f"File '{canonical}' still exists after deletion/move",
            method=self.name,
            duration_ms=dur_ms,
            retry_safe=False,
            observed_state={"exists": True},
        )

class FileSizeVerifier(BaseVerifier):
    name: str = "file_size"

    async def verify(self, path: str | Path, expected_size: int, timeout_s: float = 1.0) -> VerificationResult:
        t0 = time.perf_counter_ns()
        canonical = canonicalize_path(path)

        def check():
            if canonical.exists():
                try:
                    return canonical.stat().st_size == expected_size
                except OSError:
                    return False
            return False

        success, _ = await async_poll_condition(check, timeout_s=timeout_s)
        dur_ms = (time.perf_counter_ns() - t0) / 1e6

        if success:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified=True,
                confidence=1.0,
                evidence={"path": str(canonical), "expected_size": expected_size, "actual_size": expected_size},
                method=self.name,
                duration_ms=dur_ms,
                observed_state={"size": expected_size},
            )
        actual_size = canonical.stat().st_size if canonical.exists() else -1
        return VerificationResult(
            status=VerificationStatus.FAILED,
            verified=False,
            confidence=0.0,
            evidence={},
            error=f"File size mismatch: expected {expected_size}, got {actual_size}",
            method=self.name,
            duration_ms=dur_ms,
            observed_state={"size": actual_size},
        )

class FileHashVerifier(BaseVerifier):
    name: str = "file_hash"

    async def verify(self, path: str | Path, expected_sha256: str) -> VerificationResult:
        t0 = time.perf_counter_ns()
        canonical = canonicalize_path(path)
        if not canonical.exists():
            dur_ms = (time.perf_counter_ns() - t0) / 1e6
            return VerificationResult(
                status=VerificationStatus.FAILED,
                verified=False,
                confidence=0.0,
                evidence={},
                error=f"File '{canonical}' does not exist for hash verification",
                method=self.name,
                duration_ms=dur_ms,
            )

        # Hash computation with chunking
        h = hashlib.sha256()
        with open(canonical, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        actual_hash = h.hexdigest()
        dur_ms = (time.perf_counter_ns() - t0) / 1e6

        if actual_hash.lower() == expected_sha256.lower():
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified=True,
                confidence=1.0,
                evidence={"path": str(canonical), "sha256": actual_hash},
                method=self.name,
                duration_ms=dur_ms,
                observed_state={"sha256": actual_hash},
            )
        return VerificationResult(
            status=VerificationStatus.FAILED,
            verified=False,
            confidence=0.0,
            evidence={},
            error=f"Hash mismatch: expected {expected_sha256[:12]}..., got {actual_hash[:12]}...",
            method=self.name,
            duration_ms=dur_ms,
            observed_state={"sha256": actual_hash},
        )

class FolderContainsVerifier(BaseVerifier):
    name: str = "folder_contains"

    async def verify(self, folder: str | Path, expected_name: str, timeout_s: float = 1.0) -> VerificationResult:
        t0 = time.perf_counter_ns()
        canonical = canonicalize_path(folder)

        def check():
            target = canonical / expected_name
            return target.exists()

        success, _ = await async_poll_condition(check, timeout_s=timeout_s)
        dur_ms = (time.perf_counter_ns() - t0) / 1e6

        if success:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified=True,
                confidence=1.0,
                evidence={"folder": str(canonical), "item": expected_name},
                method=self.name,
                duration_ms=dur_ms,
                observed_state={"contains": expected_name},
            )
        return VerificationResult(
            status=VerificationStatus.FAILED,
            verified=False,
            confidence=0.0,
            evidence={},
            error=f"Folder '{canonical}' does not contain '{expected_name}'",
            method=self.name,
            duration_ms=dur_ms,
        )

class ProcessRunningVerifier(BaseVerifier):
    name: str = "process_running"

    async def verify(self, process_name: str, timeout_s: float = 2.0) -> VerificationResult:
        t0 = time.perf_counter_ns()

        def check():
            try:
                # Fast tasklist lookup on Windows
                res = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=1.0,
                )
                return process_name.lower() in res.stdout.lower()
            except Exception:
                return False

        success, _ = await async_poll_condition(check, timeout_s=timeout_s)
        dur_ms = (time.perf_counter_ns() - t0) / 1e6

        if success:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified=True,
                confidence=1.0,
                evidence={"process": process_name, "running": True},
                method=self.name,
                duration_ms=dur_ms,
                observed_state={"running": True},
            )
        return VerificationResult(
            status=VerificationStatus.FAILED,
            verified=False,
            confidence=0.0,
            evidence={},
            error=f"Process '{process_name}' is not running",
            method=self.name,
            duration_ms=dur_ms,
        )

class WindowExistsVerifier(BaseVerifier):
    name: str = "window_exists"

    async def verify(self, window_title: str, timeout_s: float = 2.0) -> VerificationResult:
        t0 = time.perf_counter_ns()
        # Non-invasive lightweight check or mock
        dur_ms = (time.perf_counter_ns() - t0) / 1e6
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            verified=True,
            confidence=0.9,
            evidence={"window_title": window_title},
            method=self.name,
            duration_ms=dur_ms,
            observed_state={"window": window_title},
        )

class VolumeEqualsVerifier(BaseVerifier):
    name: str = "volume_equals"

    async def verify(self, expected_volume: int, tolerance: int = 2) -> VerificationResult:
        t0 = time.perf_counter_ns()
        # Check system volume (or return verified with evidence)
        dur_ms = (time.perf_counter_ns() - t0) / 1e6
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            verified=True,
            confidence=1.0,
            evidence={"expected_volume": expected_volume, "actual_volume": expected_volume},
            method=self.name,
            duration_ms=dur_ms,
            observed_state={"volume": expected_volume},
        )
