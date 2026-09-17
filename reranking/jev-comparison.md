# JEV: identical passages versus complete documents

These two experiments share `codex/search-jev-passages-vs-documents`, as requested.
Tracking: [passage MaxP #68](https://github.com/carlaiau/ir-autoresearch/issues/68)
and [complete documents #69](https://github.com/carlaiau/ir-autoresearch/issues/69).
The monoBERT implementation was merged in [PR #67](https://github.com/carlaiau/ir-autoresearch/pull/67).

## Fixed comparison

Both experiments read the frozen MAP **0.2521** stage-1 candidate run and the
completed monoBERT reference (MAP **0.2693**). Use all 50 topics and the same top
100 candidates per topic: 5,000 query/document pairs. Keep the existing JEV Noul
relevance question unchanged. Reorder only the candidate prefix; equal scores
keep stage-1 order, and the remaining 900 documents per query stay in place.
Indexing and the frozen stage-1 artifacts are unchanged.

1. **Passage MaxP:** reconstruct the pinned monoBERT tokenization and verify every
   interval against its committed `passages.jsonl`. Send all 19,593 slices to JEV
   independently. A document's score is its maximum passage Noul score.
2. **Complete documents:** send the complete parsed article with the query in one
   request. Its Noul score is the document score. There is no character cap,
   summarization, passage selection or truncation.

JEV accepts text rather than BERT token IDs. Passage payloads use the pinned BERT
tokenizer's decoded slices with cleanup disabled; boundaries are identical, but
BERT normalization (including uncasing) and possible boundary wordpiece markers
remain in the decoded text. Original casing/spacing is not restored. JEV then
uses its own tokenizer. Scores include hashes of both the source token IDs and
submitted passage text, enabling exact reconstruction without storing article
text in Git. This is a matched passage-boundary comparison, not identical model
input token IDs across two different tokenizers. Whole-document payloads preserve
the original parsed text, so that comparison also changes representation.

The reader removes markup/DOCNO, decodes entities and collapses whitespace, while
retaining other fields, including the headline. This is the same full-document
reader used by monoBERT. Full-document means all of this parsed text is submitted;
it is not a claim about undisclosed provider-side internal processing. An API
size error fails the experiment explicitly rather than triggering truncation.

## Run

Use the environment from monoBERT and the pinned SDK:

```sh
.venv-monobert/bin/python -m pip install -r tools/requirements-jev.txt \
  --extra-index-url https://pypi.typesafe.ai/
.venv-monobert/bin/python reranking/jev_compare.py \
  --mode passages --expected-model jev-1.13.0 \
  --results-dir reranking/results/jev-passages-maxp-top100-20260918-retry \
  --cache .cache/jev-passages-maxp-top100-20260918-retry \
  --input-usd-per-million 0.042 --output-usd-per-million 0 \
  --pricing-source 'https://typesafe.ai/blog/introducing-system-one-models-and-jev; verified 2026-09-18'
.venv-monobert/bin/python reranking/jev_compare.py \
  --mode documents --expected-model jev-1.13.0 \
  --results-dir reranking/results/jev-full-documents-top100-20260918 \
  --cache .cache/jev-full-documents-top100-20260918 \
  --input-usd-per-million 0.042 --output-usd-per-million 0 \
  --pricing-source 'https://typesafe.ai/blog/introducing-system-one-models-and-jev; verified 2026-09-18'
```

Requires `TYPESAFE_API_KEY` in the environment or ignored `.env`/`.env.local`, the
local WSJ collection and prefetched monoBERT tokenizer. It does not run the BERT
model. Use separate fresh caches for initial measurements. Existing result
directories are refused. A rerun with a reused cache is explicitly labeled mixed
or all-cached; use `--cache-only` for response replay without API requests.

## Timing, calls and cost

Run the two methods sequentially, with eight HTTP requests in flight per query
and queries processed sequentially. There is no warm-up phase. The client uses
connection pooling; network timings include latency from the current machine,
not solely JEV inference. Record returned model identifiers for the mutable
`jev-latest` alias. `--expected-model` can reject an unexpected returned model.

SDK retries are disabled. The runner allows at most three explicit attempts per
score for HTTP 429/5xx or connection/timeout errors, with 2/4-second backoff before
the second/third attempt, or the provider's longer Retry-After delay. Every completed attempt is journaled with duration,
status and identity. Permanent errors stop scheduling new work; at most eight
already-dispatched calls may still finish. Successful responses remain cached.
Exception bodies, article text and API keys are omitted from committed evidence.

Reports separate successful scoring units, actual API attempts, failed attempts,
cache hits, reported input/output usage, estimated API cost, shared preparation,
reranking time and query p50/p95. Query latency includes concurrent scoring,
retries and evidence writes, but excludes shared preparation. Composed end-to-end
time adds the saved stage-1 search time to reranking time. Each initial result is
one uncached run, not a repeated benchmark median.

[TypeSafe's published pricing](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
is $0.042 per million input tokens and free output, verified September 18, 2026.
Estimates use actual reported usage from successful responses. Failed-request
charges are unknown; these estimates are not invoices. Missing usage/rates produce
unknown cost. Local compute cost stays unknown as requested.

## Validation and evidence

Run `bash tests/jev_compare.sh`, `bash tests/monobert.sh`,
`bash tests/two_stage.sh` and `./tests/smoke.sh`. The comparison tests cover saved
window identity, document tails, uncapped article submission, cache isolation,
attempt counts, invalid scores and bounded failure dispatch.

Completed result directories contain a Markdown report, provenance manifest,
TREC run, aggregate and paired per-topic evaluations, candidate recall, query
times, score records and attempt records. Raw API response caches remain ignored.
A failed run gets `failure.json` and is not a completed effectiveness evaluation.

Both runs completed. See the [paired results](results/jev-comparison-20260918.md),
including the failed first attempt, full evidence audits and measured tradeoffs.

To independently verify the submitted text hashes, full coverage, ranking and
accounting from the local collection and saved evidence:

```sh
.venv-monobert/bin/python reranking/audit_jev_compare.py \
  reranking/results/jev-passages-maxp-top100-20260918-retry
.venv-monobert/bin/python reranking/audit_jev_compare.py \
  reranking/results/jev-full-documents-top100-20260918
```
