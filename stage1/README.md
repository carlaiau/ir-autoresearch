# Stage 1: lexical candidate retrieval

This discrete step builds a JASSjr-derived index, retrieves up to 1,000 documents
per topic, and saves `trec_eval` **before any neural/API reranking**. Its saved
candidate run is the common input for every stage-2 comparison.

## Implementation

The engine remains in `index/JASSjr_index.go` and `search/JASSjr_search.go`.
The sole baseline is the saved BM25 + query-expansion run with **MAP 0.2521**,
before all reranking. Its implementation and settings are described below.

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
   the fixed baseline uses five feedback documents, six expansion
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

## Fixed stage-1 baseline

[Stage 1 baseline: BM25 + query expansion](results/integrated-main-20260918/results.md)

| MAP | Rprec | P_10 | bpref | recip_rank |
| ---: | ---: | ---: | ---: | ---: |
| **0.2521** | 0.2989 | 0.4460 | 0.3178 | 0.6271 |

All reranking is disabled (`JASSJR_RERANK_DOCS=0`). No JEV, OpenAI reranker,
dense-retrieval or query-rewrite sidecar contributes to this run. The saved folder
name identifies when the run was captured; it does not name another algorithm.

Use this exact saved `run.trec`, topics and qrels for every reranking comparison.
Candidate SHA-256:
`d1f737713de16e857ba69988ee85f5d30fef2bc4f4d6004d4ff73e87c7c9045b`.

The [manifest](results/integrated-main-20260918/manifest.json) records all effective
settings and content hashes. The [benchmark](results/integrated-main-20260918/benchmark.md)
records five-run medians: 11.03 s indexing and 0.41 s for all 50 title queries.
Single-pass timings in the manifest are separate measurements.

Do not replace this baseline automatically when main changes or when an evaluation
is rerun. Any proposed replacement requires an explicit decision. The completed JEV
passage and whole-document results use this same saved baseline; see the
[paired comparison](../reranking/results/jev-comparison-20260918.md).
