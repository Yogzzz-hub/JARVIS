# Stage 2 semantic corpus leakage audit

The 100,000-row synthetic SemanticFrame corpus was generated after the [Stage 1 public data audit](TANGLISH_DATA_AUDIT.md). Public comments were used only for aggregate language statistics. No public utterance was relabeled as a JARVIS command.

| Split | Rows | Contextual rows | No-action rows | Unique normalized skeletons |
|---|---:|---:|---:|---:|
| Train | 80,000 | 20,273 | 13,325 | 11,228 |
| Dev | 10,000 | 2,338 | 1,669 | 3,035 |
| Test | 5,000 | 1,164 | 834 | 636 |
| Locked holdout | 5,000 | 1,136 | 833 | 2,313 |

All 100,000 normalized utterance-plus-context hashes are unique. Pairwise exact-hash, structural-skeleton, and declared construction-family overlap is **zero** for all six split pairs. The audit does not publish locked examples or inspect model errors. In a sampled nearest-token Jaccard check against 2,000 train rows, the p95 was 0.682 for dev, 0.625 for test, and 0.633 for locked holdout; no sampled pair reached 0.8. All 100,000 rows had the required frame keys and a known action concept.

These checks cannot prove semantic independence or naturalness. The generator still composes examples from a finite grammar, and no human adjudication has been done. The locked holdout must not guide model selection; if its results are inspected later, it becomes exposed development material and a new holdout is needed.

Machine-readable counts and overlap checks: `data/tanglish/manifests/semantic_stage2_leakage.json`. Reproduce with `python -m scripts.audit_tanglish_semantic_stage2`.
