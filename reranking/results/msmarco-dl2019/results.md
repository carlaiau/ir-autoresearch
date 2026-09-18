# MS MARCO v1 / TREC DL 2019 pointwise comparison

Status: complete. Issue [#73](https://github.com/carlaiau/jev-reranking/issues/73).

All methods scored the same **41,042 candidate pairs across 43 judged queries**.
monoBERT is the reference for this dataset. The WSJ MAP 0.2521 baseline is unchanged.

## Effectiveness

| Metric | monoBERT | JEV matched text | JEV original text |
| --- | ---: | ---: | ---: |
| ndcg_cut_10 | 0.7177 | 0.6825 | 0.6835 |
| map | 0.4488 | 0.4748 | 0.4729 |
| Rprec | 0.4650 | 0.4805 | 0.4845 |
| P_10 | 0.6233 | 0.6116 | 0.6163 |
| bpref | 0.4807 | 0.5220 | 0.5238 |
| recip_rank | 0.8717 | 0.8594 | 0.8447 |
| recall_100 | 0.5854 | 0.5989 | 0.5980 |
| recall_1000 | 0.6943 | 0.6943 | 0.6943 |

**Primary metric: nDCG@10**, using original graded judgments and trec_eval linear gains.
Binary metrics use grade >=2 as relevant; MAP treats grades 2 and 3 equally.
Recall@100 is ranking-dependent; recall@1000 covers the entire fixed candidate set and is unchanged.

## Paired primary comparisons against monoBERT

| Condition | Mean nDCG@10 delta | Bootstrap 95% CI | Two-sided p | Holm-adjusted p | Queries better / worse / tied |
| --- | ---: | --- | ---: | ---: | --- |
| jev-matched | -0.0352 | [-0.0757, +0.0053] | 0.10225 | 0.20450 | 13 / 28 / 2 |
| jev-full | -0.0342 | [-0.0764, +0.0070] | 0.11758 | 0.20450 | 15 / 24 / 4 |

Intervals are pointwise bootstrap intervals (10,000 samples); sign-randomization tests use
100,000 draws. Seed 73; Holm corrects the two headline tests. Inputs are trec_eval
per-query metrics rounded to four decimals. Secondary metric statistics are descriptive.
See [paired analysis](paired-analysis.json) for all per-query changes and secondary metrics.

## Time and cost

| Method | Reranking seconds | Query p50 seconds | Query p95 seconds | Successful scores | API attempts / failed | Estimated successful API cost USD |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| monobert | 969.83 | 22.46 | 28.02 | 41,042 | 0 / 0 | 0.000000 |
| jev-matched | 1633.43 | 37.46 | 38.57 | 41,042 | 41,045 / 3 | 0.762991 |
| jev-full | 1575.11 | 38.08 | 39.90 | 41,042 | 41,045 / 3 | 0.761027 |

Total successful-response estimated JEV API cost: **$1.524018**.
Failed-request billing and local compute cost are unknown; estimates are not invoices.
JEV used the published $0.042/million input-token rate and free output, verified 2026-09-18.
Pricing source: https://typesafe.ai/blog/introducing-system-one-models-and-jev.

These are single uncached runs, executed sequentially, not repeated benchmark medians.
monoBERT ran locally on Apple M3 Pro / 36 GiB, MPS float32, batch 8. JEV used hosted
1.13.0 with eight workers per query. Network/retries are included in JEV time.
Per-query times exclude shared setup; total reranking includes model/tokenizer loading and
preparation, scoring and output. Prior downloads, input validation and evaluation are excluded.
Supplied-candidate retrieval time is unavailable; no end-to-end search time is claimed.

## Interpretation and limits

- jev-matched: nDCG@10 -0.0352, MAP +0.0260 versus monoBERT. The primary difference is not statistically distinguishable at Holm-adjusted 0.05.
- jev-full: nDCG@10 -0.0342, MAP +0.0241 versus monoBERT. The primary difference is not statistically distinguishable at Holm-adjusted 0.05.

Retain monoBERT as the declared reference. This accepts the benchmark implementation and
audited comparison evidence; it does not promote either JEV condition as a superior replacement.
Metric tradeoffs and measured execution configurations must be stated with any quality claim.

All supplied passages fit a single BERT window. The two JEV conditions therefore compare
decoded BERT text versus original casing/spacing, **not different context coverage**.
40,804 pairs change representation under BERT decoding. Both conditions retain full passage
coverage; neither includes the complete source web article. The prompt was fixed before inference,
with no evaluation-driven tuning. MS MARCO is monoBERT's training domain; checkpoint development
history and unknown JEV training exposure preclude claims of equal training conditions.

Pairwise JEV and new context-window/listwise strategies are deferred by user instruction.
No original duoBERT checkpoint result is claimed.

## Reproduction and evidence

- [Protocol and commands](../../msmarco.md).
- [Frozen input manifest](input/manifest.json); hashes include original downloads, judgments and candidate IDs.
- [monoBERT](monobert/results.md), [audit](monobert/audit.json).
- [JEV matched](jev-matched/results.md), [audit](jev-matched/audit.json).
- [JEV original text](jev-full/results.md), [audit](jev-full/audit.json).
- [Contract tests](validation/msmarco-contracts.log), [repository smoke](validation/smoke.log).

Audits reconstruct every ranking, verify exact payload hashes and token boundaries, check all
candidate pairs, and recompute attempt/usage/cost accounting. Source/model versions are recorded
in each manifest. Dataset text, model files, credentials and response caches remain outside Git.
