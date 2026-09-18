# MS MARCO v2: document reranking with JEV

[Issue #78](https://github.com/carlaiau/jev-reranking/issues/78).
Status: all 5,679 candidate documents recovered and verified; input frozen.
[Supplied baseline](results/msmarco-v2-dl2021-documents/supplied-baseline/results.md):
MAP 0.2126, P@10 0.6684, NIST MRR 0.8367, NDCG@10 0.5116.
[Context validation](results/msmarco-v2-dl2021-documents/context-validation/results.md)
passed: 6,090 large windows, maximum accepted probe 29,989 tokens, complete text
coverage. Large-window JEV inference and the independent audit are complete:
[results](results/msmarco-v2-dl2021-documents/results.md) report MAP 0.2790,
P@10 0.8930, NIST MRR 1.0000 and NDCG@10 0.7535. Small-passage MaxP was cancelled
before its first call; it was only needed for a direct monoBERT comparison.
Historical preflight counts are retained as preparation evidence.

Evaluate JEV large-window MaxP against supplied retrieval and published rerankers on the official
TREC DL 2021 document top-100 lists. All 57 judged queries have 100 candidates:
5,700 pairs, 5,679 unique documents. This is separate from the DL2019 passage
experiment and frozen WSJ baseline. No monoBERT inference is required.

## Published references

| Published run | MAP, depth 100 | P@10 | NIST MRR | NDCG@10 | NCG@100 |
| --- | ---: | ---: | ---: | ---: | ---: |
| PASH `pash_doc_r3` | 0.2672 | 0.8526 | 0.9772 | 0.7164 | 0.4376 |
| BERT `CIP_run2` | 0.2478 | 0.8140 | 0.9373 | 0.6783 | 0.4376 |
| BERT MaxP `CIP_run3` | 0.2457 | 0.8175 | 0.9567 | 0.6668 | 0.4376 |

Source: [TREC 2021 overview, Table 2](https://www.microsoft.com/en-us/research/uploads/prod/2022/05/trec2021-deeplearning-overview-final.pdf).
P@10 is available in the official NIST summaries for
[PASH](https://pages.nist.gov/trec-browser/trec30/deep/results/#pash_doc_r3),
[CIP run 2](https://pages.nist.gov/trec-browser/trec30/deep/results/#cip_run2) and
[CIP run 3](https://pages.nist.gov/trec-browser/trec30/deep/results/#cip_run3).
Their MAP, MRR and NDCG@10 also agree with the overview; all three report
recall@100 of 0.3195. Verified 2026-09-18.

PASH combines DeBERTa-2.6B and T5-3B in a multistage system. CIP run 2 uses
BERT-large and averages its four highest passage scores. CIP run 3 uses the
highest passage score (MaxP), making it a useful additional architectural
reference for our window aggregation. Their training differs too, so the CIP
comparison does not isolate aggregation alone. See the official
[run descriptions](https://pages.nist.gov/trec-browser/trec30/deep/runs/#cip_run2).
PASH and CIP run 2 remain the two preselected references; CIP run 3 is additional
context identified before any JEV evaluation.

These are published reranking systems, not locally reproduced checkpoints.
Original run downloads return HTTP 401 as checked on 2026-09-18. Compare
aggregates; paired tests against these systems require their per-query outputs.
Comparable timing, call counts and dollar cost are not supplied by these result
tables; leave them unknown. NIST MRR is `recip_rank`, not sparse-label MS MARCO
MRR@10. Published references do not require running their models locally.

The [2023 overview](https://trec.nist.gov/pubs/trec32/papers/Overview_deep.pdf)
is additional context. Its document table uses 82 different queries and all
listed systems are full-ranking pipelines. Those scores are not interchangeable
with the DL2021 fixed-candidate reference scores.

## Inputs and full-document coverage

Use [official DL2021 downloads](https://microsoft.github.io/msmarco/TREC-Deep-Learning-2021.html):
`2021_queries.tsv`, `2021_document_top100.txt.gz`, and final NIST document qrels.
The candidate file contains IDs and retrieval ranks/scores, not document text.
Candidate IDs occur in all 60 compressed shards of `msmarco_v2_doc.tar`.
`fetch_msmarco_v2.py` streams that archive in bounded parallel byte ranges and
keeps only the selected original JSON records. It verifies document IDs against
encoded byte offsets, gzip integrity and the official archive MD5; it records
SHA-256 evidence. No new index is built and no candidates are added from qrels.

Canonical text preserves complete TITLE, HEADINGS and BODY fields with explicit
separators. URL is excluded. Frozen inputs contain hashes and IDs, not raw text.
Reranker score ties preserve original supplied ranks; synthetic monotonic output
scores preserve that ordering in evaluation. The supplied baseline retains the
original retrieval scores and trec_eval's score-tie handling.

- **JEV large-window MaxP:** overlapping windows sized for JEV's context budget,
  preserving the complete original canonical text. Take the maximum Noul score
  across all windows. Short documents fit one window. This user-approved design
  replaces the original single-call full-document arm. Initial windows contain
  at most 110,000 UTF-8 bytes of original text, with up to 4,000 bytes of overlap.
  Boundaries always fall between Unicode characters.

The active run uses the frozen Noul question, pinned `jev-1.13.0`, eight workers
within each query, explicit retries and a fresh cache. The prompt is in
`msmarco_v2_documents.py`. It is frozen before evaluation, with no test-set tuning.

JEV documentation currently specifies 32k tokens for state plus the longest
question. Reserve space for the query, instructions, criteria and formatting.
The published API and installed SDK expose no exact JEV tokenizer or token-count
endpoint. UTF-8 byte lengths are a sizing proxy, not model token counts.
Every initial request above 28,000 serialized UTF-8 bytes is probed against JEV.
If the provider rejects its context size, or reports more than 30,000 input
tokens, halve that text window's byte cap and repeat with overlap. Smaller
requests use a conservative byte threshold without a claim of exact tokenization.
Unrelated API errors stop validation. Actual relevance scores and qrels are never
used to choose window sizes.

Freeze the resulting per-query/document character intervals in
`large-window-plan.json`. Before timed runs, audit complete text coverage and
confirm every final request above the probe threshold has an accepted probe
within the token budget. These are empirical checks of the current dataset and
provider, not a universal tokenizer guarantee. Provider input-limit failures in
the measured runs stop execution and preserve evidence rather than silently
changing the plan. Probe cost/time is separate; measured runs use fresh caches.

MaxP uses the maximum window probability as a ranking score; it does not imply
that the maximum is a calibrated probability for the entire document.

## Evaluation and accounting

Primary: NDCG@10 on original graded labels with linear gains. Secondary: MAP at
100-result depth, P@10, NIST MRR, recall@100 and NCG@100. Document grades 1–3 are
binary relevant, unlike the earlier passage task. NCG@100 divides retrieved gain
by ideal gain at rank 100 (not all judged gain); it must stay constant under
reranking. Record exact evaluation commands and original judgments.

The remaining headline comparison is large-window JEV versus supplied retrieval.
Use paired bootstrap intervals (10,000 resamples) and sign randomization
(100,000 draws), seed 78, for its NDCG@10 difference. The original three-comparison
plan was reduced at the user's request during inference, before final effectiveness
evaluation. Report the single-comparison p-value; the cancelled comparisons will
not be tested. Published-reference
comparisons remain descriptive without per-query source runs. Record this scope
change in [scope-change.json](results/msmarco-v2-dl2021-documents/scope-change.json).
Unknown model training exposure limits held-out claims.

Record actual attempts, retries, successful scores, cache hits, returned token
usage, setup, total reranking time and query p50/p95. Rate verified 2026-09-18:
$0.042/M input tokens, output free ([source](https://docs.typesafe.ai/models)).
Preflight character/4 token and cost estimates are rough planning values only.
Local compute and failed-request charges are unknown. Supplied retrieval time is
unknown; no end-to-end search time or speed superiority against published systems
is claimed. Cached replay is separate from uncached performance.

## Commands

Download the three small inputs into ignored `.cache/msmarco-v2-dl2021/`, named
`queries.tsv`, `candidates.gz`, `qrels.txt`, then:

```sh
python3 reranking/fetch_msmarco_v2.py .cache/msmarco-v2-dl2021
python reranking/msmarco_v2_documents.py prepare
python reranking/msmarco_v2_documents.py validate-windows \
  --results-dir reranking/results/msmarco-v2-dl2021-documents/context-validation \
  --cache .cache/msmarco-v2-dl2021/context-validation
python reranking/msmarco_v2_documents.py preflight --model-cache /path/to/tokenizer-cache
python reranking/msmarco_v2_documents.py jev-large-windows \
  --model-cache /path/to/tokenizer-cache \
  --results-dir reranking/results/msmarco-v2-dl2021-documents/jev-large-windows \
  --cache .cache/msmarco-v2-dl2021/jev-large-windows
```

The superseded `jev-full` command has been removed. The small-passage command is
retained for future explicitly authorized monoBERT comparisons, but is outside
this experiment. The compatibility launcher `run_msmarco_v2_pair.py` now starts
only the approved large-window condition.

The original two-run controller was stopped without interrupting its large-window
child, which subsequently completed. The final `jev-large-windows/manifest.json`
and `audit.json` record completion; `run-queue.json` records the cancelled arm.
Run `python reranking/audit_msmarco_v2.py` to reproduce the offline audit using
the retained local documents and response cache; this makes no API requests.

Use the installed JEV/tokenizer environment; `--env-root` can point to an existing
checkout's ignored credentials. Prepare only once; frozen inputs/results cannot
be overwritten. If Python cannot locate its CA bundle, configure `SSL_CERT_FILE`
with the system trust bundle; do not disable TLS verification.

Offline checks: `python tests/fetch_msmarco_v2.py`,
`python tests/msmarco_v2_documents.py` (the latter requires the JEV environment),
and `./tests/smoke.sh`.
