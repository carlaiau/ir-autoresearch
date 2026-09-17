# Stage 2: reranking research

The current research focus is comparing rerankers on the **same frozen stage-1
candidate run**. Stage 2 reads the saved run and writes its own evaluation and
Markdown report under `reranking/results/`; it never replaces the lexical run.

## JEV pointwise implementation

`jev.py` implements mono-like query/document scoring with TypeSafe System One.
One request contains the query and one candidate article and asks whether it
provides substantive relevant information. The `Noul` response is a score in
[0, 1]. This is a pointwise reranker, not a monoBERT checkpoint or architecture.
See the [TypeSafe reranking cookbook](https://docs.typesafe.ai/cookbooks/rerank_typesafe).

Exact DOCNO joins preserve document identity. Article fields are retained in source
order after removing DOCNO and tags, decoding entities and collapsing whitespace.
The default content policy truncates at 24,000 characters. Rerank the top K by
score, preserve the lexical order for equal JEV scores, and append the untouched
tail. Strictly decreasing synthetic TREC scores encode this final order.
All documents remain in the run, so reranking cannot increase full-run recall.

The inherited working default is K=200; the accepted historical result used K=100.
Eight concurrent workers are the default. Cache keys include endpoint, requested
model, question, payload and document hash. Missing candidates, malformed scores
or failed API calls fail the evaluation. Responses already obtained remain cached.
The mutable `jev-latest` alias is recorded alongside actual returned model IDs;
cache replay is required for exact historical reproduction.

## Run

Install `tools/requirements-jev.txt` into a virtual environment. Set
`TYPESAFE_API_KEY` and optionally `TYPESAFE_ENDPOINT` in the environment or ignored
root `.env` / `.env.local`. From the repository root:

```sh
python3 stage1/run.py /absolute/path/to/wsj.xml
# Use the exact directory printed above:
python3 reranking/run.py stage1/results/<branch>/<run-id> --top-k 100
# Repeat without making new API calls:
python3 reranking/run.py stage1/results/<branch>/<run-id> --top-k 100 --cache-only
```

Use the virtual environment's Python for stage 2. `--collection` can relocate the
WSJ file but must match its saved hash. Stage 2 also verifies run, topics and qrels
hashes before scoring. Qrels are used only by evaluation, never sent to JEV.
`tools/rerank_jev.py` remains a low-level compatibility entry point; use
`reranking/run.py` to save paired reports, timing and cost.

## Effectiveness, time and cost contract

Each run saves `results.md`, `manifest.json`, `trec_eval.txt`, `run.trec` and
`jev.json`. Report MAP, Rprec, P_10, bpref and reciprocal rank with stage-1 deltas.
Retain per-topic diagnostics and candidate recall at K when comparing depths.

The runner measures complete reranking batch wall time, including process startup,
article extraction, scoring/cache reads and output serialization. End-to-end search
is the saved stage-1 search time plus this reranking time; index construction,
data hash validation and trec_eval are excluded. This sum is a composed measurement,
not a fresh integrated service benchmark. Per-pair times live in `jev.json` and
are not query latencies. Batch time divided by topic count measures amortized
throughput. For latency studies measure individual queries separately, report
p50/p95 and repeat runs for medians; record hardware, concurrency, batching,
network region and warm-up policy. Never mix cache replay with uncached inference.

Token totals separate all scored responses from newly requested responses. To
estimate cost, supply **both** `--input-usd-per-million` and
`--output-usd-per-million`, plus `--pricing-source` containing the model, source and
effective date. No price is assumed. Reports distinguish estimated new API cost
from estimated cost of scoring all pairs without cache; missing pricing/usage is
`null` (unknown), not zero. An all-cache replay has zero new API calls. Estimates
are not invoices and may exclude provider retries or charges on failed requests.
Record actual billed spend separately, especially after interrupted experiments.
For local BERT runs use GPU/CPU seconds × an explicit hourly rate, including model
loading according to the stated benchmark scope; local inference is not free.

## Comparison protocol

| Method | Scoring unit | Status | Required controls |
| --- | --- | --- | --- |
| JEV | Query + document, pointwise | Implemented | K, model returned, question, text cap, workers, cache and token rates |
| monoBERT | Query + document, pointwise | Planned | Checkpoint/revision, tokenizer, token cap, batch size, device and compute rate |
| duoBERT | Query + document pair, pairwise | Planned | All mono settings plus pair selection, orientation and score aggregation |

The [monoBERT/duoBERT paper](https://arxiv.org/abs/1910.14424) motivates measuring
quality against latency while varying admission depth. A mono→duo cascade belongs
inside this repository's stage 2: report its component and combined time/cost.
Full ordered-pair comparison at K requires K(K−1) comparisons; sampled or pruned
pair policies must be stated explicitly.

Freeze stage-1 run/data hashes, topics, qrels and candidate depth for a paired
comparison. Match document-content policies where possible and document different
character/token limits. Label tuned results on topics 51–100 exploratory; choose
settings on separate development data before claiming held-out gains. Report
quality/time/cost tradeoffs rather than apply lexical-only slowdown thresholds to
neural reranking. Do not claim a winner when latency or cost is unknown.

[Historical JEV results](results/jev-top100/results.md) and
[implementation/experiment notes](jev-post25.md) preserve the existing evidence.
Future monoBERT and duoBERT adapters must produce the same manifest/report fields
and point back to the exact stage-1 manifest. Neither BERT comparator has been run
or implemented as part of this restructuring.
