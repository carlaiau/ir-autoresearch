# Stage 1: lexical candidate retrieval

This discrete step builds a JASSjr-derived index, retrieves up to 1,000 documents
per topic, and saves `trec_eval` **before any neural/API reranking**. Its saved
candidate run is the common input for every stage-2 comparison.

## Implementation

The engine remains in `index/JASSjr_index.go` and `search/JASSjr_search.go`.
The current configuration descends from the pre-JEV BM25 tuning commit
`552f36baf50784122de36fc419b6cbb9eac07256`.

1. Read WSJ records and associate terms with DOCNO. The lexer recognizes ASCII
   alphanumeric tokens (including internal hyphens), lowercases them and applies
   lightweight plural conflation. It skips tags and the DOCNO, DD, SO, IN and
   DATELINE fields. Headline occurrences count twice in term frequency and length.
   The lexical lexer does not perform general XML entity decoding; freeze this
   behavior for paired comparisons rather than silently changing tokenization.
2. Write vocabulary, postings, document IDs, weighted lengths and forward vectors.
3. Score title queries with BM25: `k1=0.7`, `b=0.3`, and `log(N/df)` IDF.
   `JASSJR_BM25_K1` and `JASSJR_BM25_B` override these defaults and are recorded.
4. Apply existing lightweight pseudo-relevance feedback inside lexical retrieval:
   use two leading documents, select one new term and add it at weight 0.10.
   This baseline is BM25 **with feedback**, not pure one-pass BM25.
5. Emit up to 1,000 nonzero-scoring results per query in TREC format. The engine
   breaks exact score ties by descending internal document ID. Evaluation and
   JEV's candidate reader use emitted scores with descending DOCNO tie ordering.
6. Evaluate the complete lexical run using `trec_eval -c -M1000` and freeze it.

## Run and save

Requires Go, Python 3.10+ and `trec_eval` on PATH. From the repository root:

```sh
python3 stage1/run.py /absolute/path/to/wsj.xml
# Compatibility entry point for the same stage:
./tools/eval_wsj.sh /absolute/path/to/wsj.xml
```

The printed directory is `stage1/results/<branch>/<UTC-run-id>/`. It contains
`results.md`, `trec_eval.txt`, `run.trec`, copied topics/qrels, `index.log` and
`manifest.json`. The manifest records source/data/run hashes, commit, dirty state,
BM25 settings, environment and one measured indexing/search pass. Fresh directories
prevent overwriting a baseline. Preserve the whole directory for reproducibility;
WSJ article text, index files and credentials are not included.

Search time covers process startup, index loading, all topics, feedback and run
output; indexing/building and evaluation are excluded. API cost is zero; local
compute cost is unknown unless separately measured. These single-pass timings are
not benchmark medians. Use `./tools/benchmark_wsj.sh -n 5 /absolute/path/to/wsj.xml`
for repeated lexical benchmarks (legacy branch artifact directory).

`JASSJR_JEV_RERANK=on` is rejected here. Start stage 2 explicitly only after this
step succeeds. `-t`, `-q`, `-w` and `-o` remain supported; input is now a single WSJ
file, not a directory. `--results-dir` selects a new explicit result directory.

## Baselines

[Preserved pre-JEV baseline](results/pre-jev/results.md) has MAP 0.2402.
It is the paired input for the historical JEV experiment, not a claim that it is
current main. Current `main` remains the code approval baseline. The `original`
artifacts are historical initialization data and remain untouched.
