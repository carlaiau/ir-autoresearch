# Stage-1 results

| Run | MAP | Search timing | Role |
| --- | ---: | --- | --- |
| [Integrated main, reranking off](integrated-main-20260918/results.md) | 0.2521 | Single pass in manifest | Current main feedback, new candidate cohort |
| [Pre-JEV](pre-jev/results.md) | 0.2402 | Unknown for this run | Preserved historical input |
| [Fresh lexical baseline](lexical-baseline-20260918/results.md) | 0.2402 | Single pass in manifest; [five-run median 0.22 s](lexical-baseline-20260918/benchmark.md) | Independently reproducible stage-1 input |

The two pre-integration saved candidate files have the same SHA-256. The
integrated-main run has a different candidate hash and must be compared separately. New runs create their own
branch/run-id directories. Raw trec_eval and TREC runs accompany each report.
