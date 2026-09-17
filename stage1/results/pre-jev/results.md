# Preserved pre-JEV stage-1 result

Historical run from lexical parent `552f36baf50784122de36fc419b6cbb9eac07256`.
Copied without regenerating from the original JEV experiment artifacts. This is
the pre-reranking result, distinct from current main and the original archive.

| MAP | Rprec | P_10 | bpref | recip_rank |
| ---: | ---: | ---: | ---: | ---: |
| 0.2402 | 0.2826 | 0.4320 | 0.3062 | 0.6388 |

[Raw trec_eval](trec_eval.txt) · [Candidate run](run.trec)

Search time and indexing time were not measured in this historical evaluation.
API cost: zero (lexical retrieval). Local compute cost: unknown.
A separate historical lexical benchmark reported 10.61 s indexing and 0.22 s
search medians; it is not a paired timing measurement for the JEV run.
See [benchmark source](../../../experiment_benchmarks/codex/search-bm25-grid-search/benchmark-20260317-130428.txt).

Source: [lexical evaluation](../../../experiment_evaluations/codex/search-jev-post25/trec_eval-20260917-151334.txt).
For a runnable stage manifest use the fresh lexical baseline directory alongside
this preserved historical result. Do not invent missing historical provenance.
