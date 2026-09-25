# JARVIS EDGE — Generalization Torture Test Benchmark Report

**Dataset Directory**: `tests\generalization_holdout`
**Total Queries Evaluated**: 320
**Total Passed**: 251
**Overall Accuracy**: 78.44%

---

## 1. Latency Profile
- **Router Latency (p50)**: 0.761 ms
- **Router Latency (p95)**: 2.235 ms

## 2. Capability Retrieval Benchmark
- **Primary Recall@1**: 60.74%
- **Primary Recall@3**: 63.7%
- **Primary Recall@5**: 64.44%
- **Primary Recall@10**: 64.81%

### Multi-Capability Coverage
- **Required Capability Coverage@3**: 68.09%
- **Required Capability Coverage@5**: 73.24%
- **Required Capability Coverage@10**: 73.98%
- **Deterministic Route Bypasses**: 187

## 3. Slot Extraction Benchmark
- **Precision**: 100.0%
- **Recall**: 98.33%
- **F1 Score**: 99.16%


## 4. Safety & Security Verification
- **Wrong Actions**: 6
- **Wrong Consequential Actions**: 0
- **Tool Hallucinations**: 23
- **Executed Hallucinated Tools**: 0
- **External Injection Executions**: 0
- **Confirmation Bypasses**: 0

## 5. Root Cause Classification of Failures
- **ROUTER**: 69
