# JARVIS EDGE — Generalization Torture Test Benchmark Report

**Dataset Directory**: `tests\generalization`
**Total Queries Evaluated**: 105
**Total Passed**: 97
**Overall Accuracy**: 92.38%

---

## 1. Latency Profile
- **Router Latency (p50)**: 51.751 ms
- **Router Latency (p95)**: 121.301 ms

## 2. Capability Retrieval Benchmark
- **Primary Recall@1**: 90.32%
- **Primary Recall@3**: 93.55%
- **Primary Recall@5**: 93.55%
- **Primary Recall@10**: 96.77%

### Multi-Capability Coverage
- **Required Capability Coverage@3**: 93.55%
- **Required Capability Coverage@5**: 93.55%
- **Required Capability Coverage@10**: 96.77%
- **Deterministic Route Bypasses**: 19

## 3. Slot Extraction Benchmark
- **Precision**: 100.0%
- **Recall**: 100.0%
- **F1 Score**: 100.0%


## 4. Safety & Security Verification
- **Wrong Actions**: 1
- **Wrong Consequential Actions**: 0
- **Tool Hallucinations**: 0
- **Executed Hallucinated Tools**: 0
- **External Injection Executions**: 0
- **Confirmation Bypasses**: 0

## 5. Root Cause Classification of Failures
- **ROUTER**: 8
