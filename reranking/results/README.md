# Reranking results

All results below use the fixed **stage-1 MAP 0.2521** baseline. See the [JEV comparison](jev-comparison-20260918.md) for paired metrics, timing scopes and total experiment spend.

| Method | MAP | Added reranking seconds, all 50 queries | Query p50 seconds | Estimated API cost |
| --- | ---: | ---: | ---: | ---: |
| [monoBERT MaxP](monobert-maxp-top100-20260918/results.md) | 0.2693 | 1510.927 | 30.269 | $0 (local compute unknown) |
| [JEV passage MaxP](jev-passages-maxp-top100-20260918-retry/results.md) | 0.3053 | 767.726 | 14.976 | $0.605227 |
| [JEV complete document](jev-full-documents-top100-20260918/results.md) | 0.3055 | 211.493 | 4.020 | $0.328312 |
| [JEV pointwise → duo Noul (rejected)](jev-duo-noul-top20-20260918/summary.md) | 0.3019 | 1049.477 composed (837.984 duo only) | 15.050 duo only | $2.633731 composed ($2.305419 duo only) |
| duoBERT | Planned | — | — | — |

Single uncached measurements; query percentiles exclude shared setup. Local compute cost is unknown for all methods. The failed first JEV attempt is recorded separately and is included in total experiment spend, not in completed-run timing. All methods retain the original candidates and untouched tails.
