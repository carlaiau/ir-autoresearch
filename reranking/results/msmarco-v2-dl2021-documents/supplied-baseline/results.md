# DL2021 document supplied-ranking baseline

The official top-100 candidates, before JEV reranking: 57 judged queries, 5,700 pairs and 5,679 distinct documents.

| MAP | P@10 | NIST MRR | NDCG@10 | NCG@100 | Recall@100 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.2126 | 0.6684 | 0.8367 | 0.5116 | 0.4376 | 0.3195 |

Document grades 1–3 count as binary relevant. Graded metrics retain original grades. Original retrieval scores are preserved, including trec_eval tie handling. Retrieval time is unknown.

Evaluation:

```sh
trec_eval -q -c -M100 -l 1 -m map -m recip_rank -m P.10 -m recall.100 -m ndcg_cut.10 ../input/qrels.txt run.trec
```

NCG@100 is computed separately as retrieved linear gain divided by ideal top-100 gain, averaged across queries.

Evidence: [raw trec_eval](trec_eval.txt), [per-query metrics](metrics-per-query.json), [manifest](manifest.json), [frozen input](../input/manifest.json), [extraction audit](../extraction-audit.json).

Published comparisons are in [the protocol](../../../msmarco-v2-documents.md). No JEV effectiveness results exist for this dataset yet.
