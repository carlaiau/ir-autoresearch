# Reranking results

Full-document monoBERT has completed its first exploratory WSJ evaluation on the
fixed [stage-1 baseline](../../stage1/results/integrated-main-20260918/results.md),
MAP **0.2521**. Previous JEV results were discarded; its rerun is still pending.

| Method | Status | MAP | Added search time, all 50 queries | Cost |
| --- | --- | --- | --- | --- |
| JEV pointwise, top 100 | Rerun pending | Pending | Pending | Pending |
| [monoBERT MaxP, top 100](monobert-maxp-top100-20260918/results.md) | Evaluated, Apple M3 Pro GPU | **0.2693** | **1,510.93 s** | Hosted API $0; local compute unknown |
| duoBERT | Planned | Pending | Pending | Pending |

monoBERT made **19,593 passage scores / 2,475 model calls** with full token coverage
of all 5,000 query/document pairs. Median per-query time was **30.27 s**, excluding
shared setup; p95 was **42.19 s**. This is a single uncached float32 run, not a
repeated benchmark median. Local compute cost remains unknown by user choice.
See the [audit and paired analysis](monobert-maxp-top100-20260918/validation.md).

See the [JEV rerun plan](../jev.md). Completed experiments must include the
stage-1 run hash, raw trec_eval, paired effectiveness deltas, timing scope,
cache mode, token usage and cost assumptions. Cached replay is a reproducibility
check and must not be presented as uncached inference performance.
