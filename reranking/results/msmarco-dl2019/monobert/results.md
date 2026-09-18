# TREC DL 2019: monobert

Status: complete

| Metric | Value |
| --- | ---: |
| ndcg_cut_10 | 0.7177 |
| map | 0.4488 |
| Rprec | 0.4650 |
| P_10 | 0.6233 |
| bpref | 0.4807 |
| recip_rank | 0.8717 |
| recall_100 | 0.5854 |
| recall_1000 | 0.6943 |

Binary metrics use passage grades >= 2; nDCG uses original graded judgments.

| Measurement | Value |
| --- | ---: |
| queries | 43 |
| candidate_pairs | 41042 |
| scoring_calls | 41042 |
| rerank_seconds | 969.8318375840317 |
| query_p50_seconds | 22.463440500199795 |
| query_p95_seconds | 28.01995413757395 |
| api_attempts | 0 |
| failed_api_attempts | 0 |
| cache_hits | 0 |
| estimated_new_api_cost_usd | 0.0 |

Local compute cost and supplied-candidate retrieval time are unknown. No end-to-end search time is claimed.
One measured inference run; setup and cache scope are recorded in [manifest.json](manifest.json).
Evidence: [run](run.trec), [graded evaluation](trec_eval-graded.txt), [binary evaluation](trec_eval-binary.txt), [query timings](queries.json).
