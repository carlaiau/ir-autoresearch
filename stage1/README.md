# Stage 1: lexical candidate retrieval

This discrete step builds a JASSjr-derived index, retrieves up to 1,000 documents
per topic, and saves `trec_eval` **before any neural/API reranking**. Its saved
candidate run is the common input for every stage-2 comparison.

## Implementation

The engine remains in `index/JASSjr_index.go` and `search/JASSjr_search.go`.
The saved pre-JEV configuration descends from BM25 tuning commit
`552f36baf50784122de36fc419b6cbb9eac07256`. Current code retains main's later
RM3-style feedback improvements; new runs form a separate baseline cohort.

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
   the historical saved baseline used two leading documents, one new term and
   weight 0.10. Current main defaults use five feedback documents, six expansion
   terms, weight 0.45 and a six-query-term admission limit. All effective settings
   are recorded in `lexical_config`. The runner forces `JASSJR_RERANK_DOCS=0` so
   the optional sparse passage reranking cannot leak into stage 1.
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

[Current integrated-main lexical baseline](results/integrated-main-20260918/results.md)
has MAP 0.2521 with passage reranking disabled.
[Preserved pre-JEV baseline](results/pre-jev/results.md) has MAP 0.2402.
It is the paired input for the historical JEV experiment, not a claim that it is
current main. Current `main` remains the code approval baseline. The `original`
artifacts are historical initialization data and remain untouched.

The accepted fusion, dense and rewrite code remains available through the legacy
`tools/eval_pipeline_wsj.sh` entry point. Those historical fused configurations
have different candidates and API usage; they are not interchangeable with the
new lexical-only stage-1 manifest.
