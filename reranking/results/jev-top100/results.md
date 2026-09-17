# Historical JEV top-100 result

Paired with the [preserved stage-1 run](../../../stage1/results/pre-jev/results.md).
Its SHA-256 matches the input hash recorded by JEV. The full raw results are
preserved; this report does not relabel an old run as a new benchmark.

| Metric | Stage 1 | JEV top 100 | Delta |
| --- | ---: | ---: | ---: |
| MAP | 0.2402 | 0.2925 | +0.0523 |
| Rprec | 0.2826 | 0.3143 | +0.0317 |
| P_10 | 0.4320 | 0.6100 | +0.1780 |
| bpref | 0.3062 | 0.3445 | +0.0383 |
| recip_rank | 0.6388 | 0.8322 | +0.1934 |

4,959 pairs across 50 topics; model returned `jev-1.13.0`. One cached pair,
11 truncated pairs. All responses total 7,595,855 input and 109,098 output tokens.
[Manifest](manifest.json) separates new-response usage from cache-inclusive usage.
Reranking time, end-to-end search time and dollar cost are **unknown**. No
monoBERT/duoBERT speed or cost comparison is established by these results.

[Raw trec_eval](trec_eval.txt) · [Reranked run](run.trec) ·
[Experiment discussion](../../jev-post25.md)

Original archive MAP was 0.2080 (JEV +0.0845); original is historical
initialization data, not the approval baseline. Current main is the code baseline.
