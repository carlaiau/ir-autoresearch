# Stage-1 baseline

There is one baseline: **BM25 + query expansion, MAP 0.2521, before all reranking**.

- [Evaluation and manifest](integrated-main-20260918/results.md)
- [Raw trec_eval](integrated-main-20260918/trec_eval.txt)
- [Frozen candidate run](integrated-main-20260918/run.trec)
- [Repeated timing measurements](integrated-main-20260918/benchmark.md)

All rerankers must use these same candidates, topics and qrels. New lexical
verification runs do not supersede this baseline automatically.
