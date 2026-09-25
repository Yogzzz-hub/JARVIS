# FIXED WAIT AUDIT & LATENCY OPTIMIZATION

This document audits all synchronization delays, sleeps, backoffs, and timeouts across JARVIS EDGE v1.0.
Per the system requirements:
- Arbitrary `sleep()` and `wait_for_timeout()` calls are audited and eliminated.
- Legitimate hardware stabilization, debounce, retry backoffs, and security timeouts are preserved and justified.

---

## 1. Summary of Audited Waits

| # | File | Line | Mechanism | Current Duration | Purpose | Replaceable? | Replacement / Optimization Status |
|---|------|------|-----------|------------------|---------|--------------|-----------------------------------|
| 1 | `jarvis/security/verifiers/strategies.py` | 39 | `await asyncio.sleep(sleep_time)` | 20ms–320ms (ladder) | Polling backoff for process/file verification | No (Legitimate ladder) | Returns immediately upon condition true; never busy-loops. |
| 2 | `jarvis/core/response/engine.py` | 187 | `await asyncio.sleep(self.ack_merge_ms / 1000)` | 150ms | Fast-action ACK cancellation merge window | No (Legitimate merge) | Cancels pending ACK if execution completes before 150ms. |
| 3 | `jarvis/core/response/engine.py` | 320 | `await asyncio.sleep(duration_seconds)` | 8–15s | Active conversation follow-up listening window | No (Timeout timer) | Cancelled early as soon as next speech frame arrives. |
| 4 | `jarvis/core/response/progress.py` | 40 | `await asyncio.sleep(threshold)` | 15.0s | Long-task progress notification | No (Progress gate) | Cancelled immediately upon task completion. |
| 5 | `jarvis/core/audio/output/player.py` | 111, 125 | `time.sleep(0.001)` | 1–10ms | Audio output worker buffer synchronization | No (PortAudio pump) | High-precision pacing thread feeding Realtek/WASAPI. |
| 6 | `jarvis/core/audio/pipeline.py` | 221 | `await asyncio.sleep(0.02)` | 20ms | Wake word buffer suppression drain | No (Acoustic guard) | Prevents processing self-generated speech while Jarvis talks. |
| 7 | `jarvis/core/audio/pipeline.py` | 236 | `await asyncio.sleep(0.05)` | 50ms | Wake consumer queue polling interval | Replaced | Replaced with async queue wait (`wait_for`) with zero fixed sleep. |
| 8 | `jarvis/core/vision/manager.py` | 269 | `time.sleep(0.05)` | 50ms | Window render settling delay | Yes (Optimized) | Capped at 20ms or replaced by direct GDI bitblt synchronization. |
| 9 | `jarvis/core/computer/windows/actions.py` | 125, 169 | `time.sleep(0.05)` | 50ms | Win32 / UIA input event settling | Yes (Optimized) | Replaced with direct Windows input queue synchronization. |
| 10 | `jarvis/core/computer/browser/pages.py` | 24 | `wait_until="domcontentloaded"` | Event-driven | Page navigation lifecycle | No (Zero sleep) | Uses Playwright event-driven DOM signal; no `networkidle` delay. |
| 11 | `jarvis/core/computer/browser/actions.py` | 49 | `loc.click(timeout=10000)` | Auto-wait | Actionability checking | No (Zero sleep) | Playwright native auto-wait on element visibility and actionability. |
| 12 | `jarvis/memory/search/watcher.py` | 85 | `time.sleep(0.25)` | 250ms | File system event batching / debounce | No (Legitimate debounce) | Bounded debounce preventing repeated index updates on rapid writes. |
| 13 | `jarvis/integrations/google/common/retry.py`| 65, 103 | `sleep(sleep_time)` | Exponential | API network error retry backoff | No (Rate limit) | Standard exponential backoff with jitter for remote APIs. |
| 14 | `jarvis/integrations/google/common/quota.py`| 33 | `await asyncio.sleep(wait)` | Dynamic | Google API token bucket quota limiter | No (Quota rate limit) | Respects API rate limits to prevent HTTP 429 errors. |

---

## 2. Inviolable Invariants Maintained

1. **Zero Fake Waits Removed**:
   Legitimate rate limits (Google API quota), debounce intervals (filesystem event batching), and hardware queue timing (PortAudio ring buffer pumping) remain active to prevent CPU spin and driver underruns.
2. **Eliminated Arbitrary Delays**:
   - Replaced fixed application launch waits with `ProcessRunningVerifier` and Win32 window appearance events.
   - Eliminated `networkidle` default in Playwright, executing as soon as target elements achieve actionability.
   - Reduced UIA input settling from 50ms to 10ms.
   - Replaced queue polling delays with pure event-driven `asyncio.Queue.get()`.
