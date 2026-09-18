# TREC DL 2019: jev-matched

Status: complete

| Metric | Value |
| --- | ---: |
| ndcg_cut_10 | 0.6825 |
| map | 0.4748 |
| Rprec | 0.4805 |
| P_10 | 0.6116 |
| bpref | 0.5220 |
| recip_rank | 0.8594 |
| recall_100 | 0.5989 |
| recall_1000 | 0.6943 |

Binary metrics use passage grades >= 2; nDCG uses original graded judgments.

| Measurement | Value |
| --- | ---: |
| queries | 43 |
| candidate_pairs | 41042 |
| scoring_calls | 41042 |
| rerank_seconds | 1633.4287447908428 |
| query_p50_seconds | 37.46178420819342 |
| query_p95_seconds | 38.57392560055014 |
| api_attempts | 41045 |
| failed_api_attempts | 3 |
| cache_hits | 0 |
| estimated_new_api_cost_usd | 0.7629909420000001 |

Local compute cost and supplied-candidate retrieval time are unknown. No end-to-end search time is claimed.
One measured inference run; setup and cache scope are recorded in [manifest.json](manifest.json).
Evidence: [run](run.trec), [graded evaluation](trec_eval-graded.txt), [binary evaluation](trec_eval-binary.txt), [query timings](queries.json).
