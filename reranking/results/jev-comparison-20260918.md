# JEV passage versus complete-document results

Both experiments used the frozen stage-1 top-100 candidates for all 50 topics, the same JEV relevance question, and served model **JEV 1.13.0**. No indexing or baseline changes were made.

| Method | MAP | Rprec | P_10 | bpref | recip_rank |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage 1 | 0.2521 | 0.2989 | 0.4460 | 0.3178 | 0.6271 |
| monoBERT MaxP | 0.2693 | 0.3149 | 0.4960 | 0.3368 | 0.6715 |
| JEV passage MaxP | 0.3053 | 0.3313 | 0.6000 | 0.3557 | 0.8457 |
| JEV complete document | 0.3055 | 0.3248 | 0.6340 | 0.3533 | 0.8063 |

| Measurement | JEV passage MaxP | JEV complete document |
| --- | ---: | ---: |
| Scoring units | 19,593 | 5,000 |
| API attempts | 19,593 | 5,000 |
| Failed attempts | 0 | 0 |
| Cache hits | 0 | 0 |
| Added reranking seconds | 767.726 | 211.493 |
| Composed search seconds | 768.413 | 212.180 |
| Per-query p50 seconds | 14.976 | 4.020 |
| Per-query p95 seconds | 20.906 | 4.372 |
| API cost estimate, USD | 0.60522739 | 0.32831228 |

monoBERT's local run took 1510.927 s, with query p50 30.269 s and p95 42.189 s. Its local compute cost remains unknown; zero hosted API spend does not mean free compute.

Each JEV figure is one uncached client run. Queries were processed sequentially with eight concurrent pointwise API calls within each query. monoBERT used batches of eight on the local Apple M3 Pro GPU. These measure their actual execution setups, not equal hardware or model-only speed. Query percentiles exclude shared setup; total reranking includes extraction, tokenizer/preparation, client setup, requests/retries and evidence/output writes. Provider-side caching and serving hardware are not controlled.

Whole-document scoring achieved nearly identical MAP in this evaluation with **3.63× less reranking time** and **45.8% lower estimated API cost** than passage MaxP. Passage MaxP had higher Rprec, bpref and reciprocal rank; complete documents had higher P_10. Both are retained as successful experimental variants, not as a statistically established universal winner.

## Effectiveness and coverage

JEV passage MaxP: MAP delta versus stage 1 **+0.0532** and versus monoBERT **+0.0360**. AP improved/worsened/tied versus stage 1 on **43/6/1** topics.

JEV complete document: MAP delta versus stage 1 **+0.0534** and versus monoBERT **+0.0362**. AP improved/worsened/tied versus stage 1 on **42/7/1** topics.

All 5,000 query/document pairs were scored. The passage run covers the exact 19,593 monoBERT windows and uses MaxP; the complete-document run submits every parsed article without a character cap. Both audits reconstructed the full final ranking and checked the unchanged tail. Mean candidate recall at 100 remains **0.3121**, and full-run recall is unchanged.

JEV passage payloads decode the original BERT token slices, including tokenizer normalization and possible boundary wordpiece markers. JEV retokenizes that text. Complete-document payloads use original parsed text. Thus the whole-document comparison changes context size and text representation. No claim is made that different models consumed identical token IDs. These are exploratory measurements without tuning on held-out data or statistical significance claims.

## Cost and the failed first attempt

The completed runs' successful responses cost an estimated **$0.93353967** combined at $0.042/million input tokens and free output. The [failed first passage attempt](jev-passages-maxp-top100-20260918/results.md) adds **$0.56420154**, bringing the total recorded successful-response estimate to **$1.49774121**. Across the two completed runs and the failed first attempt there were **42,839 API attempts**, including **one failed request**. Charges for failed requests are unknown; these are estimates, not invoices. Local compute cost remains unknown.

Pricing: [TypeSafe announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev), verified September 18, 2026. The first attempt stopped on a server error; SDK error compatibility was fixed and tested before running a fresh passage evaluation. Partial data and the original code are preserved in commit `1973695`. No cached continuation is presented as uncached performance.

## Evidence

- [JEV passage report](jev-passages-maxp-top100-20260918-retry/results.md), [audit](jev-passages-maxp-top100-20260918-retry/audit.json), [paired topic analysis](jev-passages-maxp-top100-20260918-retry/paired-analysis.json).
- [JEV complete-document report](jev-full-documents-top100-20260918/results.md), [audit](jev-full-documents-top100-20260918/audit.json), [paired topic analysis](jev-full-documents-top100-20260918/paired-analysis.json).
- [monoBERT report](monobert-maxp-top100-20260918/results.md).
- [Implementation and reproduction](../jev-comparison.md).

Passed: repository smoke, two-stage contracts, six monoBERT tests, five JEV comparison tests (including real SDK transient exceptions), dependency checks, Python compilation, and full-data audits of coverage, payload hashes, ranking, calls and cost arithmetic. Raw WSJ text, API keys and response caches are not committed. Historical original artifacts remain untouched.
