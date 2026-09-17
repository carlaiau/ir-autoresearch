# Retain recall expansion; replace the final reranker with JEV

Tracking issue: https://github.com/carlaiau/ir-autoresearch/issues/61
Base: main ec2beac902d0c1c0feffeee5e46bf879146251f8.

This experiment keeps current main's indexer, BM25, RM3, expansion-only source,
dense embeddings, weighted RRF, sparse query rewrites and rewrite-derived RM3
expansion. Only the final reranker changes. JEV mode bypasses both OpenAI mono
and duo scoring, even if a local .env still selects a legacy reranker. Sparse
passage reranking is already disabled in the fused retrieval path.

## Run

Install tools/requirements-jev.txt in a Python 3.10+ environment and configure
TYPESAFE_API_KEY and OPENAI_API_KEY in .env. OpenAI is still used for retained
embeddings and query rewrites. No OpenAI reranking calls are made in JEV mode.
The wrappers now load dotenv settings in their own shell (previous command
substitution loaded settings only in a subshell).

```sh
./tests/smoke.sh
JASSJR_SEMANTIC_MODE=openai JASSJR_OPENAI_QUERY_REWRITE_MODE=sparse \
JASSJR_OPENAI_RERANK_MODE=off JASSJR_JEV_RERANK=pointwise \
JASSJR_FUSION_WEIGHT_BM25=0.05 JASSJR_FUSION_WEIGHT_RM3=0.55 \
JASSJR_FUSION_WEIGHT_DENSE=0.40 JASSJR_JEV_PYTHON=/path/to/venv/bin/python \
  ./tools/eval_wsj.sh /absolute/path/to/wsj.xml
```

Those explicit fusion weights are the later accepted main defaults, superseding
the original scaffold's 0.45/0.35/0.20 preset. Other retained source weights are
RM3 expansion 0.10, rewrite 0.08, rewrite expansion 0.05. Read the run metadata
for the actual effective configuration.

The evaluator supplies the original collection path to the pipeline and records
the pre-JEV run, final run and per-request JEV metadata as branch artifacts.
For direct pipeline calls, also set JASSJR_JEV_COLLECTION. Use
JASSJR_JEV_CACHE to share existing pointwise response caches across experiments.
On this Mac, Python's default CA path was absent; SSL_CERT_FILE=/etc/ssl/cert.pem
selects the system CA bundle without disabling certificate verification.

## Pointwise reranking

Pointwise retains the successful #58 question, top-100 prefix, 24000-character
article limit and full-input cache keys. It scores each query/document pair
independently; it is not pairwise document comparison. Original document text is
joined by DOCNO. Qrels never enter the model payload. Per-topic candidates and
the tail remain intact, and output scores encode the final order for trec_eval.

Choice comparison and a matched article-budget control are planned on a separate experiment branch. They are not part of this accepted implementation.

The endpoint rejected the cookbook's jev-1.12; jev-latest currently returns
jev-1.13.0. Cache replay is reproducible, but the alias itself can change. Record
and inspect actual response models before combining fresh and cached judgments.

## Validation and acceptance

Compare identical fused candidates before reranking, with JEV pointwise, and
with JEV Choice. Report MAP, Rprec, P_10, bpref, recip_rank, per-topic AP and
candidate recall. Main is the approval baseline; original artifacts remain
read-only initialization history. The previous post-25 JEV result (MAP 0.2925)
is a useful separate comparator. The archived main API-assisted result was
MAP 0.2867; fresh recall generation can differ because query rewrites and models
may have changed since that run.

Local tests cover DOC boundaries/entities, invalid probabilities, stable ties,
candidate preservation, and bypassing the legacy
reranker even when its old mode is set. Full WSJ pointwise results are recorded below.

## Accepted pointwise result

Full evaluation completed on 2026-09-17 with all 5000 query/document pairs,
including 5000 cached judgments in final validation. All responses reported jev-1.13.0. Three pairs
were truncated at 24000 characters. Token usage including cache was 7,440,322
input and 110,000 output tokens; this is not the cost of new requests alone.

| Metric | Identical fusion before JEV | JEV pointwise |
|---|---:|---:|
| MAP | 0.2833 | 0.3265 |
| Rprec | 0.3159 | 0.3463 |
| P_10 | 0.5060 | 0.6660 |
| bpref | 0.3545 | 0.3904 |
| recip_rank | 0.7730 | 0.8963 |

In final validation, AP improved on 46 topics and worsened on 4. The first run had 45 improvements, 4 declines and 1 tie; fresh query embeddings slightly changed the candidate ordering. The retrieved set and
order after rank 100 are unchanged. Fusion retrieved 4175 judged relevant
documents, compared with 3755 in the historical post-25 engine. Its top 100
contain 1527 relevant documents (24.52% micro recall), versus 1370 previously.

Fresh main with external modes off reached MAP 0.2530; the historical API-assisted
main report reached 0.2867. The previous post-25 JEV experiment reached 0.2925.
Original's 0.2080 is archival initialization data, not the approval baseline.

Smoke/contract checks, full WSJ evaluation and exact cache replay passed.
Indexing, lexical retrieval, fusion algorithms and recall-source implementation
files are unchanged from main. No benchmark was run. Evaluation-only dashboard
rows are supported with n/a timings. Choice has only a pilot result so far and
remains experimental pending a separate full comparison.

Corpus length statistics are in wsj-length-statistics.json. Full original text
averages 629.3 cl100k_base tokens (population standard deviation 610.1; maximum
20933). Indexed token occurrences average 456.5 (standard deviation 459.8;
maximum 12804). The retained 220-term embedding prefix truncates 55.4% of articles.

Final pointwise-only validation (trec_eval-20260917-160716.txt) reproduced all five headline metrics with 5000 cached JEV judgments. Fresh query embeddings changed some tail ordering relative to the first run; each run preserves its own pre-JEV tail. The exact replay claim refers to fixed saved candidates. Choice controls use a fixed saved candidate file.
