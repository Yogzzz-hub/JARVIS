import asyncio
from pathlib import Path
import psutil
from jarvis.core.metrics.clock import now_ns
from jarvis.tools.base import VerificationResult

def process_evidence(data):
    names = set(data["process_names"])
    pid = data.get("pid")
    if pid:
        try:
            proc = psutil.Process(pid)
            if proc.is_running() and proc.name().casefold() in names:
                return {"pid": pid, "process": proc.name(), "criterion": "matching process exists"}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # A launcher may hand off to a single-instance / packaged process.
            pass
    for proc in psutil.process_iter(attrs=["pid", "name"], ad_value=None):
        if (proc.info["name"] or "").casefold() in names:
            return {"pid": proc.info["pid"], "process": proc.info["name"], "criterion": "matching process exists"}
    return None

class Verifier:
    def __init__(self, poll_ms=50, timeout_ms=3000, probe=process_evidence):
        self.poll_s, self.timeout_s = poll_ms / 1000, timeout_ms / 1000
        self.probe = probe

    async def verify(self, tool_name, result, arguments, cancellation):
        start = now_ns()
        evidence = None
        error = None
        if cancellation.is_set():
            raise asyncio.CancelledError
        if tool_name == "open_app":
            if not result.data.get("process_names"):
                error = "Shortcut launched, but its process identity is unknown; cannot verify."
            else:
                try:
                    async with asyncio.timeout(self.timeout_s):
                        while not evidence:
                            if cancellation.is_set():
                                raise asyncio.CancelledError
                            evidence = await asyncio.to_thread(self.probe, result.data)
                            if not evidence:
                                try:
                                    await asyncio.wait_for(cancellation.wait(), self.poll_s)
                                except TimeoutError:
                                    continue
                except TimeoutError:
                    error = "No matching application process observed before verification deadline."
        elif tool_name == "volume_set":
            from jarvis.tools.system.native import volume
            actual = await asyncio.to_thread(volume)
            if abs(actual - arguments.percent) <= 1:
                evidence = {"readback_percent": actual}
            else:
                error = f"Volume readback differs: {actual:.1f}%"
        elif tool_name == "take_screenshot":
            def inspect():
                path = Path(result.data["path"])
                with path.open("rb") as file:
                    signature = file.read(8)
                return path.stat().st_size, signature
            size, signature = await asyncio.to_thread(inspect)
            if signature == b"\x89PNG\r\n\x1a\n" and size == result.data["bytes"]:
                evidence = {"path": result.data["path"], "bytes": size, "png_signature": True}
            else:
                error = "Screenshot file verification failed"
        else:
            evidence = {"criterion": "native read completed and output schema validated", "tool": tool_name}
        return VerificationResult(verified=bool(evidence), confidence=1.0 if evidence else 0.0,
                                  evidence=evidence or {}, error=error,
                                  duration_ms=(now_ns() - start) / 1e6)
