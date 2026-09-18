# TREC DL 2019: jev-full

Status: complete

| Metric | Value |
| --- | ---: |
| ndcg_cut_10 | 0.6835 |
| map | 0.4729 |
| Rprec | 0.4845 |
| P_10 | 0.6163 |
| bpref | 0.5238 |
| recip_rank | 0.8447 |
| recall_100 | 0.5980 |
| recall_1000 | 0.6943 |

Binary metrics use passage grades >= 2; nDCG uses original graded judgments.

| Measurement | Value |
| --- | ---: |
| queries | 43 |
| candidate_pairs | 41042 |
| scoring_calls | 41042 |
| rerank_seconds | 1575.1114128751215 |
| query_p50_seconds | 38.07501312484965 |
| query_p95_seconds | 39.90373656293377 |
| api_attempts | 41045 |
| failed_api_attempts | 3 |
| cache_hits | 0 |
| estimated_new_api_cost_usd | 0.7610274840000001 |

Local compute cost and supplied-candidate retrieval time are unknown. No end-to-end search time is claimed.
One measured inference run; setup and cache scope are recorded in [manifest.json](manifest.json).
Evidence: [run](run.trec), [graded evaluation](trec_eval-graded.txt), [binary evaluation](trec_eval-binary.txt), [query timings](queries.json).
