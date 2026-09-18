# Benchmark 2: MS MARCO v2 / TREC DL 2021 document reranking

Completed 2026-09-18. [Issue #78](https://github.com/carlaiau/jev-reranking/issues/78).
The completed large-window experiment improves the fixed supplied ranking and
is retained as a positive result. No fresh paid repeat was run to produce this report.

## Effectiveness

57 judged queries, 100 supplied candidates each; 5,700 query/document pairs and
5,679 unique documents. MAP is evaluated at the available 100-result depth.
NIST document grades 1–3 are binary relevant; nDCG uses original graded labels
with linear gains. NIST MRR is `recip_rank`, not sparse-label MS MARCO MRR@10.

| Method | Evidence | nDCG@10 | MAP | P@10 | recip_rank |
| --- | --- | ---: | ---: | ---: | ---: |
| JEV large-window MaxP | Measured | 0.7535 | 0.2790 | 0.8930 | 1.0000 |
| PASH `pash_doc_r3` | Published | 0.7164 | 0.2672 | 0.8526 | 0.9772 |
| BERT `CIP_run2` | Published | 0.6783 | 0.2478 | 0.8140 | 0.9373 |
| BERT MaxP `CIP_run3` | Published | 0.6668 | 0.2457 | 0.8175 | 0.9567 |
| Supplied ranking | Locally evaluated | 0.5116 | 0.2126 | 0.6684 | 0.8367 |

Published values: [TREC 2021 overview, Table 2](https://www.microsoft.com/en-us/research/uploads/prod/2022/05/trec2021-deeplearning-overview-final.pdf)
and NIST summaries for [PASH](https://pages.nist.gov/trec-browser/trec30/deep/results/#pash_doc_r3),
[CIP run 2](https://pages.nist.gov/trec-browser/trec30/deep/results/#cip_run2), and
[CIP run 3](https://pages.nist.gov/trec-browser/trec30/deep/results/#cip_run3).
PASH combines DeBERTa and T5; CIP run 2 averages its top four passage scores,
while CIP run 3 uses MaxP. Their training also differs. See the
[protocol](../../msmarco-v2-documents.md) for reference selection and provenance.

JEV exceeds these selected published aggregate values. Their source run downloads
returned HTTP 401, so we cannot audit candidate identities or perform paired tests
against them. This is not a claim of statistically significant superiority over
those systems. Model training exposure is unknown. DL2019 passage, DL2021 document,
DL2023 and WSJ results must not be combined into one comparable score table.

Recall@100 remains 0.3195 and NCG@100 remains 0.4376, as expected for unchanged
candidates. Reciprocal rank 1.0000 means every query's first result has grade at
least 1; it does not mean every retrieved document is highly relevant.

## Paired comparison against supplied ranking

The sole primary test is nDCG@10. Its mean gain is **0.2419**, with 95% paired
bootstrap interval **[0.1934, 0.2927]** and two-sided sign-randomization
**p < 0.0001**. There are 53 improved queries, three worse and one tied.

| Metric | Mean paired gain | Bootstrap 95% interval | Improved / worse / tied |
| --- | ---: | --- | --- |
| nDCG@10 (primary) | 0.2419 | [0.1934, 0.2927] | 53 / 3 / 1 |
| MAP (secondary) | 0.0664 | [0.0510, 0.0833] | 55 / 2 / 0 |
| P@10 (secondary) | 0.2246 | [0.1579, 0.2947] | 38 / 4 / 15 |
| recip_rank (secondary) | 0.1633 | [0.0900, 0.2421] | 14 / 0 / 43 |

Statistics use saved four-decimal trec_eval per-query values, 10,000 bootstrap
resamples, 100,000 randomization draws and seed 78. Secondary results are
descriptive. The user cancelled the small-passage arm during inference before
final evaluation, reducing the original three-comparison plan to this one primary
test; see [scope-change.json](scope-change.json). The cancelled arm made zero calls.

## Method, time and cost

JEV `jev-1.13.0` answers the frozen Noul relevance question independently for each
window. Windows cover the entire original title, headings and body without
truncation. Each document receives its maximum window probability; ties retain
supplied ranks. This maximum is a ranking score, not a calibrated document
probability. There are 6,090 windows; 181 query/document pairs need more than one,
with a maximum of 12. The plan was frozen before measured scoring.

| Measurement | Value |
| --- | ---: |
| Scoring calls / API attempts | 6,090 / 6,090 |
| Failed scoring attempts / cache hits | 0 / 0 |
| Total reranking | 309.16 s |
| Query median / p95 | 4.81 s / 9.40 s |
| Preparation within reranking | 0.029 s |
| Total wall time, including verification/evaluation | 311.18 s |
| Input / output tokens | 41,960,380 / 133,980 |
| Estimated scoring API cost | $1.76233596 |
| Separate context-validation time | 784.96 s |
| Separate successful context-validation API cost | $1.221349878 |
| Combined known estimated API cost | $2.983685838 |

Single uncached run, eight workers per query. SDK retries were disabled, with
up to three explicit attempts allowed. Costs use $0.042 per million input tokens,
output free ([provider pricing](https://docs.typesafe.ai/models), checked 2026-09-18).
Local compute cost and billing for 23 recovered context-validation rejections
are unknown. Published-system timing/cost and supplied retrieval time are unknown;
reranking latency is not end-to-end search latency.

The [context-validation report](context-validation/results.md) records provider
probes and recursive splitting of oversized windows. All 1,925 final requests
above the conservative byte threshold were probed; maximum accepted probe usage
was 29,989 input tokens. The 4,165 smaller windows used the byte threshold without
an exact tokenizer claim. Validation scores were not reused in measured inference.

## Reproduction and evidence

The [offline audit](audit.json) passed: frozen input/source/plan hashes, exact
window identities and text hashes, complete character coverage, cached score and
token agreement, call accounting, timings, and MaxP reconstruction. It reproduced
`run.trec` and raw trec_eval output byte for byte and reevaluated the supplied
baseline. No API requests are made by the audit.

- [Frozen input manifest](input/manifest.json) and [window plan](large-window-plan.json).
- [Measured manifest](jev-large-windows/manifest.json), [raw evaluation](jev-large-windows/trec_eval.txt),
  [run](jev-large-windows/run.trec), and [per-query metrics](jev-large-windows/metrics-per-query.json).
- [Scored windows](jev-large-windows/scores.jsonl), [attempts](jev-large-windows/attempts.jsonl),
  [document scores](jev-large-windows/document-scores.json), and [query timing](jev-large-windows/queries.json).
- [Baseline evaluation](supplied-baseline/results.md) and [reproduction commands](../../msmarco-v2-documents.md#commands).

The launch manifest records source commit `a4f67e59d999fe6412d22975f57b22451a4c546f`
and a dirty working tree from generated queue/run artifacts. Recorded source
file hashes match the audited implementation. The final run SHA-256 is
`d5cffbee2a05467d4b216de4e8e56c710936f7511e5bd46c05bc1b847ef1c33a`.
Raw document text, credentials and response caches remain outside Git.
