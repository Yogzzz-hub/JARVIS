# Connector & Orchestration Performance Benchmarks

## Benchmark Methodology
Measured using `scripts/bench_connectors.py` and `scripts/bench_orchestration.py` across 5-10 iterations reporting p50, p95, and max latencies.
External network latency is separated from internal JARVIS dispatch overhead.

## Benchmark Results

### 1. Connector Dispatch & Operations (`scripts/bench_connectors.py`)
| Operation | Domain | p50 (ms) | p95 (ms) | Max (ms) |
| :--- | :--- | :--- | :--- | :--- |
| **Connector Dispatch Overhead** | INTERNAL | 0.00 | 0.01 | 0.01 |
| **LocalSend Discovery** | LOCAL NETWORK | 1508.60 | 1513.80 | 1513.80 |
| **Memos Note Creation** | INTERNAL | 0.02 | 0.05 | 0.05 |
| **Memos Recent Retrieval** | INTERNAL | 0.03 | 0.04 | 0.04 |
| **FreshRSS News Retrieval** | INTERNET | 0.02 | 0.04 | 0.04 |
| **Notification Dispatch (ntfy)**| INTERNET | 886.84 | 922.65 | 922.65 |
| **Notification Dedup Check** | INTERNAL | 0.01 | 0.14 | 0.14 |
| **Android ADB Device Poll** | INTERNAL/USB | 79.45 | 85.62 | 85.62 |

### 2. Orchestration & Morning Workflow (`scripts/bench_orchestration.py`)
| Operation | Domain | p50 (ms) | p95 (ms) | Max (ms) |
| :--- | :--- | :--- | :--- | :--- |
| **Morning Workflow Parallel Gather** | INTERNAL/PARALLEL | 5.54 | 6.24 | 6.24 |
| **PC Health Metric Sampling** | INTERNAL | 3.97 | 6.28 | 6.28 |
| **Recent Downloads Scan** | INTERNAL | 4.10 | 4.48 | 4.48 |
| **Contextual Follow-up Resolution** | INTERNAL | 0.01 | 0.02 | 0.02 |
| **Lane 0 Routing ('show phone')** | INTERNAL | 0.01 | 0.10 | 0.10 |
| **Lane 0 Routing ('good morning')** | INTERNAL | 0.01 | 0.01 | 0.01 |
| **Lane 0 Routing ('send to phone')**| INTERNAL | 0.01 | 0.04 | 0.04 |

### Summary
All internal routing, dispatching, and orchestration operations execute with sub-millisecond to under 6ms overhead, leaving everyday voice commands completely unimpeded.
