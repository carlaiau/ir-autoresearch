# Two-stage retrieval and reranking research

**Stage 1 is fixed at MAP 0.2521, before all reranking.** Its saved candidate
run is the sole baseline for JEV, monoBERT and duoBERT experiments.

| Stage | Status | MAP | Results |
| --- | --- | ---: | --- |
| Stage 1: BM25 + query expansion | Fixed baseline; all reranking disabled | **0.2521** | [Saved baseline](stage1/results/integrated-main-20260918/results.md) |
| Stage 2: JEV passage MaxP | Evaluated; hosted JEV | **0.3053** | [Results](reranking/results/jev-passages-maxp-top100-20260918-retry/results.md) |
| Stage 2: JEV complete document | Evaluated; hosted JEV | **0.3055** | [Results](reranking/results/jev-full-documents-top100-20260918/results.md) |
| Stage 2: monoBERT MaxP, top 100 | Evaluated; local Apple GPU | **0.2693** | [Full-document results](reranking/results/monobert-maxp-top100-20260918/results.md) |
| Stage 2: JEV duo Noul, top 20 | Rejected; worse than pointwise input | **0.3019** | [Outcome and cost](reranking/results/jev-duo-noul-top20-20260918/summary.md) |
| Stage 2: duoBERT | Planned | Pending | [Reranking methodology](reranking/README.md) |

The stage-1 baseline uses BM25 (`k1=0.7`, `b=0.3`) with five feedback documents,
six expansion terms, expansion weight 0.45 and a six-query-term admission limit.
Sparse passage reranking is disabled. JEV, OpenAI reranking, dense retrieval and
query-rewrite sidecars are not part of this baseline.

The saved baseline contains the candidate run, topics, qrels, raw `trec_eval`,
source/data hashes and timing evidence. Five-run medians are **11.03 s indexing**
and **0.41 s search for all 50 topics**. See [stage 1](stage1/README.md).

Full-document monoBERT scored 19,593 passages in 2,475 batched model calls.
Added reranking time was **1,510.93 s** for all 50 topics; median per-query time
was **30.27 s**, excluding shared setup. Hosted inference API cost was $0; local
compute cost is unknown. This is one exploratory uncached run, not a latency or
cost winner. See the [implementation](reranking/monobert.md).

Both JEV experiments are complete. Passage MaxP used 19,593 scores,
with 767.73 s added time and an estimated $0.605227 API cost.
Complete-document scoring used 5,000 scores, with 211.49 s
added time and an estimated $0.328312 API cost. See the
[paired comparison](reranking/results/jev-comparison-20260918.md), including the
failed first attempt and full cost/timing scope. Local compute remains unknown.

`stage1/run.py` and `tools/eval_wsj.sh` can verify lexical retrieval, but their
outputs do not automatically replace the fixed baseline. `main` is the code
integration branch; the saved stage-1 run is the experimental comparison baseline.
The original initialization archive remains read-only and is not a competing
baseline. Legacy combined-pipeline commands are outside this comparison workflow.

## Inspiration And Provenance

This project is inspired by two upstream efforts:

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch), which frames software improvement as an autonomous experiment loop driven by branch-based iteration and measurable outcomes. That repository is MIT-licensed.
- [andrewtrotman/JASSjr](https://github.com/andrewtrotman/JASSjr), which provides the minimal BM25 search engine foundation and the teaching-oriented WSJ/TREC setup that this repository adapts. JASSjr is BSD-2-Clause licensed and this repo keeps that upstream attribution in derived source files and includes the BSD-2-Clause text in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).

The goal here is to bring the autonomous experiment-management ideas from `autoresearch` into information retrieval, and to further test the hypothesis that an agent can improve any system as long as it has a measurable objective.

This project is licensed under the MIT License, except for JassJr related code which is included in this repository, which are licensed under their respective open-source licenses, please see THIRD_PARTY_NOTICES.txt for details.
